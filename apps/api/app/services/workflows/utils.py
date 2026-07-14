from datetime import UTC, datetime
from time import perf_counter
from typing import Any


def _jsonish(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _now() -> datetime:
    return datetime.now(UTC)
