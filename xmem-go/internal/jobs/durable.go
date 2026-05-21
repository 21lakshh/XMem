package jobs

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log/slog"
	"math"
	"sort"
	"strings"
	"sync"
	"time"
)

type Status string

const (
	StatusQueued     Status = "queued"
	StatusRunning    Status = "running"
	StatusSucceeded  Status = "succeeded"
	StatusFailed     Status = "failed"
	StatusDeadLetter Status = "dead_letter"
)

var terminalStatuses = map[Status]bool{
	StatusSucceeded:  true,
	StatusDeadLetter: true,
}

type Job struct {
	ID             string         `json:"job_id" bson:"job_id"`
	Type           string         `json:"job_type" bson:"job_type"`
	IdempotencyKey string         `json:"idempotency_key" bson:"idempotency_key"`
	UserID         string         `json:"user_id" bson:"user_id"`
	Payload        map[string]any `json:"payload,omitempty" bson:"payload,omitempty"`
	Status         Status         `json:"status" bson:"status"`
	RetryCount     int            `json:"retry_count" bson:"retry_count"`
	MaxAttempts    int            `json:"max_attempts" bson:"max_attempts"`
	TimeoutSeconds float64        `json:"timeout_seconds" bson:"timeout_seconds"`
	Error          string         `json:"error,omitempty" bson:"error,omitempty"`
	ErrorState     map[string]any `json:"error_state,omitempty" bson:"error_state,omitempty"`
	Result         any            `json:"result,omitempty" bson:"result,omitempty"`
	CreatedAt      time.Time      `json:"created_at" bson:"created_at"`
	UpdatedAt      time.Time      `json:"updated_at" bson:"updated_at"`
	StartedAt      *time.Time     `json:"started_at,omitempty" bson:"started_at,omitempty"`
	CompletedAt    *time.Time     `json:"completed_at,omitempty" bson:"completed_at,omitempty"`
	DeadLetteredAt *time.Time     `json:"dead_lettered_at,omitempty" bson:"dead_lettered_at,omitempty"`
}

type EnqueueInput struct {
	JobType           string
	Payload           any
	IdempotencyFields any
	UserID            string
	TimeoutSeconds    float64
	MaxAttempts       int
}

type Store interface {
	Enqueue(ctx context.Context, input EnqueueInput) (Job, bool, error)
	Get(ctx context.Context, jobID string) (Job, bool, error)
	ClaimForRun(ctx context.Context, jobID string) (Job, bool, error)
	MarkSucceeded(ctx context.Context, jobID string, result any) error
	MarkFailed(ctx context.Context, jobID string, err string) (Status, error)
	ResetForRetry(ctx context.Context, jobID string) error
}

type Handler func(context.Context) (any, error)

func Run(ctx context.Context, store Store, logger *slog.Logger, jobID string, handler Handler) {
	if logger == nil {
		logger = slog.Default()
	}
	for {
		job, ok, err := store.Get(ctx, jobID)
		if err != nil {
			logger.Error("durable job lookup failed", "job_id", jobID, "error", err)
			return
		}
		if !ok {
			logger.Warn("durable job disappeared before execution", "job_id", jobID)
			return
		}
		if terminalStatuses[job.Status] {
			return
		}

		claimed, ok, err := store.ClaimForRun(ctx, jobID)
		if err != nil {
			logger.Error("durable job claim failed", "job_id", jobID, "error", err)
			return
		}
		if !ok {
			logger.Info("durable job already claimed; skipping duplicate runner", "job_id", jobID)
			return
		}

		timeout := time.Duration(claimed.TimeoutSeconds * float64(time.Second))
		if timeout <= 0 {
			timeout = 120 * time.Second
		}
		attemptCtx, cancel := context.WithTimeout(ctx, timeout)
		started := time.Now()
		result, runErr := handler(attemptCtx)
		cancel()
		if runErr == nil {
			payload := toMap(result)
			payload["elapsed_ms"] = float64(time.Since(started).Microseconds()) / 1000
			if err := store.MarkSucceeded(ctx, jobID, payload); err != nil {
				logger.Error("durable job success update failed", "job_id", jobID, "error", err)
			}
			return
		}

		status, err := store.MarkFailed(ctx, jobID, runErr.Error())
		if err != nil {
			logger.Error("durable job failure update failed", "job_id", jobID, "error", err)
			return
		}
		if status == StatusDeadLetter {
			logger.Error("durable job dead-lettered", "job_id", jobID, "error", runErr)
			return
		}
		delay := retryDelay(claimed.RetryCount)
		logger.Warn("durable job failed; retrying", "job_id", jobID, "delay", delay.String(), "error", runErr)
		select {
		case <-time.After(delay):
		case <-ctx.Done():
			return
		}
		if err := store.ResetForRetry(ctx, jobID); err != nil {
			logger.Error("durable job retry reset failed", "job_id", jobID, "error", err)
			return
		}
	}
}

func Public(job Job) map[string]any {
	return map[string]any{
		"job_id":           job.ID,
		"job_type":         job.Type,
		"status":           job.Status,
		"retry_count":      job.RetryCount,
		"max_attempts":     job.MaxAttempts,
		"timeout_seconds":  job.TimeoutSeconds,
		"error":            job.Error,
		"error_state":      job.ErrorState,
		"result":           job.Result,
		"created_at":       job.CreatedAt,
		"updated_at":       job.UpdatedAt,
		"started_at":       job.StartedAt,
		"completed_at":     job.CompletedAt,
		"dead_lettered_at": job.DeadLetteredAt,
	}
}

