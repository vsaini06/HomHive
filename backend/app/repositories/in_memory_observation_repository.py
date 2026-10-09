from app.models import Observation


class InMemoryObservationRepository:
    def __init__(self) -> None:
        self._observations: dict[str, dict[str, Observation]] = {}

    def add_observation(self, household_id: str, observation: Observation) -> Observation:
        if not household_id:
            raise ValueError("household_id must not be empty")
        observations = self._observations.setdefault(household_id, {})
        if observation.id in observations:
            raise ValueError(f"Observation already exists: {observation.id}")
        observations[observation.id] = observation.model_copy(deep=True)
        return observations[observation.id].model_copy(deep=True)

    def find_observation(self, household_id: str, observation_id: str) -> Observation | None:
        observation = self._observations.get(household_id, {}).get(observation_id)
        return observation.model_copy(deep=True) if observation is not None else None

    def list_observations(self, household_id: str) -> list[Observation]:
        observations = self._observations.get(household_id, {}).values()
        return [
            observation.model_copy(deep=True)
            for observation in sorted(observations, key=lambda item: (item.timestamp, item.id))
        ]
