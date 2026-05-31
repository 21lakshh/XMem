from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, Query, Request

from src.api.dependencies import enforce_rate_limit, require_api_key
from src.api.routes import memory as memory_v1
from src.api.routes.v2.shared import _error, _wrap, elapsed_ms, job_status_data, read_user_job
from src.api.routes.v2.temporal_client import cancel_job_workflow, start_job_workflow
from src.api.schemas import APIResponse
from src.jobs.durable import DEAD_LETTER, QUEUED, RUNNING, get_default_job_store

router = APIRouter(
    prefix="/v2/jobs",
    tags=["jobs-v2"],
    dependencies=[Depends(enforce_rate_limit)],
)


@router.get("/{job_id}/status", response_model=APIResponse, summary="Poll a durable v2 job")
async def get_job_status(job_id: str, request: Request, user: dict = Depends(require_api_key)):
    start = time.perf_counter()
    job = await read_user_job(job_id, memory_v1._current_user_id(user))
    if not job:
        return _error(request, "Job not found.", 404, elapsed_ms(start))
    return _wrap(request, job_status_data(job), elapsed_ms(start))


@router.get("/dead-letter", response_model=APIResponse, summary="List your dead-lettered v2 jobs")
async def list_dead_letter_jobs(
    request: Request,
    user: dict = Depends(require_api_key),
    limit: int = Query(default=50, ge=1, le=200),
):
    start = time.perf_counter()
    user_id = memory_v1._current_user_id(user)
    jobs = await asyncio.to_thread(
        get_default_job_store().list_by_status,
        DEAD_LETTER,
        user_id,
        limit,
    )
    return _wrap(request, [job_status_data(job) for job in jobs], elapsed_ms(start))


@router.post("/{job_id}/retry", response_model=APIResponse, summary="Retry a failed or dead-lettered v2 job")
async def retry_job(job_id: str, request: Request, user: dict = Depends(require_api_key)):
    start = time.perf_counter()
    user_id = memory_v1._current_user_id(user)
    job = await read_user_job(job_id, user_id)
    if not job:
        return _error(request, "Job not found.", 404, elapsed_ms(start))
    if job.get("status") not in {"failed", "dead_letter", "cancelled"}:
        return _error(request, "Only failed, dead-lettered, or cancelled jobs can be retried.", 409, elapsed_ms(start))

    await asyncio.to_thread(get_default_job_store().reset_for_retry, job_id, True)
    job = await asyncio.to_thread(get_default_job_store().get, job_id)
    try:
        await start_job_workflow(job)
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        await asyncio.to_thread(get_default_job_store().mark_failed, job_id, error)
        return _error(request, f"Retry failed to start workflow: {error}", 503, elapsed_ms(start))
    job = await asyncio.to_thread(get_default_job_store().get, job_id)
    return _wrap(request, job_status_data(job), elapsed_ms(start))


@router.post("/{job_id}/cancel", response_model=APIResponse, summary="Cancel a running v2 job")
async def cancel_job(job_id: str, request: Request, user: dict = Depends(require_api_key)):
    start = time.perf_counter()
    user_id = memory_v1._current_user_id(user)
    job = await read_user_job(job_id, user_id)
    if not job:
        return _error(request, "Job not found.", 404, elapsed_ms(start))
    if job.get("status") not in {QUEUED, RUNNING}:
        return _error(request, "Only queued or running jobs can be cancelled.", 409, elapsed_ms(start))
    await cancel_job_workflow(job)
    await asyncio.to_thread(get_default_job_store().mark_cancelled, job_id)
    job = await asyncio.to_thread(get_default_job_store().get, job_id)
    return _wrap(request, job_status_data(job), elapsed_ms(start))
