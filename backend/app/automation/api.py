"""Authenticated in-app suggestions and explicit manual presence consent."""
from collections.abc import Mapping
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker
from app.api.household_auth import build_household_authorizer
from app.automation.context import (PresenceState, current_presence, update_presence,
                                    household_feasibility)
from app.automation.notifications import list_notifications


class PresenceUpdate(BaseModel):
    state: PresenceState
    consent: bool
    reliability: float = Field(default=1, ge=0, le=1)
    ttl_minutes: int = Field(default=60, ge=1, le=1440)


def build_automation_router(sessions: sessionmaker[Session],
                            tokens: Mapping[str, str]) -> APIRouter:
    router = APIRouter(prefix='/households/{household_id}', tags=['automation'])
    authorize = build_household_authorizer(tokens)

    @router.get('/notifications')
    def notifications(household_id: str, _: None = Depends(authorize)):
        presence = current_presence(sessions, household_id)['state']
        return [{**item, 'feasibility': household_feasibility(presence).value,
                'recommended_time': None} for item in list_notifications(sessions, household_id)]

    @router.get('/presence')
    def get_presence(household_id: str, _: None = Depends(authorize)):
        return current_presence(sessions, household_id)

    @router.post('/presence')
    def set_presence(household_id: str, body: PresenceUpdate,
                    _: None = Depends(authorize)):
        return update_presence(sessions, household_id, body.state,
                               body.reliability, body.ttl_minutes, body.consent)

    @router.post('/presence/revoke')
    def revoke_presence(household_id: str, _: None = Depends(authorize)):
        return update_presence(sessions, household_id, PresenceState.UNKNOWN, 0, 1, False)

    return router
