# Demo image library

The scan dialog supports choosing a public sample image. Samples were generated from the available HomHive original-scene, base-scene, and controlled-variant archives. The gallery contains 220 indexed entries (153 originals, 32 bases, 35 variants); candidate eligibility and duplicates must be checked against the canonical dataset audit before publication. Do not interpret archive membership as final human approval.

Static gallery files are JPEG derivatives for display and trial analysis. `frontend/public/demo-library/catalog.json` preserves original names and SHA-256 digests. Canonical PNG evaluation assets are not modified or replaced by these derivatives.

Public gallery samples are not private household photos. Selecting one creates a normal File and uses existing authenticated upload/vision APIs; no predetermined task outcomes or mock observations are supplied. Avoid placing confidential or externally licensed images into the public directory.

## Pending product work

This slice does not change household bearer-token authentication. Production user login, password recovery, sessions, household memberships, server-side authorization, persistent room identity, automatic task lifecycle, and research-grounded task estimates require separate schema, migration, access-control, and integration testing.
