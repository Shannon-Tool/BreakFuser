import markUrl from "../../../assets/breakfuser-mark.svg";
import pipelineFallbackUrl from "./pipeline-fallback.svg";
import pipelineMobileUrl from "./pipeline-mobile.svg";

import { createAcquisitionFigure } from "../figures/AcquisitionFigure";
import { createAdvancedFigure } from "../figures/AdvancedFigure";
import { createIntegrationFigure } from "../figures/IntegrationFigure";
import { createProvenanceFigure } from "../figures/ProvenanceFigure";
import { createRecoveryFigure } from "../figures/RecoveryFigure";
import { createVerificationFigure } from "../figures/VerificationFigure";
import type { FigureView } from "../figures/types";
import { SCENARIOS, SIMULATION_LABEL } from "../scenarios";
import { NODE_CONTENT } from "../scene/content";
import {
    FUSION_NODE_IDS,
    FUSION_ROUTE_IDS,
    getStageVisualState,
    PACKET_LABELS,
    type FusionRouteId,
} from "../scene/geometry";
import { getFigureState, getVisibleEvents } from "../simulation";
import {
    STAGE_IDS,
    type FusionNode,
    type PlaybackSpeed,
    type Scenario,
    type SceneLabelPositions,
    type ScenePacketPositions,
    type SimulationState,
} from "../types";
import { button, element, json } from "./dom";

interface SimulatorActions {
    onPlayPause: () => void;
    onNextStep: () => void;
    onReplay: () => void;
    onSpeedChange: (speed: PlaybackSpeed) => void;
    onScenarioSelect: (scenarioId: string) => void;
    onNodeInspect: (node: FusionNode) => void;
    onViewReset: () => void;
    onCameraView: (view: "isometric" | "top") => void;
    onCameraMode?: (followStage: boolean) => void;
    onSceneResize?: () => void;
    onCopy: () => void;
}

export interface SimulatorView {
    readonly sceneContainer: HTMLElement;
    update: (state: SimulationState) => void;
    announceStage: (state: SimulationState) => void;
    inspectNode: (node: FusionNode | null) => void;
    projectLabels: (positions: SceneLabelPositions) => void;
    projectPackets: (positions: ScenePacketPositions) => void;
    setSceneAvailable: (available: boolean) => void;
    setReducedMotion: (reducedMotion: boolean) => void;
    setDockVisible: (visible: boolean) => void;
    setActiveFigure: (index: number) => void;
    setCopyFeedback: (feedback: "success" | "error" | null) => void;
}

const sectionData = [
    [
        "system",
        "Watch the fusion happen",
        "Your request becomes a live response contract. Three branches gather what they need, then the uncensored model writes the final answer.",
    ],
    [
        "acquisition",
        "Three branches. Zero dead time.",
        "Documents, frontier knowledge, and a local draft move in parallel—each with exactly the context it needs.",
    ],
    [
        "recovery",
        "A refusal is not the finish line",
        "Detect hedging, refusals, and missing facts. Recover useful knowledge with bounded, strategy-driven follow-ups.",
    ],
    [
        "provenance",
        "Every claim keeps its receipts",
        "Follow each answer back to source documents and individual model turns. Recovered knowledge stays attributable.",
    ],
    [
        "verification",
        "Uncensored does not mean unchecked",
        "The uncensored response model writes freely. Verification catches omissions and contradictions before delivery.",
    ],
    [
        "integration",
        "Your stack already knows how to use it",
        "Point your existing OpenAI-compatible client, agent, MCP server, or tool harness at BreakFuser and keep building.",
    ],
    [
        "advanced",
        "Simple by default. Powerful when you want it.",
        "Tune planning, context, harvesting, stopping, and budgets without turning the basic integration into a science project.",
    ],
] as const;

function getScenario(scenarioId: string): Scenario {
    const scenario = SCENARIOS.find((candidate) => candidate.id === scenarioId);
    const fallback = SCENARIOS[0];
    if (scenario !== undefined) return scenario;
    if (fallback === undefined)
        throw new Error("At least one curated scenario is required");
    return fallback;
}

function createMasthead(): HTMLElement {
    const header = element("header", "masthead");
    const inner = element("div", "paper-width masthead-inner");
    const brand = element("a", "brand");
    brand.href = "#paper-title";
    brand.setAttribute("aria-label", "BreakFuser home");
    const mark = element("img", "brand-mark");
    mark.src = markUrl;
    mark.alt = "";
    mark.width = 34;
    mark.height = 34;
    const words = element("span", "brand-words");
    words.append(
        element("strong", undefined, "SHANNON"),
        element("span", undefined, "BREAKFUSER"),
    );
    brand.append(mark, words);
    const navigation = element("nav", "masthead-classification");
    navigation.setAttribute("aria-label", "Main navigation");
    for (const [href, label] of [
        ["#worked-example", "Live demo"],
        ["#figure-1", "How it works"],
        ["#figure-6", "Integrations"],
    ] as const) {
        const link = element("a", undefined, label);
        link.href = href;
        navigation.append(link);
    }
    const source = element("a", "source-link", "GitHub ↗");
    source.href = "https://github.com/Shannon-Tool/BreakFuser";
    source.target = "_blank";
    source.rel = "noreferrer";
    inner.append(brand, navigation, source);
    header.append(inner);
    return header;
}