func IdempotencyKey(jobType string, fields any) string {
	return stableHash(map[string]any{"job_type": jobType, "fields": fields})
}

func NewJob(input EnqueueInput) Job {
	key := IdempotencyKey(input.JobType, input.IdempotencyFields)
	timeout := input.TimeoutSeconds
	if timeout <= 0 {
		timeout = 120
	}
	maxAttempts := input.MaxAttempts
	if maxAttempts <= 0 {
		maxAttempts = 3
	}
	now := time.Now().UTC()
	return Job{
		ID:             input.JobType + ":" + key,
		Type:           input.JobType,
		IdempotencyKey: key,
		UserID:         input.UserID,
		Payload:        Redact(toMap(input.Payload)),
		Status:         StatusQueued,
		RetryCount:     0,
		MaxAttempts:    maxAttempts,
		TimeoutSeconds: timeout,
		CreatedAt:      now,
		UpdatedAt:      now,
	}
}

type MemoryStore struct {
	mu      sync.Mutex
	jobs    map[string]Job
	byIdemp map[string]string
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		jobs:    map[string]Job{},
		byIdemp: map[string]string{},
	}
}

func (s *MemoryStore) Enqueue(_ context.Context, input EnqueueInput) (Job, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	job := NewJob(input)
	idempKey := job.Type + ":" + job.IdempotencyKey
	if existingID, ok := s.byIdemp[idempKey]; ok {
		return s.jobs[existingID], false, nil
	}
	s.jobs[job.ID] = job
	s.byIdemp[idempKey] = job.ID
	return job, true, nil
}

func (s *MemoryStore) Get(_ context.Context, jobID string) (Job, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	job, ok := s.jobs[jobID]
	return job, ok, nil
}

func (s *MemoryStore) ClaimForRun(_ context.Context, jobID string) (Job, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	job, ok := s.jobs[jobID]
	if !ok || job.Status != StatusQueued {
		return Job{}, false, nil
	}
	now := time.Now().UTC()
	job.Status = StatusRunning
	job.StartedAt = &now
	job.UpdatedAt = now
	job.Error = ""
	job.ErrorState = nil
	job.RetryCount++
	s.jobs[jobID] = job
	return job, true, nil
}

func (s *MemoryStore) MarkSucceeded(_ context.Context, jobID string, result any) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	job, ok := s.jobs[jobID]
	if !ok {
		return errors.New("job not found")
	}
	now := time.Now().UTC()
	job.Status = StatusSucceeded
	job.Result = result
	job.Error = ""
	job.ErrorState = nil
	job.CompletedAt = &now
	job.UpdatedAt = now
	s.jobs[jobID] = job
	return nil
}

func (s *MemoryStore) MarkFailed(_ context.Context, jobID string, message string) (Status, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	job, ok := s.jobs[jobID]
	if !ok {
		return "", errors.New("job not found")
	}
	now := time.Now().UTC()
	status := StatusFailed
	if job.RetryCount >= job.MaxAttempts {
		status = StatusDeadLetter
		job.DeadLetteredAt = &now
		job.CompletedAt = &now
	}
	job.Status = status
	job.Error = message
	job.ErrorState = map[string]any{
		"message":   message,
		"failed_at": now,
		"attempt":   job.RetryCount,
	}
	job.UpdatedAt = now
	s.jobs[jobID] = job
	return status, nil
}

func (s *MemoryStore) ResetForRetry(_ context.Context, jobID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	job, ok := s.jobs[jobID]
	if !ok {
		return errors.New("job not found")
	}
	job.Status = StatusQueued
	job.UpdatedAt = time.Now().UTC()
	s.jobs[jobID] = job
	return nil
}

func Redact(payload map[string]any) map[string]any {
	out := map[string]any{}
	for key, value := range payload {
		lowered := strings.ToLower(key)
		if strings.Contains(lowered, "authorization") ||
			strings.Contains(lowered, "cookie") ||
			strings.Contains(lowered, "password") ||
			strings.Contains(lowered, "secret") ||
			strings.Contains(lowered, "token") ||
			strings.Contains(lowered, "pat") {
			out[key] = "[redacted]"
			continue
		}
		if nested, ok := value.(map[string]any); ok {
			out[key] = Redact(nested)
			continue
		}
		if items, ok := value.([]any); ok {
			redacted := make([]any, 0, len(items))
			for _, item := range items {
				if nested, ok := item.(map[string]any); ok {
					redacted = append(redacted, Redact(nested))
				} else {
					redacted = append(redacted, item)
				}
			}
			out[key] = redacted
			continue
		}
		out[key] = value
	}
	return out
}

func stableHash(value any) string {
	encoded, _ := json.Marshal(value)
	sum := sha256.Sum256(encoded)
	return hex.EncodeToString(sum[:])
}

func toMap(value any) map[string]any {
	if value == nil {
		return map[string]any{}
	}
	if m, ok := value.(map[string]any); ok {
		return m
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		return map[string]any{}
	}
	var out map[string]any
	if err := json.Unmarshal(encoded, &out); err != nil {
		return map[string]any{}
	}
	return out
}

func retryDelay(retryCount int) time.Duration {
	if retryCount < 1 {
		retryCount = 1
	}
	seconds := math.Pow(2, float64(retryCount-1))
	if seconds > 30 {
		seconds = 30
	}
	return time.Duration(seconds * float64(time.Second))
}

func SortedKeys(values map[string]any) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
