# Architecture

HomHive is a household evidence-processing and decision system, not a direct appliance/robot controller.

## Data flow

```text
Authenticated image -> Private media store -> Durable scan job
                                  |
                                  v
                    Nebius multimodal perception
                                  |
                                  v
                   OpenAI + Anthropic image review
                                  |
                                  v
                     Independently checked claims
                                  |
                 +----------------+----------------+
                 |                |                |
                 v                v                v
        Room continuity    Persistent objects   Task discovery
                 |                |                |
                 +----------------+----------------+
                                  |
                                  v
                       PostgreSQL history
                                  |
                         +--------+--------+
                         |                 |
                         v                 v
                 Tavily research     Feasibility rules
                         |                 |
                         +--------+--------+
                                  |
                                  v
                          Nemotron advice
                                  |
                                  v
                      Consumer decision interface
```

The vision reviewer, task proposer, research provider, and planner have separate roles. A visually supported observation does not automatically establish room identity, object species, task necessity, task completion, or executability.

## Main components

| Component | Code | Responsibility |
| --- | --- | --- |
| API | `backend/app/api/` | Authentication, household endpoints, scan and decision routes |
| Vision | `backend/app/vision/` | Open-world perception, independent review, room comparison, worker |
| Household objects | `backend/app/services/autonomous_objects.py` | Stable object identities and evidence-linked object records |
| Task lifecycle | `backend/app/services/autonomous_lifecycle.py` | Persistent tasks, state transitions, and progress evidence |
| Coordination | `backend/app/coordination/` | Feasibility, Nemotron advice, post-scan orchestration |
| Research | `backend/app/research/` | Tavily requests, normalization, and cached evidence |
| Storage | `backend/app/db/`, `backend/alembic/` | PostgreSQL, SQLAlchemy and schema migrations |
| Consumer client | `frontend/app/`, `frontend/lib/` | Scan, Spaces, Objects, Tasks, and Automation views |

## Identity and uncertainty

A **room category** (such as Kitchen) is not a **physical room identifier**. Two kitchens in one household are not the same space merely because the classifier returns the same category. A close-up object can persist without being assigned to a room. Uncertain object species and unverified locations should remain explicitly unknown.

Observations record evidence; household state summarizes history; tasks represent actionable work; planning chooses among feasible tasks. These cannot be collapsed into a single model response without losing auditability.

## Research and planning boundaries

Tavily provides third-party evidence rather than a diagnosis or guaranteed household fact. Source links must be associated with the relevant task or object before the interface can claim research-backed guidance. NVIDIA Nemotron makes a recommendation from the currently eligible task set, while deterministic logic blocks infeasible selections. A no-executable-task response can be legitimate.

## Trust and deployment

API credentials and signing secrets stay server-side. Images are stored privately behind household access controls, while demo photos are public static assets. The provided local Docker demonstration is not hardened for public internet exposure. Device control, continuous camera streams, production identity administration, and external calendar sync are out of scope for the current demo.
