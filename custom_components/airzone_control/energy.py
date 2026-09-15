"""Helpers for Airzone Cloud energy interval readings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

ENERGY_INTERVAL_COUNTERS: tuple[tuple[str, str, str], ...] = (
    ("energy_hour_latest", "energy_hour_total", "energy_hour_latest_date"),
    ("energy_acc", "energy_acc_total", "energy_period_end_dt"),
    ("energy_ret", "energy_ret_total", "energy_period_end_dt"),
    ("energy1_acc", "energy1_acc_total", "energy1_period_end_dt"),
    ("energy1_ret", "energy1_ret_total", "energy1_period_end_dt"),
    ("energy2_acc", "energy2_acc_total", "energy2_period_end_dt"),
    ("energy2_ret", "energy2_ret_total", "energy2_period_end_dt"),
    ("energy3_acc", "energy3_acc_total", "energy3_period_end_dt"),
    ("energy3_ret", "energy3_ret_total", "energy3_period_end_dt"),
)


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def update_interval_totals(
    stored_meters: dict[str, Any], meter_id: str, meter: dict[str, Any]
) -> bool:
    """Add each completed interval exactly once and expose persistent totals.

    Airzone's ``energy*_acc`` and ``energy*_ret`` fields are values for the
    interval ending at ``energy*_period_end_dt``. They are not lifetime
    counters, despite their names.
    """
    changed = False
    stored_meter = stored_meters.setdefault(str(meter_id), {})

    for interval_key, total_key, period_key in ENERGY_INTERVAL_COUNTERS:
        raw_value = meter.get(interval_key)
        raw_period = meter.get(period_key)
        try:
            interval_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        period = _timestamp(raw_period)
        if interval_value < 0 or period is None:
            continue

        record = stored_meter.get(interval_key)
        if not isinstance(record, dict):
            record = None

        if record is None:
            total = interval_value
            stored_meter[interval_key] = {
                "period": raw_period,
                "total": round(total, 6),
            }
            changed = True
        else:
            try:
                total = max(float(record.get("total", 0)), 0.0)
            except (TypeError, ValueError):
                total = 0.0
            previous_period = _timestamp(record.get("period"))
            if previous_period is None or period > previous_period:
                total = round(total + interval_value, 6)
                stored_meter[interval_key] = {
                    "period": raw_period,
                    "total": total,
                }
                changed = True

        meter[total_key] = round(total, 6)

    return changed
