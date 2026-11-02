"""Run logs, hashing, and DeepSeek cost accounting."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRICING_SNAPSHOT = "2026-11-02"
DEFAULT_MODEL = "deepseek-flash"

# DeepSeek public list prices in USD per 1M tokens, off-peak, snapshot 2026-11-02.
# Peak hours are 2x. https://api-docs.deepseek.com/quick_start/pricing
PRICING_USD_PER_MTOK = {
    "deepseek-flash": {
        "cache_hit": 0.003,
        "cache_miss": 0.15,
        "output": 0.60,
    },
    "deepseek-v4-pro": {
        "cache_hit": 0.022,
        "cache_miss": 0.66,
        "output": 1.98,
    },
}

# Peak windows are UTC, Monday-Friday. Chinese public holidays are not modeled.
PEAK_HOURS_UTC = ((1, 4), (6, 10))
USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_peak(at: datetime) -> bool:
    """Return True when DeepSeek's peak rate applies at ``at``."""
    if at.tzinfo is None:
        raise ValueError("is_peak requires a timezone-aware datetime")
    at = at.astimezone(timezone.utc)
    return at.weekday() < 5 and any(
        start <= at.hour < end for start, end in PEAK_HOURS_UTC
    )


def usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize OpenAI/DeepSeek usage objects, including extra fields."""
    if usage is None:
        return {}
    if isinstance(usage, dict):
        data = dict(usage)
    elif hasattr(usage, "model_dump"):
        data = usage.model_dump()
    else:
        data = {}
    extra = getattr(usage, "model_extra", None)
    if isinstance(extra, dict):
        data.update(extra)
    return {
        key: int(value)
        for key, value in data.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def add_usage(total: dict[str, int], usage: dict[str, int]) -> None:
    for key in USAGE_KEYS:
        if key in usage:
            total[key] = total.get(key, 0) + usage[key]
    if "total_tokens" not in total:
        total["total_tokens"] = total.get("prompt_tokens", 0) + total.get(
            "completion_tokens", 0
        )


def compute_cost(
    model: str, usage: dict[str, int], at: datetime | None = None
) -> tuple[float, dict[str, Any]]:
    """Return (cost_usd, breakdown) using cache-aware DeepSeek prices."""
    rates = dict(PRICING_USD_PER_MTOK.get(model, PRICING_USD_PER_MTOK[DEFAULT_MODEL]))
    peak = bool(at and is_peak(at))
    if peak:
        rates = {key: value * 2 for key, value in rates.items()}

    cache_hit = max(int(usage.get("prompt_cache_hit_tokens", 0)), 0)
    cache_miss = usage.get("prompt_cache_miss_tokens")
    if cache_miss is None:
        cache_miss = max(int(usage.get("prompt_tokens", 0)) - cache_hit, 0)
    cache_miss = max(int(cache_miss), 0)
    output = max(int(usage.get("completion_tokens", 0)), 0)

    cost = (
        cache_hit * rates["cache_hit"]
        + cache_miss * rates["cache_miss"]
        + output * rates["output"]
    ) / 1_000_000
    return cost, {
        "peak": peak,
        "cache_hit_tokens": cache_hit,
        "cache_miss_tokens": cache_miss,
        "output_tokens": output,
        "rates_usd_per_mtok": rates,
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None