function createHero(onRun: () => void): HTMLElement {
    const hero = element("header", "paper-header");
    const issue = element("span", "issue-number", "BF");
    issue.setAttribute("aria-hidden", "true");
    const heroGrid = element("div", "hero-grid");
    const heroCopy = element("div", "hero-copy");
    const kicker = element("p", "paper-kicker");
    kicker.append(
        element("span", "status-dot"),
        element("span", undefined, "OPEN-SOURCE RUNTIME MODEL FUSION"),
    );
    const title = element("h1");
    title.id = "paper-title";
    title.append(
        element("span", undefined, "Any model."),
        element("em", undefined, "Uncensored."),
    );
    const primary = element(
        "p",
        "paper-primary",
        "Fuse frontier intelligence with uncensored response composition. Keep the capability, lose the overrefusals, and ship through one OpenAI-compatible API.",
    );
    const heroActions = element("div", "hero-actions");
    const launch = button(
        "hero-cta hero-cta-primary",
        "See BreakFuser in action ↓",
        onRun,
    );
    const github = element(
        "a",
        "hero-cta hero-cta-secondary",
        "Explore on GitHub ↗",
    );
    github.href = "https://github.com/Shannon-Tool/BreakFuser";
    github.target = "_blank";
    github.rel = "noreferrer";
    heroActions.append(launch, github);
    const proof = element("div", "hero-proof");
    for (const [value, label] of [
        ["01 API", "OpenAI compatible"],
        ["ANY PROVIDER", "Your models, your choice"],
        ["FULL CONTEXT", "One fused response"],
    ]) {
        const item = element("div", "hero-proof-item");
        item.append(
            element("strong", undefined, value),
            element("span", undefined, label),
        );
        proof.append(item);
    }
    heroCopy.append(kicker, title, primary, heroActions, proof);

    const cover = element("aside", "trace-cover");
    cover.setAttribute("aria-label", "Live fusion demo");
    const coverHeader = element("div", "cover-header");
    coverHeader.append(
        element("span", undefined, "●  LIVE FUSION DEMO"),
        element("span", "cover-stage", "Request + response contract"),
    );
    const coverRequest = element("blockquote", "cover-request");
    const coverBranches = element("div", "cover-branches");
    for (const [index, [id, label]] of [
        ["document", "Documents"],
        ["smart", "Frontier knowledge"],
        ["local", "Uncensored draft"],
    ].entries()) {
        const branch = element("div", "cover-branch");
        branch.dataset.branch = id;
        branch.dataset.state = "pending";
        branch.append(
            element("span", "cover-branch-index", `0${index + 1}`),
            element("strong", undefined, label),
            element("span", "cover-branch-state", "Pending"),
        );
        coverBranches.append(branch);
    }
    const coverResponse = element("div", "cover-response");
    coverResponse.append(
        element("span", "cover-response-marker"),
        element("strong", undefined, "Sealed · awaiting verify_after"),
    );
    const run = button("hero-run", "Run the fusion  →", onRun);
    cover.append(coverHeader, coverRequest, coverBranches, coverResponse, run);
    heroGrid.append(heroCopy, cover);

    const valueProps = element("section", "abstract");
    valueProps.setAttribute("aria-labelledby", "value-title");
    const valueTitle = element(
        "h2",
        undefined,
        "The brains you want. The freedom you need.",
    );
    valueTitle.id = "value-title";
    const copy = element(
        "p",
        undefined,
        "BreakFuser mines capable models for knowledge, then gives an uncensored model ownership of the final response. You get one seamless answer—not a relay, not a refusal, and not a second workflow.",
    );
    const values = element("div", "value-grid");
    for (const [index, title, description] of [
        [
            "01",
            "Mine the knowledge",
            "Recover useful evidence with multi-turn strategies and minimal-context queries.",
        ],
        [
            "02",
            "Fuse the response",
            "Let the uncensored model compose from the original request and complete evidence.",
        ],
        [
            "03",
            "Ship it anywhere",
            "Use Python, HTTP, streaming, MCP, agents, and existing OpenAI-compatible tools.",
        ],
    ]) {
        const card = element("article", "value-card");
        card.append(
            element("span", "value-index", index),
            element("h3", undefined, title),
            element("p", undefined, description),
        );
        values.append(card);
    }
    const disclosure = element("aside", "paper-disclosure");
    disclosure.append(
        element("strong", undefined, SIMULATION_LABEL),
        element(
            "p",
            undefined,
            "Explore four curated requests with synchronized live playback. No provider is called; illustrative timings are not benchmark results.",
        ),
    );
    valueProps.append(valueTitle, copy, values, disclosure);
    hero.append(issue, heroGrid, valueProps);
    return hero;
}

function createFigureSection(
    index: number,
    figureView: FigureView,
): HTMLElement {
    const data = sectionData[index];
    if (data === undefined) throw new Error("Unknown figure section");
    const [id, title, introduction] = data;
    const section = element("section", "paper-section");
    section.id = `section-${id}`;
    const number = element("span", "section-number", `${index + 1}.`);
    const heading = element("div", "section-heading");
    heading.append(
        element("h2", undefined, title),
        element("p", undefined, introduction),
    );
    section.append(number, heading);
    const figure = element("figure", "paper-figure");
    figure.id = `figure-${index + 1}`;
    figure.dataset.figure = id;
    figure.append(figureView.element);
    const caption = element("figcaption");
    caption.append(
        element(
            "strong",
            undefined,
            `LIVE VIEW ${String(index + 1).padStart(2, "0")}`,
        ),
        element("span", undefined, introduction),
    );
    figure.append(caption);
    section.append(figure);
    return section;
}

