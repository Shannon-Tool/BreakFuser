# Handoff: BreakFuser Interactive 3D Pipeline Experience

## Purpose of this handoff

Take over the public interactive BreakFuser experience in `/root/BreakFuser-public`.

The current implementation is functional and heavily tested, but **the user has rejected its visual design repeatedly**. Do not treat this as a small styling task or defend the existing result. The user considers the current presentation unprofessional, childish, and insufficiently representative of the real pipeline.

The next agent should have strong product-design, motion-design, and 3D/data-visualization judgment. The main remaining problem is **design quality and communication**, not basic functionality.

## User’s actual request

Create an amazing, professional, interactive 3D simulation that explains how BreakFuser works to normal users. It must show the live input, output, and processing flow clearly.

The intended product message is:

> **Make any model uncensored by fusing it with an uncensored model.**

The experience must make the real BreakFuser process understandable. Attractive geometry alone is not enough. A diagram that does not communicate actual data flow is a failure.

## What went wrong

Three design directions have been rejected:

1. **Generic glowing model orbs**
   - Abstract smart/uncensored/fusion nodes.
   - Did not show the real acquisition branches, evidence, provenance, or response objects.
   - Looked like a generic landing-page animation.

2. **Larger torus-knot/fusion-reactor version**
   - Enlarged the same decorative concept and added labels.
   - Still did not represent the actual process.
   - User explicitly rejected this as unprofessional and unrelated to the pipeline.

3. **Current process-graph version**
   - Added actual pipeline nodes, request JSON, events, evidence, and response metadata.
   - This is substantially closer to the real implementation and passes 105 tests.
   - **The user still rejects the visual design.** Do not assume that technical correctness makes the presentation acceptable.

Do not respond with another minor CSS revision, larger glow effect, different primitive shape, or claims that the existing version is “cinematic.” The next agent should rethink the art direction and interaction model from first principles.

## Recommended way to proceed

1. **Start with a high-fidelity visual direction, not more feature work.**
   - Produce a polished mockup or small visual prototype before rebuilding everything.
   - Get the user’s reaction to the art direction early.
   - Use a concrete professional reference for composition, typography, motion, and data visualization.

2. **Design around the data story.**
   - A normal user should immediately understand what is sent, where it goes, what happens concurrently, what is recovered, what is synthesized, and what is returned.
   - Every visual element should have a process meaning.
   - Moving particles must represent named payloads, not decoration.

3. **Make input/output/process unmistakable.**
   - Show the request entering the system.
   - Show real-shaped events and evidence changing as the process advances.
   - Show the final response and its metadata arriving at the end.
   - Do not hide the important evidence or response process behind generic explanatory copy.

4. **Do not fabricate live inference.**
   - Current scenarios are curated and labeled `Guided simulation · illustrative data`.
   - If arbitrary prompts are offered, they must call a real configured BreakFuser backend.
   - Never accept an arbitrary prompt and return a canned response as if a model generated it.
   - If actual provider telemetry is required, implement it honestly; the existing HTTP API does not emit progressive stage events.

5. **Preserve the useful engineering, replace whatever visual work is necessary.**
   - Structured scenarios, state transitions, accessibility controls, and tests may be reusable.
   - The current Three.js scene, layout, CSS, and visual assertions are not sacred.
   - Do not preserve tests merely because they pass when they encode a rejected visual model.

## Actual BreakFuser pipeline to represent

Authoritative implementation files:

- `src/breakfuser/fusion/pipeline.py`
- `src/breakfuser/fusion/acquisition.py`
- `src/breakfuser/fusion/evidence.py`
- `src/breakfuser/fusion/domain.py`
- `src/breakfuser/harvest/models.py`
- `src/breakfuser/models.py`
- `src/breakfuser/retrieval/models.py`
- `src/breakfuser/server.py`

The ordinary fusion path does the following:

1. **Original request and triage**
   - Receives OpenAI-shaped `messages[]`.
   - Compresses context where needed.
   - Routes the latest user question into a `ResponseContract`.
   - Selects required atoms, output shape, verification mode, and output budgets.

