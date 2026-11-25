# BreakFuser interactive product launch

This website presents BreakFuser's runtime model-fusion pipeline as a bold developer-product launch with a live interactive product tour. A single selected trace synchronizes the 3D system model, six supporting technical views, request JSON, process events, evidence spans, provenance links, verification results, and response metadata.

## Interactive product tour

1. **Watch the fusion happen** — an orthographic Three.js model with isometric and top views, named data payloads, module inspection, and a responsive static schematic.
2. **Three branches, zero dead time** — document retrieval, response-model drafting, and sanitized knowledge-model acquisition.
3. **Quality detection and bounded recovery** — the initial knowledge-model turn, quality class, selected strategy, conditional second turn, and inline two-turn limit.
4. **Evidence and provenance** — source records, required atoms, complete/salvaged spans, final claims, turn IDs, and document IDs.
5. **Composition and verify-after** — uncensored response ownership, verification checks, and the gated final response.
6. **Delivery contracts** — Python, OpenAI-compatible HTTP, buffered streaming, MCP, and caller-owned tool execution.
7. **Extended orchestration** — context compression, optional decider/VoI control, subagent DAGs, advanced harvest policy, budgets, cancellation, and artifacts.

Four worked examples are included: general question answering, medical information, authorized pentesting, and code generation. Use **Play**, **Pause**, **Next step**, **Replay**, and the speed controls to inspect their shared state. The live launch cover and floating trace dock follow the same reducer. After the main transport leaves the viewport, the dock preserves playback control and the product-tour state follows the active view.

The 3D exhibit supports **Follow stage** camera framing and **Free orbit**. **Focus figure** opens an accessible near-fullscreen dialog with the same live scene, payload inspector, Escape-to-close behavior, and focus restoration. Named payloads carry short directional trails; reduced-motion mode disables cinematic movement and automatic playback. On mobile, the vertical schematic is the default; select **Isometric** to mount the interactive 3D view. Keyboard users can inspect every module through the adjacent payload controls.

Instrument Serif, Inter, and IBM Plex Mono are bundled locally under `src/assets/fonts/`, including their SIL Open Font License texts. The site makes no runtime font-service requests.

**All scenarios and responses are fixed illustrative data.** The site does not accept arbitrary questions, call a model provider, or establish factual correctness. Live playback means synchronized presentation of a curated trace, not live inference. Illustrative timestamps are not measurements.

## Run locally

Node.js 22 is recommended. From this directory:

```bash
npm ci
npm run dev
```

Open the local URL printed by Vite. Development uses `/` as its base. Production builds use `/BreakFuser/` for GitHub Pages; set `VITE_BASE_PATH=/` only when a root-relative production preview is needed, as the browser-test configuration does.

## Checks and production build

```bash
npm run typecheck       # strict TypeScript checking
npm test -- --run       # unit and DOM tests
npm run format:check    # Prettier formatting
npm run build           # production output in dist/
npm run preview         # serve the production build locally
```

Every build checks the generated base paths and verifies that `dist/THREE-LICENSE.txt` exactly matches the Three.js MIT license shipped with the installed package.

## Browser tests

Install Playwright's Chromium browser once, then run the desktop and mobile tests:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 npx playwright install chromium
npm run test:e2e
```

The browser suite covers all four examples, camera controls, keyboard operation, claim provenance, mobile 3D opt-in, responsive fallback, reduced motion, WebGL context loss, clipboard behavior, and horizontal overflow at desktop, tablet, and narrow mobile sizes.

Chromium also needs Playwright's standard Linux system libraries. On a clean Debian/Ubuntu machine where system package installation is available, `PLAYWRIGHT_BROWSERS_PATH=0 npx playwright install --with-deps chromium` installs both; this may require administrator privileges. Most users do not need any additional workaround.

On the project's Ubuntu 24.04 verification host only, system package installation was intentionally avoided. The missing libraries were instead downloaded and extracted beneath the ignored `.browser-deps/` directory:

```bash
mkdir -p .browser-deps/packages .browser-deps/root
cd .browser-deps/packages
apt-get download libatk-bridge2.0-0t64 libatspi2.0-0t64 libasound2t64
for package in ./*.deb; do dpkg-deb -x "$package" ../root; done
cd ../..
LD_LIBRARY_PATH="$PWD/.browser-deps/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" npm run test:e2e
```

Remove that project-local workaround afterward with `rm -rf .browser-deps`. The CI workflow uses Playwright's standard `--with-deps` installation instead.
