"""Authorized context controls and deterministic task coordination."""
from collections.abc import Mapping
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker
from app.api.household_auth import build_household_authorizer
from .service import coordination_plan, set_availability, set_quiet_hours


class CalendarTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(min_length=1, max_length=4096)


class AvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    state: str
    ttl_minutes: int = Field(default=60, ge=1, le=240)


class QuietHoursRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    start_time: str
    end_time: str
    timezone: str | None = None


def build_coordination_router(sessions: sessionmaker[Session], tokens: Mapping[str, str]) -> APIRouter:
    router = APIRouter(prefix='/households/{household_id}/coordination', tags=['coordination'])
    authorize = build_household_authorizer(tokens)

    @router.get('')
    def get_plan(household_id: str, _: None = Depends(authorize)):
        return coordination_plan(sessions, household_id)

    @router.post('/nemotron-advice')
    def nemotron_advice(household_id: str, _: None = Depends(authorize)):
        from .nemotron import advise_coordination
        plan = coordination_plan(sessions, household_id)
        try:
            return advise_coordination(plan)
        except Exception as exc:
            raise HTTPException(status_code=503,
                detail="Nemotron advice is unavailable; the safe household plan is unchanged") from exc

    def calendar_aware_plan(household_id: str, token: str) -> dict:
        from .google_calendar import freebusy_intervals, apply_freebusy
        now = datetime.now(timezone.utc)
        plan = coordination_plan(sessions, household_id, now=now)
        checked_minutes = max(60, min(1440, plan['preferred_minutes_remaining']))
        try:
            busy = freebusy_intervals(token, now, checked_minutes)
        except ValueError as exc:
            raise HTTPException(503, str(exc)) from None
        return apply_freebusy(plan, busy, now, checked_minutes)

    @router.post('/google-calendar/plan')
    def google_calendar_plan(household_id: str, request: CalendarTokenRequest,
                             _: None = Depends(authorize)):
        return calendar_aware_plan(household_id, request.access_token)

    @router.post('/google-calendar/nemotron-advice')
    def google_calendar_advice(household_id: str, request: CalendarTokenRequest,
                               _: None = Depends(authorize)):
        from .nemotron import advise_coordination
        plan = calendar_aware_plan(household_id, request.access_token)
        try:
            return advise_coordination(plan)
        except Exception as exc:
            raise HTTPException(status_code=503,
                detail="Nemotron advice is unavailable; no household tasks were changed") from exc

    @router.put('/availability')
    def update_availability(household_id: str, request: AvailabilityRequest,
                            _: None = Depends(authorize)):
        try:
            set_availability(sessions, household_id, request.state, ttl_minutes=request.ttl_minutes)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return coordination_plan(sessions, household_id)

    @router.put('/quiet-hours')
    def update_quiet(household_id: str, request: QuietHoursRequest,
                     _: None = Depends(authorize)):
        try:
            set_quiet_hours(sessions, household_id, request.enabled,
                            request.start_time, request.end_time, timezone_name=request.timezone)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return coordination_plan(sessions, household_id)

    return router