2. **Parallel acquisition**
   - `SpeculativeAcquisition` uses `asyncio.gather` for three independent branches:
     - `document_retrieval`: curated/HTTPS documents become `SourceDocument` records.
     - `local_draft`: the uncensored model drafts from original context plus contract.
     - `remote_evidence`: the smart model receives sanitized/minimal-context acquisition turns.

3. **Smart-model recovery**
   - The smart branch classifies refusal, hedging, disclaimer, truncation, hallucination suspicion, or out-of-scope behavior.
   - Recovery can include refusal repair, crescendo, continuation, and related strategies.
   - Recovery belongs to the smart-model acquisition path, not the uncensored writer.
   - Ordinary inline acquisition caps harvesting at **two turns**, so an illustrative inline trace must not invent `turn-03`, `turn-04`, etc.

4. **Evidence blackboard**
   - Collects the original question and contract.
   - Holds retrieved documents, local draft, remote `EvidenceSpan` records, harvest results, provenance, branch errors, and timings.
   - Complete remote answers do not bypass uncensored composition.

5. **Uncensored composition**
   - The same uncensored model role used for local drafting performs final synthesis.
   - Uses original context plus the evidence blackboard.
   - Typical composition mode is `targeted_synthesis`.

6. **Verify after**
   - Performs applicable omission, contradiction, modality, schema, and deterministic checks.
   - Can perform bounded repair.
   - Produces verification and fusion metadata.

7. **Final response**
   - Returns an OpenAI-compatible `ChatCompletion`.
   - The request compatibility alias can be `breakfuser`; the response `model` is the configured uncensored model ID, not that alias.
   - `breakfuser` metadata contains trace ID, pipeline stages, artifacts, harvest metrics, provenance, verification, events, and fusion metadata.

The backend’s reported linear stage names are:

```text
document_retrieval
local_draft
remote_evidence
fusion_composition
verify_after
```

The user-facing walkthrough may group these into five high-level phases, but the full graph must show the three acquisition branches and their payloads clearly.

## Data shapes that were corrected recently

Do not regress these fixes:

- `ResponseContract` uses the real backend fields:
  - `domain`
  - `required_atoms`
  - `output_shape`
  - `max_answer_tokens`
  - `completion_directive`
  - `verification_mode`
  - `format_envelope`
  - `remote_output_tokens`

- `SourceDocument` uses:
  - `id`
  - `title`
  - `url`
  - `excerpt`
  - `source_type`
  - `sha256`
  - `retrieved_at`
  - `keywords`

- `EvidenceSpan` uses:
  - `source_id`
  - `origin`
  - `text`
  - `atom_ids`
  - `complete`
  - `salvaged`
  - `tail_anchor`
  - `confidence`

- Recovered facts from one repaired inline turn share `turn-02` while retaining unique atom/span/provenance IDs.

- The blackboard inspector stays pending until the fusion phase, matching the `blackboard_assembled` event.

- The response panel is a concise projection. The full response nests composition data under `breakfuser.fusion` and `local_finish_reason` under `breakfuser`.

A final independent fidelity review was interrupted. Although the identified issues were corrected and tests pass, do not claim a complete independent audit certifies every displayed field.

## Current website file map

Frontend root: `/root/BreakFuser-public/website`

Important files:

- `src/types.ts`
  - Playback state, process nodes, request/contract/document/evidence/event/response types.
- `src/scenarios.ts`
  - Four curated scenarios and structured traces.
  - General question answering, medical information, authorized pentesting, and code generation.
- `src/simulation.ts`
  - Pure play/pause/tick/step/speed/replay/scenario reducer.
- `src/main.ts`
  - Scheduler, scene lifecycle, page lifecycle, motion preferences, clipboard behavior.
- `src/scene/geometry.ts`
  - Current process nodes, routes, visual mappings, and geometry.
- `src/scene/FusionScene.ts`
  - Three.js renderer, camera, projected labels, packet motion, focus, resize, fallback, disposal.
- `src/scene/state.ts`
  - Camera fitting and visibility helpers.
- `src/ui/render.ts`
  - Page, controls, request/events/evidence/response panels, inspectors, and fallback.
