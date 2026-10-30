"""Read Google Calendar conflicts and constrain household recommendations."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import httpx

GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"


def freebusy_intervals(access_token: str, now: datetime, checked_minutes: int, *, client=None) -> list[tuple[datetime, datetime]]:
    """Read only the primary calendar's busy intervals, without event details."""
    if not isinstance(access_token, str) or not 1 <= len(access_token) <= 4096:
        raise ValueError("A valid Google Calendar access token is required")
    if not 1 <= checked_minutes <= 1440:
        raise ValueError("Invalid calendar check range")
    until = now + timedelta(minutes=checked_minutes)
    payload = {"timeMin": now.isoformat(), "timeMax": until.isoformat(),
               "timeZone": "UTC", "items": [{"id": "primary"}]}
    request = client or httpx.Client(timeout=12, follow_redirects=False)
    try:
        response = request.post(GOOGLE_FREEBUSY_URL,
            headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
            json=payload)
        if response.status_code in (401, 403):
            raise ValueError("Google Calendar authorization expired, lacks permission, or the API is disabled")
        if response.status_code != 200:
            raise ValueError("Google Calendar is temporarily unavailable")
        body = response.json()
    except (httpx.RequestError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("Google Calendar could not be reached") from exc
    finally:
        if client is None:
            request.close()
    calendars = body.get("calendars") if isinstance(body, dict) else None
    primary = calendars.get("primary") if isinstance(calendars, dict) else None
    if not isinstance(primary, dict) or primary.get("errors") or not isinstance(primary.get("busy"), list):
        raise ValueError("Google Calendar did not return valid primary-calendar availability")
    intervals = []
    for entry in primary["busy"]:
        try:
            start = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(entry["end"].replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError("Invalid interval")
            if start < until and end > now:
                intervals.append((start.astimezone(timezone.utc), end.astimezone(timezone.utc)))
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise ValueError("Google Calendar returned an invalid busy interval") from exc
    return sorted(intervals)


def apply_freebusy(plan: dict, intervals: list[tuple[datetime, datetime]], now: datetime,
                   checked_minutes: int) -> dict:
    """Constrain eligible work, never infer actual presence or free time."""
    result = deepcopy(plan)
    now = now.astimezone(timezone.utc)
    pref = max(0, int(plan["preferred_minutes_remaining"]))
    next_busy = next(((start, end) for start, end in intervals if end > now), None)
    busy_now = bool(next_busy and next_busy[0] <= now < next_busy[1])
    time_to_busy = 0 if busy_now else (max(0, int((next_busy[0] - now).total_seconds() // 60)) if next_busy else checked_minutes)
    conflict_free = min(checked_minutes, time_to_busy)
    effective = min(pref, conflict_free)
    result["calendar"] = {
        "connected": True, "source": "google_calendar_primary_freebusy",
        "busy_now": busy_now, "conflict_free_minutes": conflict_free,
        "effective_work_minutes": effective,
        "checked_until": (now + timedelta(minutes=checked_minutes)).isoformat(),
        "next_busy_starts_at": next_busy[0].isoformat() if next_busy and not busy_now else None,
        "busy_interval_count": len(intervals),
    }
    for task in result["tasks"]:
        if task["status"] != "NOW":
            continue
        if busy_now:
            task["status"] = "DEFERRED"
            task["reasons"] = ["Google Calendar shows a busy event right now"]
        elif task["duration_max"] is not None and task["duration_max"] > effective:
            task["status"] = "DEFERRED"
            task["reasons"] = ["The task cannot fit before the next calendar event or work-window end"]
        else:
            task["reasons"] = ["No Google Calendar conflict during the task's estimated duration; manual availability confirmed"]
    order = {"NOW": 0, "SOON": 1, "DEFERRED": 2, "BLOCKED": 3}
    result["tasks"].sort(key=lambda task: (order[task["status"]], -task["priority"], task["task_id"]))
    result["groups"] = {state: sum(t["status"] == state for t in result["tasks"]) for state in order}
    result["source_note"] = ("Read-only Google Calendar primary Free/Busy checked. No event conflicts does not "
                             "prove personal availability; manual presence and availability are still required.")
    return result
