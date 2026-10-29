# Architecture decisions

These decisions keep the evidence-to-action pipeline auditable.

1. **Observation != task.** Visible evidence can exist without creating work. Task identity and lifecycle are independent from evidence identity.
2. **History != current state.** Store original events and reconstruct a current view without overwriting the supporting record.
3. **Room category != room identity.** Two rooms can share the same category; the system must establish physical continuity before joining histories.
4. **Object identity != location.** A close-up plant can be tracked without a verified room, and user-selected locations must remain explicit.
5. **Presence != visibility.** An occluded object or an object outside the frame is not necessarily absent from the home.
6. **Unknown remains unknown.** Missing confidence, species, duration, or research evidence must not be replaced by invented values.
7. **Progress != proof of physical completion.** A changed image supports visible goal progress only to the extent independently assessed.
8. **Priority != feasibility.** Deterministic constraints filter executable tasks before Nemotron ranks or explains them.
9. **Research is external evidence.** Tavily citations cannot, by themselves, establish diagnoses or rewrite observed facts.
10. **Provider outputs are untrusted until validated.** JSON structure, task IDs, and evidence claims are checked before persistence or recommendation.
11. **Workers preserve durable state.** Failure or restart should not silently lose completed scan evidence or create duplicate tasks.

Implementation history belongs in Git. Current architectural components are described in [architecture.md](architecture.md).
