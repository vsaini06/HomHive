from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .observation import Observation


class HouseholdState(BaseModel):
    id: str

    observation_history: list[Observation] = Field(default_factory=list)

    current_observations: dict[str, Observation] = Field(
        default_factory=dict
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_observation(self, observation: Observation) -> None:
        self.observation_history.append(observation)

        state_key = observation.state_key()

        self.current_observations[state_key] = observation
        self.updated_at = datetime.now(timezone.utc)