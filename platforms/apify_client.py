from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from apify_client import ApifyClient as _ApifyClient
        from config.settings import APIFY_API_TOKEN
        if not APIFY_API_TOKEN:
            raise RuntimeError("APIFY_API_TOKEN is not set.")
        _client = _ApifyClient(APIFY_API_TOKEN)
    return _client


def run_actor(
    actor_id: str,
    run_input: dict,
    timeout_secs: int = 600,
) -> tuple[list[dict], dict]:
    """
    Runs Apify actor using .call() (blocking with timeout).
    Returns (items, run_metadata) where run_metadata has cost info.
    Raises RuntimeError on FAILED/ABORTED status.
    """
    client = _get_client()
    logger.info("Running Apify actor %s (timeout=%ss)", actor_id, timeout_secs)

    actor_run = client.actor(actor_id).call(
        run_input=run_input,
        timeout_secs=timeout_secs,
    )

    status = actor_run.get("status", "")
    if status in ("FAILED", "ABORTED", "TIMED-OUT"):
        raise RuntimeError(
            f"Apify actor {actor_id} finished with status={status}. "
            f"Run ID: {actor_run.get('id')}"
        )

    dataset_id = actor_run.get("defaultDatasetId")
    items: list[dict] = []
    if dataset_id:
        dataset_items = client.dataset(dataset_id).iterate_items()
        items = list(dataset_items)

    run_metadata: dict[str, Any] = {
        "run_id": actor_run.get("id"),
        "status": status,
        "dataset_id": dataset_id,
        "stats": actor_run.get("stats", {}),
        "cost_usd": float(actor_run.get("usageTotalUsd") or 0.0),
    }

    logger.info(
        "Actor %s finished: status=%s items=%d cost_usd=%.4f",
        actor_id, status, len(items), run_metadata["cost_usd"],
    )
    return items, run_metadata


def get_account_usage() -> dict:
    """
    Fetches current billing-cycle usage from /v2/users/me/usage/monthly.
    Returns dict with keys: usage_usd (float), cycle_start (str), cycle_end (str).
    """
    import requests as _requests
    from config.settings import APIFY_API_TOKEN
    if not APIFY_API_TOKEN:
        raise RuntimeError("APIFY_API_TOKEN is not set.")
    r = _requests.get(
        "https://api.apify.com/v2/users/me/usage/monthly",
        params={"token": APIFY_API_TOKEN},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    services = data.get("monthlyServiceUsage", {})
    total = sum(
        v.get("amountAfterVolumeDiscountUsd", 0.0)
        for v in services.values()
    )
    cycle = data.get("usageCycle", {})
    return {
        "usage_usd": round(total, 4),
        "cycle_start": (cycle.get("startAt") or "")[:10],
        "cycle_end": (cycle.get("endAt") or "")[:10],
    }
