from typing import Protocol, runtime_checkable

from app.models import Observation


@runtime_checkable
class ObservationStorage(Protocol):
    def add_observation(self, household_id: str, observation: Observation) -> Observation: ...

    def find_observation(self, household_id: str, observation_id: str) -> Observation | None: ...

    def list_observations(self, household_id: str) -> list[Observation]: ...
