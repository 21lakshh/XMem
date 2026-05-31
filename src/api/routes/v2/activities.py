from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi.encoders import jsonable_encoder

from src.api.dependencies import get_ingest_pipeline
from src.api.routes import memory as memory_v1
from src.jobs.durable import get_default_job_store

try:  # pragma: no cover - no-op fallback keeps imports working without SDK.
    from temporalio import activity
except Exception:  # pragma: no cover
    class _ActivityFallback:
        def defn(self, fn=None, **_kwargs):
            if fn is None:
                return lambda wrapped: wrapped
            return fn

    activity = _ActivityFallback()


def _domain_payload(result: Dict[str, Any], domain: str) -> Dict[str, Any] | None:
    value = memory_v1._build_domain_result(
        result.get(f"{domain}_judge"),
        result.get(f"{domain}_weaver"),
    )
    return value.model_dump() if value else None


@activity.defn
async def mark_job_running_activity(job_id: str) -> None:
    await asyncio.to_thread(get_default_job_store().mark_running, job_id)


@activity.defn
async def mark_job_progress_activity(payload: Dict[str, Any]) -> None:
    await asyncio.to_thread(
        get_default_job_store().update_progress,
        payload["job_id"],
        payload.get("progress") or {},
    )


@activity.defn
async def mark_job_succeeded_activity(payload: Dict[str, Any]) -> None:
    await asyncio.to_thread(
        get_default_job_store().mark_succeeded,
        payload["job_id"],
        payload.get("result") or {},
    )


@activity.defn
async def mark_job_dead_letter_activity(payload: Dict[str, Any]) -> None:
    await asyncio.to_thread(
        get_default_job_store().mark_dead_letter,
        payload["job_id"],
        payload.get("error") or "Workflow failed",
    )


@activity.defn
async def memory_classify_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    pipeline = get_ingest_pipeline()
    state = {
        "user_query": payload.get("user_query", ""),
        "image_url": payload.get("image_url", ""),
    }
    result = await pipeline._node_classify(state)
    classification = result.get("classification_result")
    return {
        "model": memory_v1._model_name(pipeline.model),
        "classification": jsonable_encoder(
            getattr(classification, "classifications", []) or []
        ),
    }


@activity.defn
async def memory_domain_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    pipeline = get_ingest_pipeline()
    domain = payload["domain"]
    user_id = payload["user_id"]

    if domain == "profile":
        result = await pipeline._node_extract_profile({
            "profile_queries": payload.get("queries", []),
            "user_id": user_id,
        })
        return {"domain": domain, "result": _domain_payload(result, "profile")}

    if domain == "temporal":
        result = await pipeline._node_extract_temporal({
            "temporal_queries": payload.get("queries", []),
            "session_datetime": payload.get("session_datetime", ""),
            "user_id": user_id,
        })
        return {"domain": domain, "result": _domain_payload(result, "temporal")}

    if domain == "summary":
        result = await pipeline._node_extract_summary({
            "user_query": payload.get("user_query", ""),
            "agent_response": payload.get("agent_response", ""),
            "user_id": user_id,
        })
        return {"domain": domain, "result": _domain_payload(result, "summary")}

    if domain == "image":
        result = await pipeline._node_extract_image({
            "classifier_output": payload.get("classifier_output", ""),
            "image_url": payload.get("image_url", ""),
            "user_id": user_id,
        })
        return {"domain": domain, "result": _domain_payload(result, "image")}

    if domain == "code":
        result = await pipeline._node_extract_code({
            "code_queries": payload.get("queries", []),
            "user_id": user_id,
        })
        return {"domain": domain, "stored": bool(result)}

    if domain == "snippet":
        result = await pipeline._node_extract_snippet({
            "code_queries": payload.get("queries", []),
            "user_id": user_id,
        })
        return {"domain": domain, "stored": bool(result)}

    raise ValueError(f"Unsupported memory domain activity: {domain}")


@activity.defn
async def memory_run_pipeline_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await memory_v1._run_ingest_payload(payload, payload["user_id"])


@activity.defn
async def memory_batch_ingest_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    results = []
    for item in payload["items"]:
        results.append(await memory_v1._run_ingest_payload(item, item["user_id"]))
    return {"results": results}


@activity.defn
async def memory_scrape_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await memory_v1._run_scrape_payload(payload)


@activity.defn
async def scanner_scan_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    from src.api.routes import scanner as scanner_v1
    from src.api.routes.v2.secrets import resolve_scanner_pat

    pat = await asyncio.to_thread(resolve_scanner_pat, payload.get("github_credential_ref") or "")
    await scanner_v1._run_scan_job(
        payload["scanner_job_id"],
        payload["username"],
        payload["org"],
        payload["repo"],
        payload["github_url"],
        payload.get("branch") or "main",
        pat,
        bool(payload.get("force_full", True)),
    )
    job = scanner_v1._get_code_store().get_scanner_job(payload["scanner_job_id"]) or {}
    return {
        "scanner_job_id": payload["scanner_job_id"],
        "phase1_status": job.get("phase1_status"),
        "phase2_status": job.get("phase2_status"),
    }


@activity.defn
async def scanner_phase2_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    from src.api.routes import scanner as scanner_v1

    await scanner_v1._run_phase2_job(
        payload["scanner_job_id"],
        payload["username"],
        payload["org"],
        payload["repo"],
        payload["github_url"],
        payload.get("branch") or "main",
    )
    job = scanner_v1._get_code_store().get_scanner_job(payload["scanner_job_id"]) or {}
    return {
        "scanner_job_id": payload["scanner_job_id"],
        "phase1_status": job.get("phase1_status"),
        "phase2_status": job.get("phase2_status"),
    }


ALL_ACTIVITIES = [
    mark_job_running_activity,
    mark_job_progress_activity,
    mark_job_succeeded_activity,
    mark_job_dead_letter_activity,
    memory_classify_activity,
    memory_domain_activity,
    memory_run_pipeline_activity,
    memory_batch_ingest_activity,
    memory_scrape_activity,
    scanner_scan_activity,
    scanner_phase2_activity,
]
