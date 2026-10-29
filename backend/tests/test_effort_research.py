from types import SimpleNamespace

from app.research.models import ResearchEvidence, ResearchPurpose, ResearchRequest, ResearchResult
from app.services.effort_research import ground_action_effort, reported_minutes
from app.services.open_world_planning import ActionProposal, EffortEstimate


def action():
    return ActionProposal(action_id='a1', title='Organize closet floor',
        action='Sort the visible belongings on the closet floor',
        supporting_evidence_ids=['e1'],
        verification_criteria='The floor is clear of the loose items')


class Provider:
    def __init__(self, sources):
        self.sources = sources
        self.calls = 0

    def search(self, request):
        self.calls += 1
        assert request.purpose == ResearchPurpose.HOUSEHOLD_CONTEXT
        return SimpleNamespace(evidence=[SimpleNamespace(url=url, content=content)
                                         for url, content in self.sources])


def test_two_distinct_published_sources_required_for_duration():
    provider = Provider([
        ('https://example.org/duration', 'Allow 20 minutes to organize a closet floor.'),
        ('https://another.org/tips', 'Organizing a closet floor usually takes 30 minutes.'),
    ])
    result = ground_action_effort(action(), provider=provider)
    assert provider.calls == 1
    assert result.estimated_effort.minimum_minutes == 20
    assert result.estimated_effort.maximum_minutes == 30
    assert result.estimated_effort.externally_verified
    assert len(result.estimated_effort.source_urls) == 2


def test_one_domain_cannot_ground_effort():
    provider = Provider([
        ('https://example.org/one', 'Allow 20 minutes to organize the closet.'),
        ('https://example.org/two', 'Usually takes 30 minutes.'),
    ])
    assert ground_action_effort(action(), provider=provider).estimated_effort is None


def test_research_failure_does_not_reject_approved_action():
    class BrokenProvider:
        def search(self, request):
            raise ConnectionError('network unavailable')
    assert ground_action_effort(action(), provider=BrokenProvider()).estimated_effort is None


def test_untrusted_model_duration_cannot_be_accepted_without_sources():
    candidate = action().model_copy(update={'estimated_effort': EffortEstimate(
        minimum_minutes=10, maximum_minutes=15, rationale='Estimated from visual evidence', evidence_ids=['e1'])})
    assert ground_action_effort(candidate, provider=Provider([])).estimated_effort is None


def test_hazardous_actions_skip_external_research():
    candidate = action().model_copy(update={'hazard_or_professional_help': True})
    provider = Provider([])
    assert ground_action_effort(candidate, provider=provider).estimated_effort is None
    assert provider.calls == 0


def test_time_parser_handles_minutes_and_hours():
    assert reported_minutes('Allow 25 minutes to complete the process.') == 25
    assert reported_minutes('The process takes about 1 to 2 hours.') == 90


def test_published_source_models_accept_valid_research_contract():
    request = ResearchRequest(query='closet organization time', purpose=ResearchPurpose.HOUSEHOLD_CONTEXT)
    result = ResearchResult(query=request.query, purpose=request.purpose,
        evidence=[ResearchEvidence(title='Closet organization time',
                                   url='https://example.org/duration',
                                   content='Allow 20 minutes to organize a closet floor.')])
    assert result.evidence[0].content.startswith('Allow 20')


def test_schema_errors_record_field_names_not_sensitive_values(caplog):
    from pydantic import BaseModel, Field
    class BadResearch(BaseModel):
        amount: int = Field(ge=1)

    class BadProvider:
        def search(self, request):
            BadResearch(amount=0)

    result = ground_action_effort(action(), provider=BadProvider())
    assert result.estimated_effort is None
    assert 'amount:greater_than_equal' in caplog.text
    assert 'input_value' not in caplog.text


def test_unrelated_task_durations_are_not_trusted_as_research():
    provider = Provider([
        ('https://example.org/closet', 'Allow 20 minutes to organize a closet floor.'),
        ('https://another.org/unrelated', 'Painting a bedroom usually takes 30 minutes.'),
    ])
    assert ground_action_effort(action(), provider=provider).estimated_effort is None
