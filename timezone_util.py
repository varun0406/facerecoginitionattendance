"""
Attendance wall-clock times in India Standard Time (IST).

New punches use datetime.now(Asia/Kolkata). List views add *_display fields;
optional ATTENDANCE_LEGACY_STORED_AS_UTC treats existing DB strings as UTC and
converts them to IST for display only.
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo(os.environ.get("DISPLAY_TIMEZONE", "Asia/Kolkata"))
UTC = ZoneInfo("UTC")


def now_attendance_datetime() -> datetime:
    """Current moment in configured attendance zone (default IST)."""
    return datetime.now(IST)


def now_attendance_date_str() -> str:
    return now_attendance_datetime().strftime("%d/%m/%Y")


def now_attendance_time_str() -> str:
    return now_attendance_datetime().strftime("%H:%M:%S")


def _parse_date_ddmmyyyy(s: str) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_hms(s: str) -> tuple[int, int, int] | None:
    if not s or not isinstance(s, str):
        return None
    parts = s.strip().split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        sec = int(parts[2]) if len(parts) > 2 else 0
        return h, m, sec
    except (ValueError, IndexError):
        return None


def _combine_local(dt_date: datetime, hms: str, tz) -> datetime | None:
    t = _parse_hms(hms)
    if not t:
        return None
    return datetime(
        dt_date.year,
        dt_date.month,
        dt_date.day,
        t[0],
        t[1],
        t[2],
        tzinfo=tz,
    )


def _format_ist_local(dt: datetime) -> tuple[str, str]:
    """Return (dd/mm/yyyy, HH:MM:SS) in IST as naive wall strings."""
    loc = dt.astimezone(IST)
    return loc.strftime("%d/%m/%Y"), loc.strftime("%H:%M:%S")


def enrich_attendance_display(rec: dict) -> dict:
    """
    Add date_display, start_time_display, end_time_display (always IST wall clock).

    By default stored date/time are treated as already IST (typical for Indian ops).
    Set ATTENDANCE_LEGACY_STORED_AS_UTC=1 if old rows were written in UTC wall clock.
    """
    out = dict(rec)
    legacy = os.environ.get("ATTENDANCE_LEGACY_STORED_AS_UTC", "").lower() in (
        "1",
        "true",
        "yes",
    )
    date_s = out.get("date") or ""
    start_s = out.get("start_time") or out.get("time") or ""
    end_s = out.get("end_time") or ""

    if not legacy:
        out["date_display"] = date_s or None
        out["start_time_display"] = start_s or None
        out["end_time_display"] = end_s or None
        return out

    base = _parse_date_ddmmyyyy(date_s)
    if not base:
        out["date_display"] = date_s or None
        out["start_time_display"] = start_s or None
        out["end_time_display"] = end_s or None
        return out

    if start_s:
        aware = _combine_local(base, start_s, UTC)
        if aware:
            dds, sts = _format_ist_local(aware)
            out["date_display"] = dds
            out["start_time_display"] = sts
        else:
            out["date_display"] = date_s
            out["start_time_display"] = start_s
    else:
        out["date_display"] = date_s
        out["start_time_display"] = None

    if end_s:
        aware_e = _combine_local(base, end_s, UTC)
        if aware_e:
            _, ets = _format_ist_local(aware_e)
            out["end_time_display"] = ets
        else:
            out["end_time_display"] = end_s
    else:
        out["end_time_display"] = None

    return out