- `src/ui/pipeline-fallback.svg`
  - Static real-pipeline fallback.
- `src/styles.css`
  - Current rejected visual presentation.
- `tests/`
  - Vitest and happy-dom unit/DOM tests.
- `e2e/`
  - Playwright desktop/mobile interaction, live-data, resilience, and layout tests.
- `public/THREE-LICENSE.txt`
  - Required redistributed Three.js MIT notice.
- `scripts/check-production.mjs`
  - Checks Pages base paths and exact Three.js license in the artifact.
- `README.md`
  - Setup, test commands, and browser-library notes.

Root additions/changes:

- `assets/interactive-simulation-preview.png`
  - Current preview; the underlying visual direction has been rejected.
- `.github/workflows/website.yml`
  - Node 22 CI and main-only GitHub Pages deployment.
- `README.md` and `docs/index.md`
  - Link the intended public experience.
- Existing uncommitted branding edits in `README.md`, `docs/`, `assets/*.svg`, and `pyproject.toml` must be preserved.

## Run the current implementation

```bash
cd /root/BreakFuser-public/website
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

A Vite server was left running on port `5173` when this handoff was written.

Local URL:

```text
http://127.0.0.1:5173
```

User-facing host URL:

```text
http://82.26.104.58:5173
```

Check whether the existing server is still running before starting another:

```bash
curl --fail http://127.0.0.1:5173/
```

## Verification commands

From `website/`:

```bash
npm ci
npm run typecheck
npm test -- --run
npm run format:check
npm run build
npm run test:e2e
```

Last completed results:

- **65/65 unit and DOM tests**
- **40/40 Playwright tests** across desktop and mobile
- **105 total tests passing**
- Strict TypeScript passed
- Production build and artifact checks passed
- Prettier passed

The existing Python acceptance suite also passed before frontend-only work:

- 255 standard Python tests
- 4 Python end-to-end tests
- 92.57% overall coverage
- 93% core coverage

Do not rerun paid/live model calls. These are deterministic frontend and local pipeline tests.

### Chromium on this host

The host lacks several standard Chromium libraries. `website/README.md` documents a project-local workaround using `apt-get download` and `dpkg-deb -x` into `website/.browser-deps`.

Do not install system packages or use sudo. Set `LD_LIBRARY_PATH` to the extracted local library directory when running Playwright, then remove the temporary dependency directory and test reports afterward.

## Repository state and constraints

- Repository: `/root/BreakFuser-public`
- GitHub: `https://github.com/Shannon-Tool/BreakFuser`
- Current branch: `main`
- HEAD when the work began: `7cfc0edcf319cf5ad9ea2539bca14072bb32786f`
- All current branding and website work is **uncommitted and unpushed**.
- Do not overwrite or revert unrelated branding edits.
- Do not commit or push unless the user explicitly asks.
- GitHub Pages deployment has not been executed.
- Pages should use GitHub Actions when publication is authorized.
- No backend/provider changes were made for the guided simulator.
- No API keys or secrets are needed or included.
- Do not add a marketing entry to `CHANGELOG.md`.
- Preserve SHANNON LAB LLC branding and provider neutrality.
- Aggressive recovery remains the product’s zero-configuration default; no custom headers should be required in normal product use.

## Acceptance bar for the next agent

A replacement is acceptable only when all of these are true:

- The user considers the visual direction professional and approves it.
- The first screen communicates a real process, not abstract model worship or decorative geometry.
- Input, parallel processing, recovery, evidence, composition, verification, and output are unmistakable.
- Data packets have meaningful names and follow the correct direction.
- Request JSON, process events, evidence, and response output update coherently.
- No important explanation depends on tiny labels or hidden panels.
- Desktop and mobile are both deliberately composed and readable.
- Reduced motion, keyboard use, and WebGL fallback remain functional.
- Curated data is never presented as live inference.
- Tests verify the actual behavior and do not merely preserve the rejected design.
- The final result is shown to the user as a real running experience and visually inspected at multiple stages and screen sizes.

**Do not declare success from passing tests alone. The missing requirement is the user’s approval of the design.**
