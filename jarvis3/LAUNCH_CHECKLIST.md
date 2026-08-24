# Jarvis 3 launch gate

Do not migrate legacy features until every Core Gate item passes.

## Core Gate
- [ ] GitHub Jarvis 3 CI is green.
- [ ] Separate Render `jarvis-staging` service builds from `jarvis-3-clean-rebuild`.
- [ ] `/health` returns HTTP 200 and version 3.x.
- [ ] `/ready` reports all checks true.
- [ ] Wrong owner password is rejected.
- [ ] Correct owner password creates an authenticated session.
- [ ] Authenticated `/api/status` works.
- [ ] Text chat returns a real OpenAI response.
- [ ] Restart the Render service; login still works.
- [ ] Restart the Render service; database persists.
- [ ] Deploy the same commit again; service remains healthy.

## Feature Gate 2 — Voice
- [ ] Browser microphone permission and speech recognition have clear states.
- [ ] TTS endpoint works with configured British male voice.
- [ ] Voice failure never prevents text chat.

## Feature Gate 3 — Agent execution
- [ ] Objective state machine is separate from chat.
- [ ] Every mutation records evidence.
- [ ] Completion requires verification.
- [ ] Approval gates cover sensitive/destructive actions.

## Feature Gate 4 — Integrations
Migrate one integration at a time. Each must have its own health test and must not prevent Jarvis from booting if unavailable.

## Feature Gate 5 — Self-engineering
- [ ] Candidate branch only; never direct-to-production writes.
- [ ] CI required before staging.
- [ ] Staging verification required before promotion.
- [ ] Owner approval required for production.
- [ ] Production verification and rollback path tested.

Production cutover happens only after all required gates pass on staging.