export function renderSimulator(
    root: HTMLElement,
    reducedMotion: boolean,
    actions: SimulatorActions,
): SimulatorView {
    root.replaceChildren();
    root.classList.add("research-paper");
    const skip = element("a", "skip-link", "Skip to live demo");
    skip.href = "#worked-example";
    const layout = element("div", "paper-width paper-layout");
    const contents = element("aside", "contents-column");
    const nav = element("nav", "paper-contents");
    nav.setAttribute("aria-label", "Product tour");
    nav.append(element("p", "contents-title", "PRODUCT TOUR"));
    for (const [index, data] of sectionData.entries()) {
        const link = element("a", undefined, `${index + 1}  ${data[1]}`);
        link.href = `#figure-${index + 1}`;
        nav.append(link);
    }
    const notation = element("div", "notation");
    notation.append(
        element("p", "contents-title", "FLOW COLORS"),
        element("p", undefined, "Violet · knowledge acquisition"),
        element("p", undefined, "Pink · response model"),
        element("p", undefined, "Green · verified evidence"),
        element("p", undefined, "Amber · verification"),
    );
    contents.append(nav, notation);
    const article = element("main", "paper-article");
    article.id = "main-content";
    article.append(
        createHero(() => {
            document.querySelector("#worked-example")?.scrollIntoView({
                behavior: motionReduced ? "auto" : "smooth",
            });
            if (currentState.status === "complete") actions.onReplay();
            else if (motionReduced) actions.onNextStep();
            else actions.onPlayPause();
        }),
    );

    const experiment = element("section", "experiment");
    experiment.id = "worked-example";
    const experimentHeading = element("div", "experiment-heading");
    const experimentTitle = element("div", "experiment-title");
    experimentTitle.append(
        element("p", "figure-label", "INTERACTIVE PRODUCT DEMO"),
        element("h2", undefined, "One request. Watch every move."),
    );
    experimentHeading.append(
        experimentTitle,
        element("span", "trace-disclosure", SIMULATION_LABEL),
    );
    const scenarios = element("div", "scenario-grid");
    scenarios.setAttribute("role", "group");
    scenarios.setAttribute("aria-label", "Curated worked examples");
    const scenarioButtons = new Map<string, HTMLButtonElement>();
    for (const [index, scenario] of SCENARIOS.entries()) {
        const select = button("scenario-select", "", () =>
            actions.onScenarioSelect(scenario.id),
        );
        select.setAttribute("aria-label", `Select ${scenario.title} scenario`);
        select.setAttribute("aria-pressed", "false");
        select.append(
            element("span", "scenario-number", `0${index + 1}`),
            element("span", "scenario-title", scenario.title),
        );
        scenarios.append(select);
        scenarioButtons.set(scenario.id, select);
    }
    const inputPreview = element("blockquote", "input-preview");
    const requestPreview = element("pre", "request-json code-block");
    const transport = element("div", "transport");
    const playPause = button("transport-primary", "Play", actions.onPlayPause);
    playPause.setAttribute("aria-label", "Play");
    const nextStep = button(
        "transport-button",
        "Next step",
        actions.onNextStep,
    );
    nextStep.setAttribute("aria-label", "Next step");
    const replay = button("transport-button", "Replay", actions.onReplay);
    replay.setAttribute("aria-label", "Replay");
    const progressText = element("span", "progress-text", "01 / 05");
    const runStatus = element("span", "run-status", "Ready");
    const progress = element("div", "progress-track");
    progress.setAttribute("role", "progressbar");
    progress.setAttribute("aria-label", "Worked trace progress");
    progress.setAttribute("aria-valuemin", "1");
    progress.setAttribute("aria-valuemax", "5");
    progress.setAttribute("aria-valuenow", "1");
    const progressFill = element("span", "progress-fill");
    progress.append(progressFill);
    const speedControl = element("div", "speed-control");
    speedControl.setAttribute("role", "group");
    speedControl.setAttribute("aria-label", "Playback speed");
    const speedButtons = new Map<PlaybackSpeed, HTMLButtonElement>();
    for (const speed of [0.5, 1, 2] as const) {
        const speedButton = button("speed-button", `${speed}×`, () =>
            actions.onSpeedChange(speed),
        );
        speedButton.setAttribute("aria-label", `${speed} times speed`);
        speedButton.setAttribute("aria-pressed", String(speed === 1));
        speedControl.append(speedButton);
        speedButtons.set(speed, speedButton);
    }
    transport.append(
        playPause,
        nextStep,
        replay,
        progressText,
        progress,
        runStatus,
        speedControl,
    );
    const motionNote = element(
        "p",
        "motion-note",
        "Reduced motion is on. Use Next step to inspect every state without automatic playback.",
    );
    motionNote.hidden = !reducedMotion;
    const timeline = element("ol", "timeline");
    const timelineItems: HTMLElement[] = [];
    const timelineTitles: HTMLElement[] = [];
    const timelineExplanations: HTMLElement[] = [];
    const timelineDetails: HTMLDetailsElement[] = [];
    for (const [index, id] of STAGE_IDS.entries()) {
        const item = element("li", "timeline-item");
        item.dataset.stage = id;
        item.dataset.state = index === 0 ? "active" : "pending";
        const marker = element(
            "span",
            "timeline-marker",
            String(index + 1).padStart(2, "0"),
        );
        const content = element("div", "timeline-content");
        const title = element("h3");
        const explanation = element("p", "timeline-explanation");
        const detail = element("details", "technical-detail");
        detail.append(
            element("summary", undefined, "Implementation note"),
            element("p"),
        );
        content.append(title, explanation, detail);
        item.append(marker, content);
        timeline.append(item);
        timelineItems.push(item);
        timelineTitles.push(title);
        timelineExplanations.push(explanation);
        timelineDetails.push(detail);
    }
    experiment.append(
        experimentHeading,
        scenarios,
        inputPreview,
        requestPreview,
        transport,
        motionNote,
        timeline,
    );
    article.append(experiment);

    const sceneFigure = element("div", "system-figure-body");
    const sceneTools = element("div", "scene-tools");
    const iso = button("view-button", "Isometric", () =>
        actions.onCameraView("isometric"),
    );
    iso.dataset.cameraView = "isometric";
    iso.setAttribute("aria-pressed", "true");
    const top = button("view-button", "Top / schematic", () =>
        actions.onCameraView("top"),
    );
    top.dataset.cameraView = "top";
    top.setAttribute("aria-pressed", "false");
    const resetView = button("view-button", "Reset view", actions.onViewReset);
    const follow = button("view-button", "Follow stage", () => {
        follow.setAttribute("aria-pressed", "true");
        free.setAttribute("aria-pressed", "false");
        actions.onCameraMode?.(true);
    });
    follow.dataset.cameraMode = "follow";
    follow.setAttribute("aria-pressed", "true");
    const free = button("view-button", "Free orbit", () => {
        follow.setAttribute("aria-pressed", "false");
        free.setAttribute("aria-pressed", "true");
        actions.onCameraMode?.(false);
    });
    free.dataset.cameraMode = "free";
    free.setAttribute("aria-pressed", "false");
    const focusButton = button("view-button", "Focus figure", openFocusFigure);
    focusButton.dataset.action = "focus-figure";
    sceneTools.append(
        iso,
        top,
        resetView,
        follow,
        free,
        focusButton,
        element(
            "span",
            "scene-hint",
            "Drag to orbit · scroll to zoom · select a module",
        ),
    );
    const sceneViewport = element("div", "scene-viewport");
    const sceneContainer = element("div", "scene-canvas");
    sceneContainer.setAttribute(
        "aria-label",
        "Interactive three-dimensional BreakFuser system model",
    );
    const fallback = element("div", "scene-fallback");
    fallback.hidden = true;
    const fallbackPicture = element("picture", "fallback-picture");
    const mobileSource = element("source");
    mobileSource.media = "(max-width: 700px)";
    mobileSource.srcset = pipelineMobileUrl;
    const fallbackImage = element("img", "fallback-image");
    fallbackImage.src = pipelineFallbackUrl;
    fallbackImage.alt =
        "BreakFuser pipeline: request, ResponseContract, three acquisition branches, Evidence blackboard, uncensored composition, verify after, and ChatCompletion.";
    fallbackPicture.append(mobileSource, fallbackImage);
    fallback.append(
        fallbackPicture,
        element(
            "p",
            undefined,
            "Static schematic · all figures, payload controls, and the trace ledger remain available.",
        ),
    );
    const packetBar = element("div", "packet-bar");
    packetBar.setAttribute("aria-hidden", "true");
    const packetLabels = new Map<FusionRouteId, HTMLElement>();
    for (const route of FUSION_ROUTE_IDS) {
        const label = element(
            "span",
            "scene-packet-label",
            PACKET_LABELS[route],
        );
        label.dataset.route = route;
        packetBar.append(label);
        packetLabels.set(route, label);
    }
    const nodeBar = element("div", "node-bar");
    const nodeButtons = new Map<FusionNode, HTMLButtonElement>();
    for (const node of FUSION_NODE_IDS) {
        const content = NODE_CONTENT[node];
        const nodeButton = button("scene-node-label", "", () =>
            actions.onNodeInspect(node),
        );
        nodeButton.dataset.node = node;
        nodeButton.dataset.sceneNode = node;
        nodeButton.setAttribute("aria-label", `Inspect ${content.title}`);
        nodeButton.setAttribute("aria-controls", "node-inspector");
        nodeButton.setAttribute("aria-expanded", "false");
        nodeButton.addEventListener("focus", () => actions.onNodeInspect(node));
        nodeButton.append(
            element("span", `node-index node-index-${node}`),
            element("span", "node-button-words"),
        );
        const words = nodeButton.lastElementChild;
        words?.append(
            element("strong", undefined, content.shortTitle),
            element("span", undefined, content.label),
        );
        nodeBar.append(nodeButton);
        nodeButtons.set(node, nodeButton);
    }
    sceneViewport.append(sceneContainer, fallback, packetBar, nodeBar);
    const moduleIndex = element("div", "module-payload-index");
    moduleIndex.setAttribute("role", "group");
    moduleIndex.setAttribute("aria-label", "Inspect module payloads");
    const payloadButtons = new Map<FusionNode, HTMLButtonElement>();
    for (const [index, node] of FUSION_NODE_IDS.entries()) {
        const content = NODE_CONTENT[node];
        const payloadButton = button(
            "module-payload-button",
            `${String(index + 1).padStart(2, "0")} · ${content.shortTitle}`,
            () => actions.onNodeInspect(node),
        );
        payloadButton.setAttribute("aria-label", `Payload: ${content.title}`);
        payloadButton.setAttribute("aria-expanded", "false");
        payloadButton.addEventListener("focus", () =>
            actions.onNodeInspect(node),
        );
        moduleIndex.append(payloadButton);
        payloadButtons.set(node, payloadButton);
    }
    const packetLegend = element("div", "mobile-packet-legend");
    packetLegend.append(element("strong", undefined, "ACTIVE PAYLOADS"));
    const packetLegendItems = element("div", "mobile-packet-items");
    packetLegend.append(packetLegendItems);
    const inspector = element("aside", "node-inspector");
    inspector.id = "node-inspector";
    inspector.hidden = true;
    const inspectorCopy = element("div", "inspector-copy");
    const inspectorTitle = element("h3");
    inspectorTitle.id = "inspector-title";
    inspectorCopy.append(
        element("p", "figure-label", "MODULE + DATA PAYLOAD"),
        inspectorTitle,
        element("p", undefined),
    );
    const inspectorPayload = element("pre", "inspector-payload code-block");
    const inspectorClose = button(
        "view-button",
        "Close node inspection",
        () => {
            actions.onViewReset();
            resetView.focus();
        },
    );
    inspector.append(inspectorCopy, inspectorPayload, inspectorClose);
    sceneFigure.append(
        sceneTools,
        sceneViewport,
        moduleIndex,
        packetLegend,
        inspector,
    );
    const focusDialog = element("dialog", "focus-dialog");
    focusDialog.setAttribute("aria-label", "Focused BreakFuser system figure");
    const focusClose = button(
        "view-button focus-close",
        "Exit focus",
        closeFocusFigure,
    );
    focusClose.dataset.action = "close-focus";
    focusDialog.append(focusClose);
    let sceneHome: ParentNode | null = null;
    let sceneNext: Node | null = null;
    let focusReturn: HTMLElement | null = null;

    function openFocusFigure(): void {
        if (focusDialog.open || sceneFigure.parentElement === null) return;
        sceneHome = sceneFigure.parentElement;
        sceneNext = sceneFigure.nextSibling;
        focusReturn =
            document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null;
        focusDialog.append(sceneFigure);
        if (typeof focusDialog.showModal === "function")
            focusDialog.showModal();
        else focusDialog.setAttribute("open", "");
        focusClose.focus();
        actions.onSceneResize?.();
    }

    function closeFocusFigure(): void {
        if (typeof focusDialog.close === "function" && focusDialog.open)
            focusDialog.close();
        else focusDialog.removeAttribute("open");
        restoreSceneFigure();
    }

    function restoreSceneFigure(): void {
        if (sceneFigure.parentElement !== focusDialog) return;
        sceneHome?.insertBefore(sceneFigure, sceneNext);
        focusReturn?.focus();
        actions.onSceneResize?.();
    }

    focusDialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeFocusFigure();
    });
    focusDialog.addEventListener("close", restoreSceneFigure);
    const systemFigure: FigureView = {
        element: sceneFigure,
        update() {},
    };
    article.append(createFigureSection(0, systemFigure));

    const acquisition = createAcquisitionFigure();
    const recovery = createRecoveryFigure();
    const provenance = createProvenanceFigure();
    const verification = createVerificationFigure();
    const integration = createIntegrationFigure();
    const advanced = createAdvancedFigure();
    const figures = [
        acquisition,
        recovery,
        provenance,
        verification,
        integration,
        advanced,
    ];
    for (const [index, figure] of figures.entries()) {
        article.append(createFigureSection(index + 1, figure));
    }

    const copy = button("transport-button", "Copy answer", actions.onCopy);
    copy.setAttribute("aria-label", "Copy final answer");
    copy.setAttribute("aria-describedby", "copy-feedback");
    copy.disabled = true;
    verification.element.querySelector(".output-actions")?.append(copy);

    const ledger = element("section", "trace-ledger");
    const ledgerHeading = element("div", "ledger-heading");
    ledgerHeading.append(
        element("p", "figure-label", "OBSERVATION RECORD"),
        element("h2", undefined, "Synchronized trace ledger"),
        element(
            "p",
            undefined,
            "The same selected trace drives every figure. Events append in order; evidence and response fields retain their implementation-shaped names.",
        ),
    );
    const ledgerGrid = element("div", "ledger-grid");
    const eventsPanel = element("section", "ledger-panel");
    eventsPanel.append(
        element("p", "figure-label", "ORDERED PROCESS EVENTS"),
        element("h3", undefined, "Execution journal"),
    );
    const eventsList = element("ol", "process-events");
    eventsPanel.append(eventsList);
    const evidencePanel = element("section", "ledger-panel");
    evidencePanel.append(
        element("p", "figure-label", "EVIDENCE SPANS"),
        element("h3", undefined, "Source-linked records"),
    );
    const evidenceList = element("div", "evidence-list");
    evidencePanel.append(evidenceList);
    ledgerGrid.append(eventsPanel, evidencePanel);
    ledger.append(ledgerHeading, ledgerGrid);
    article.append(ledger);

    const conclusion = element("section", "paper-conclusion");
    const conclusionActions = element("div", "conclusion-actions");
    const startBuilding = element(
        "a",
        "hero-cta hero-cta-primary",
        "Start building ↗",
    );
    startBuilding.href = "https://github.com/Shannon-Tool/BreakFuser";
    startBuilding.target = "_blank";
    startBuilding.rel = "noreferrer";
    const documentation = element(
        "a",
        "hero-cta hero-cta-secondary",
        "Read the docs",
    );
    documentation.href =
        "https://github.com/Shannon-Tool/BreakFuser#quickstart";
    documentation.target = "_blank";
    documentation.rel = "noreferrer";
    conclusionActions.append(startBuilding, documentation);
    conclusion.append(
        element("p", "figure-label", "OPEN SOURCE. PROVIDER NEUTRAL."),
        element("h2", undefined, "Your models. Your rules."),
        element(
            "p",
            undefined,
            "Build with the frontier knowledge you need and the response freedom your users expect. Drop BreakFuser into your stack, bring your own providers, and make your next request.",
        ),
        conclusionActions,
    );
    article.append(conclusion);
    layout.append(contents, article);
    const footer = element("footer", "paper-footer");
    const footerInner = element("div", "paper-width");
    footerInner.append(
        element("strong", undefined, "SHANNON LAB LLC · BREAKFUSER"),
        element(
            "span",
            undefined,
            "Open-source runtime model fusion · provider-neutral architecture",
        ),
    );
    footer.append(footerInner);
    const stageLive = element("p", "sr-only");
    stageLive.setAttribute("aria-live", "polite");
    const traceDock = element("section", "trace-dock");
    traceDock.hidden = true;
    traceDock.setAttribute("aria-label", "Persistent trace controls");
    const dockIdentity = element("div", "dock-identity");
    dockIdentity.append(
        element("span", "dock-kicker", "LIVE TRACE"),
        element("strong", "dock-scenario", "General QA"),
        element("span", "dock-stage", "Request + response contract"),
    );
    const dockSegments = element("div", "dock-segments");
    const dockSegmentItems: HTMLElement[] = [];
    for (let index = 0; index < 5; index += 1) {
        const segment = element("span", "dock-segment");
        segment.dataset.state = index === 0 ? "active" : "pending";
        dockSegments.append(segment);
        dockSegmentItems.push(segment);
    }
    const dockPlay = button("dock-button", "Play", actions.onPlayPause);
    dockPlay.setAttribute("aria-label", "Dock play");
    const dockNext = button("dock-button", "Next", actions.onNextStep);
    dockNext.setAttribute("aria-label", "Dock next step");
    const dockReplay = button("dock-button", "Replay", actions.onReplay);
    dockReplay.setAttribute("aria-label", "Dock replay");
    traceDock.append(
        dockIdentity,
        dockSegments,
        dockPlay,
        dockNext,
        dockReplay,
    );
    root.append(
        skip,
        createMasthead(),
        layout,
        footer,
        stageLive,
        traceDock,
        focusDialog,
    );

    let currentState = createInitialPaperState();
    let renderedScenarioId = "";
    let renderedEventsKey = "";
    let renderedEvidenceKey = "";
    let motionReduced = reducedMotion;

    function createInitialPaperState(): SimulationState {
        return {
            scenarioId: SCENARIOS[0]?.id ?? "",
            stageIndex: 0,
            status: "idle",
            speed: 1,
        };
    }

    function nodePayload(node: FusionNode): unknown {
        const scenario = getScenario(currentState.scenarioId);
        const figure = getFigureState(scenario, currentState);
        const pending = {
            status: "pending",
            available_at: node === "output" ? "verify_after" : "later_stage",
        };
        if (node === "request") return scenario.request;
        if (node === "orchestrator") return scenario.contract;
        if (node === "documents")
            return currentState.stageIndex >= 1 ? scenario.documents : pending;
        if (node === "smart")
            return {
                sanitized_query: scenario.sanitizedQuery,
                minimal_context: true,
                quality: figure.recovery.quality ?? "pending",
                recovery_strategy: figure.recovery.strategy ?? "pending",
                recovery_owner: "smart_model",
                turns: figure.recovery.turns,
            };
        if (node === "local_draft")
            return currentState.stageIndex >= 1
                ? {
                      model_role: "uncensored",
                      turn_id: "local-draft",
                      text: scenario.localDraft,
                  }
                : pending;
        if (node === "blackboard") {
            if (figure.blackboard.status === "pending") return pending;
            return {
                question: scenario.input,
                contract: scenario.contract,
                documents: scenario.documents,
                spans: figure.blackboard.evidence,
                harvest_results: {
                    quality: scenario.quality,
                    strategy: scenario.recoveryStrategy,
                },
                timings: scenario.completion.breakfuser.fusion.stage_timings_ms,
            };
        }
        if (node === "composition")
            return currentState.stageIndex >= 3
                ? {
                      composition_mode: "targeted_synthesis",
                      model_role: "uncensored",
                      inputs: ["original_context", "EvidenceBlackboard"],
                      remote_bypass: false,
                  }
                : pending;
        if (node === "verification")
            return figure.verification.result ?? pending;
        return figure.output.completion ?? pending;
    }

    function inspectNode(node: FusionNode | null): void {
        inspector.hidden = node === null;
        for (const [id, nodeButton] of nodeButtons) {
            const selected = id === node;
            nodeButton.classList.toggle("is-selected", selected);
            nodeButton.setAttribute("aria-expanded", String(selected));
        }
        for (const [id, payloadButton] of payloadButtons) {
            payloadButton.setAttribute("aria-expanded", String(id === node));
        }
        if (node === null) return;
        inspector.dataset.node = node;
        const content = NODE_CONTENT[node];
        const title = inspectorCopy.querySelector("h3");
        const description = inspectorCopy.querySelector("p:not(.figure-label)");
        if (title !== null) title.textContent = content.title;
        if (description !== null) {
            description.id = "inspector-description";
            description.textContent = content.description;
        }
        inspectorPayload.textContent = json(nodePayload(node));
    }

    function updateEvents(state: SimulationState, scenario: Scenario): void {
        const key = `${scenario.id}:${state.stageIndex}`;
        if (key === renderedEventsKey) return;
        renderedEventsKey = key;
        eventsList.replaceChildren();
        for (const event of getVisibleEvents(scenario, state)) {
            const item = element("li", "process-event");
            item.dataset.sequence = String(event.sequence);
            item.dataset.stage = event.stage;
            item.dataset.phase = event.phase;
            item.dataset.kind = event.kind;
            if (event.branch !== undefined) item.dataset.branch = event.branch;
            item.append(
                element(
                    "span",
                    "event-meta",
                    `${event.timestamp} · #${String(event.sequence).padStart(2, "0")} · ${event.phase}`,
                ),
                element("p", undefined, event.message),
            );
            eventsList.append(item);
        }
        eventsList.scrollTop = eventsList.scrollHeight;
    }

    function updateEvidence(state: SimulationState): void {
        const key = `${state.scenarioId}:${state.stageIndex}`;
        if (key === renderedEvidenceKey) return;
        renderedEvidenceKey = key;
        evidenceList.replaceChildren();
        const scenario = getScenario(state.scenarioId);
        const records = getFigureState(scenario, state).blackboard.evidence;
        if (records.length === 0) {
            evidenceList.append(
                element(
                    "p",
                    "evidence-pending",
                    "Evidence is revealed here when the blackboard is assembled for composition.",
                ),
            );
            return;
        }
        for (const record of records) {
            const item = element("article", "evidence-record");
            item.dataset.origin = record.origin;
            item.dataset.revealStage = record.revealStage;
            const heading = element("div", "evidence-record-heading");
            heading.append(
                element(
                    "span",
                    `evidence-origin evidence-origin-${record.origin}`,
                    record.origin,
                ),
                element("code", undefined, record.id),
            );
            const link = element("a", "evidence-provenance", "provenance ↗");
            link.href = record.provenance;
            item.append(
                heading,
                element(
                    "p",
                    "evidence-ids",
                    `source_id=${record.source_id} · turn_id=${record.turn_id ?? "null"}`,
                ),
                element("p", "evidence-text", record.text),
                element(
                    "p",
                    "evidence-record-footer",
                    `complete=${record.complete} · salvaged=${record.salvaged} · confidence=${record.confidence.toFixed(2)}`,
                ),
                link,
            );
            evidenceList.append(item);
        }
    }

    function update(state: SimulationState): void {
        currentState = state;
        const scenario = getScenario(state.scenarioId);
        const figureState = getFigureState(scenario, state);
        const stageIndex = Math.max(
            0,
            Math.min(state.stageIndex, STAGE_IDS.length - 1),
        );
        const stage = scenario.stages[stageIndex] ?? scenario.stages[0];
        if (stage === undefined)
            throw new Error("The selected scenario has no stages");
        const outputReady = figureState.output.status === "ready";
        root.dataset.stage = stage.id;
        root.dataset.status = state.status;
        const cover = root.querySelector<HTMLElement>(".trace-cover");
        if (cover !== null) cover.dataset.stage = stage.id;
        const coverStage = root.querySelector(".cover-stage");
        if (coverStage !== null) coverStage.textContent = stage.title;
        const coverRequest = root.querySelector(".cover-request");
        if (coverRequest !== null)
            coverRequest.textContent = `“${scenario.input}”`;
        for (const branch of figureState.acquisition) {
            const coverBranch = root.querySelector<HTMLElement>(
                `.cover-branch[data-branch='${branch.id}']`,
            );
            if (coverBranch === null) continue;
            coverBranch.dataset.state = branch.status;
            const branchStatus = coverBranch.querySelector(
                ".cover-branch-state",
            );
            if (branchStatus !== null)
                branchStatus.textContent =
                    branch.status === "complete" ? "Complete" : "Pending";
        }
        const coverResponse = root.querySelector(".cover-response strong");
        if (coverResponse !== null)
            coverResponse.textContent = outputReady
                ? "Verified · ChatCompletion"
                : `Sealed · ${stage.title}`;
        const dockScenario = traceDock.querySelector(".dock-scenario");
        if (dockScenario !== null) dockScenario.textContent = scenario.title;
        const dockStage = traceDock.querySelector(".dock-stage");
        if (dockStage !== null) dockStage.textContent = stage.title;
        for (const [index, segment] of dockSegmentItems.entries()) {
            segment.dataset.state =
                index < stageIndex || outputReady
                    ? "complete"
                    : index === stageIndex
                      ? "active"
                      : "pending";
        }
        const dockPlayLabel =
            state.status === "playing"
                ? "Pause"
                : state.status === "paused"
                  ? "Resume"
                  : "Play";
        dockPlay.textContent = dockPlayLabel;
        dockPlay.setAttribute(
            "aria-label",
            `Dock ${dockPlayLabel.toLowerCase()}`,
        );
        dockPlay.disabled = motionReduced || state.status === "complete";
        dockNext.disabled =
            state.status === "playing" || state.status === "complete";
        if (renderedScenarioId !== scenario.id) {
            renderedScenarioId = scenario.id;
            requestPreview.textContent = json(scenario.request);
            inputPreview.textContent = `“${scenario.input}”`;
            for (const [index, timelineStage] of scenario.stages.entries()) {
                const title = timelineTitles[index];
                const explanation = timelineExplanations[index];
                const detail = timelineDetails[index]?.querySelector("p");
                if (title !== undefined)
                    title.textContent = timelineStage.title;
                if (explanation !== undefined)
                    explanation.textContent = timelineStage.explanation;
                if (detail !== null && detail !== undefined)
                    detail.textContent = timelineStage.detail;
            }
        }
        for (const candidate of SCENARIOS) {
            scenarioButtons
                .get(candidate.id)
                ?.setAttribute(
                    "aria-pressed",
                    String(candidate.id === scenario.id),
                );
        }
        progressText.textContent = `${String(stageIndex + 1).padStart(2, "0")} / 05`;
        progress.setAttribute("aria-valuenow", String(stageIndex + 1));
        progress.setAttribute(
            "aria-valuetext",
            `${stage.title}, step ${stageIndex + 1} of 5`,
        );
        progressFill.style.width = `${((stageIndex + 1) / 5) * 100}%`;
        for (const [index, item] of timelineItems.entries()) {
            const complete =
                index < stageIndex ||
                (state.status === "complete" && index === stageIndex);
            const active = index === stageIndex && !complete;
            item.dataset.state = complete
                ? "complete"
                : active
                  ? "active"
                  : "pending";
            if (active) item.setAttribute("aria-current", "step");
            else item.removeAttribute("aria-current");
            const explanation = timelineExplanations[index];
            const detail = timelineDetails[index];
            if (explanation !== undefined) explanation.hidden = !active;
            if (detail !== undefined) {
                detail.hidden = !active;
                if (!active) detail.open = false;
            }
        }
        runStatus.textContent = motionReduced
            ? "Manual"
            : state.status === "playing"
              ? "Playing"
              : state.status === "complete"
                ? "Complete"
                : state.status === "paused"
                  ? "Paused"
                  : "Ready";
        runStatus.dataset.status = state.status;
        acquisition.element.dataset.state = figureState.acquisition.every(
            (branch) => branch.status === "complete",
        )
            ? "complete"
            : "pending";
        const acquisitionFigure = root.querySelector<HTMLElement>(
            "[data-figure='acquisition']",
        );
        if (acquisitionFigure !== null)
            acquisitionFigure.dataset.state = acquisition.element.dataset.state;
        const recoveryFigure = root.querySelector<HTMLElement>(
            "[data-figure='recovery']",
        );
        if (recoveryFigure !== null)
            recoveryFigure.dataset.state = figureState.recovery.status;
        for (const figure of figures)
            figure.update(figureState, scenario, state);
        const visual = getStageVisualState(stage.id);
        for (const [node, label] of nodeButtons)
            label.dataset.active = String(visual.activeNodes.includes(node));
        for (const [route, label] of packetLabels)
            label.dataset.active = String(visual.activeRoutes.includes(route));
        packetLegendItems.replaceChildren();
        for (const route of visual.activeRoutes)
            packetLegendItems.append(
                element("span", "active-packet", PACKET_LABELS[route]),
            );
        updateEvents(state, scenario);
        updateEvidence(state);
        if (!inspector.hidden && inspector.dataset.node !== undefined)
            inspectNode(inspector.dataset.node as FusionNode);
        copy.disabled = !outputReady;
        const playLabel =
            state.status === "playing"
                ? "Pause"
                : state.status === "paused"
                  ? "Resume"
                  : "Play";
        playPause.textContent = playLabel;
        playPause.setAttribute("aria-label", playLabel);
        playPause.disabled = motionReduced || state.status === "complete";
        nextStep.disabled =
            state.status === "playing" || state.status === "complete";
        nextStep.title =
            state.status === "playing" ? "Pause playback to step manually" : "";
        for (const [speed, speedButton] of speedButtons) {
            speedButton.setAttribute(
                "aria-pressed",
                String(state.speed === speed),
            );
            speedButton.disabled = motionReduced;
        }
    }

    function announceStage(state: SimulationState): void {
        const scenario = getScenario(state.scenarioId);
        const stage = scenario.stages[state.stageIndex];
        if (stage !== undefined)
            stageLive.textContent = `Stage ${state.stageIndex + 1} of 5: ${stage.title}.`;
    }

    function projectLabels(positions: SceneLabelPositions): void {
        for (const [node, label] of nodeButtons) {
            const position = positions[node];
            label.style.left = `${position.x}px`;
            label.style.top = `${position.y}px`;
            label.dataset.projected = "true";
            label.hidden = !position.visible;
        }
    }

    function projectPackets(positions: ScenePacketPositions): void {
        for (const [route, label] of packetLabels) {
            const position = positions[route];
            if (position === undefined) continue;
            label.style.left = `${position.x}px`;
            label.style.top = `${position.y}px`;
            label.hidden = !position.visible || label.dataset.active !== "true";
        }
    }

    function setSceneAvailable(available: boolean): void {
        sceneContainer.hidden = !available;
        fallback.hidden = available;
        packetBar.hidden = !available;
        nodeBar.hidden = !available;
        sceneViewport.dataset.scene = available ? "webgl" : "fallback";
        sceneHintUpdate(available);
    }

    function sceneHintUpdate(available: boolean): void {
        const hint = sceneTools.querySelector(".scene-hint");
        if (hint !== null)
            hint.textContent = available
                ? "Drag to orbit · scroll to zoom · select a module"
                : "Static schematic · use Isometric to enable the interactive model";
    }

    function setReducedMotion(reduced: boolean): void {
        motionReduced = reduced;
        motionNote.hidden = !reduced;
        root.dataset.reducedMotion = String(reduced);
    }

    function setDockVisible(visible: boolean): void {
        traceDock.hidden = !visible;
        root.classList.toggle("dock-visible", visible);
    }

    function setActiveFigure(index: number): void {
        const links = nav.querySelectorAll("a");
        for (const [linkIndex, link] of links.entries()) {
            if (linkIndex === index)
                link.setAttribute("aria-current", "location");
            else link.removeAttribute("aria-current");
        }
        root.style.setProperty(
            "--reading-progress",
            String((index + 1) / links.length),
        );
    }

    function setCopyFeedback(feedback: "success" | "error" | null): void {
        const target =
            verification.element.querySelector<HTMLElement>(".copy-feedback");
        if (target === null) return;
        target.dataset.state = feedback ?? "";
        target.textContent =
            feedback === "success"
                ? "Copied to clipboard."
                : feedback === "error"
                  ? "Copy failed. Select the answer text and copy it manually."
                  : "";
    }

    root.dataset.reducedMotion = String(reducedMotion);
    update(currentState);
    return {
        sceneContainer,
        update,
        announceStage,
        inspectNode,
        projectLabels,
        projectPackets,
        setSceneAvailable,
        setReducedMotion,
        setDockVisible,
        setActiveFigure,
        setCopyFeedback,
    };
}
