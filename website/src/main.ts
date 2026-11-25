import { createFusionScene } from "./scene/FusionScene";
import { SCENARIOS } from "./scenarios";
import {
    createInitialState,
    transition,
    type SimulationAction,
} from "./simulation";
import "./styles.css";
import "./elevated.css";
import "./marketing.css";
import type { FusionNode, FusionSceneAdapter, SimulationState } from "./types";
import { renderSimulator } from "./ui/render";

const STAGE_DURATION_MS = 2200;

const app = document.querySelector<HTMLElement>("#app");
const firstScenario = SCENARIOS[0];

if (app === null || firstScenario === undefined) {
    throw new Error("The simulator could not be initialized");
}

const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
let reducedMotion = motionPreference.matches;
let state = createInitialState(firstScenario.id);
let scene: FusionSceneAdapter | null = null;
let webglRequested = window.innerWidth > 700;
let scheduledTick: number | null = null;
let dockObserver: IntersectionObserver | null = null;
let sectionObserver: IntersectionObserver | null = null;
let copyOperation = 0;
let disposed = false;

function currentScenario() {
    return (
        SCENARIOS.find((scenario) => scenario.id === state.scenarioId) ??
        firstScenario
    );
}

function cancelScheduledTick(): void {
    if (scheduledTick !== null) {
        window.clearTimeout(scheduledTick);
        scheduledTick = null;
    }
}

function canSchedule(): boolean {
    return (
        !disposed &&
        !reducedMotion &&
        !document.hidden &&
        state.status === "playing"
    );
}

function scheduleNextTick(): void {
    cancelScheduledTick();
    if (!canSchedule()) {
        return;
    }
    scheduledTick = window.setTimeout(() => {
        scheduledTick = null;
        if (canSchedule()) {
            dispatch({ type: "tick" });
        }
    }, STAGE_DURATION_MS / state.speed);
}

function syncScene(previous: SimulationState | null): void {
    if (scene === null) {
        return;
    }
    const previousStage = previous === null ? null : previous.stageIndex;
    if (previousStage !== state.stageIndex) {
        scene.setStage(
            currentScenario().stages[state.stageIndex]?.id ?? "input",
        );
    }
    if (previous === null || previous.status !== state.status) {
        scene.setPlaying(state.status === "playing" && !reducedMotion);
    }
    if (previous === null || previous.speed !== state.speed) {
        scene.setSpeed(state.speed);
    }
}

function inspectNode(node: FusionNode): void {
    view.inspectNode(node);
    scene?.focusNode(node);
}

function resetView(): void {
    view.inspectNode(null);
    scene?.resetView();
}

function dispatch(action: SimulationAction): void {
    if (disposed) {
        return;
    }
    cancelScheduledTick();
    copyOperation += 1;
    view.setCopyFeedback(null);
    const previous = state;
    state = transition(state, action);

    if (action.type === "replay" || action.type === "selectScenario") {
        view.inspectNode(null);
        scene?.resetView();
    }

    view.update(state);
    syncScene(previous);
    if (previous.stageIndex !== state.stageIndex) {
        view.announceStage(state);
    }
    scheduleNextTick();
}

function legacyCopy(text: string): boolean {
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.readOnly = true;
    helper.className = "copy-helper";
    document.body.append(helper);
    helper.select();
    const copied = document.execCommand("copy");
    helper.remove();
    return copied;
}

async function copyFinalResponse(): Promise<void> {
    if (state.status !== "complete") {
        return;
    }
    const operation = ++copyOperation;
    const scenario = currentScenario();
    try {
        if (navigator.clipboard !== undefined) {
            await navigator.clipboard.writeText(scenario.finalResponse);
        } else if (!legacyCopy(scenario.finalResponse)) {
            throw new Error("Legacy clipboard copy was rejected");
        }
        if (!disposed && operation === copyOperation) {
            view.setCopyFeedback("success");
        }
    } catch {
        if (!disposed && operation === copyOperation) {
            view.setCopyFeedback("error");
        }
    }
}

const view = renderSimulator(app, reducedMotion, {
    onPlayPause: () => {
        if (!reducedMotion) {
            dispatch({ type: state.status === "playing" ? "pause" : "play" });
        }
    },
    onNextStep: () => {
        dispatch({ type: "step" });
    },
    onReplay: () => {
        dispatch({ type: "replay" });
    },
    onSpeedChange: (speed) => {
        dispatch({ type: "setSpeed", speed });
    },
    onScenarioSelect: (scenarioId) => {
        dispatch({ type: "selectScenario", scenarioId });
    },
    onNodeInspect: inspectNode,
    onViewReset: resetView,
    onCameraView: (cameraView) => {
        webglRequested = true;
        if (scene === null) mountScene();
        scene?.setView(cameraView);
        for (const button of document.querySelectorAll<HTMLButtonElement>(
            "button[data-camera-view]",
        )) {
            button.setAttribute(
                "aria-pressed",
                String(button.dataset.cameraView === cameraView),
            );
        }
    },
    onCameraMode: (followStage) => {
        scene?.setFollowStage(followStage);
    },
    onSceneResize: () => {
        scene?.resize();
    },
    onCopy: () => {
        void copyFinalResponse();
    },
});

function mountScene(): void {
    if (!webglRequested) {
        view.setSceneAvailable(false);
        return;
    }
    scene = createFusionScene(view.sceneContainer, {
        reducedMotion,
        onNodeSelect: inspectNode,
        onLabelsProject: view.projectLabels,
        onPacketsProject: view.projectPackets,
        onContextLost: () => {
            if (disposed) {
                return;
            }
            const lostScene = scene;
            scene = null;
            lostScene?.dispose();
            view.setSceneAvailable(false);
        },
    });
    view.setSceneAvailable(scene !== null);
    syncScene(null);
}

function handleVisibilityChange(): void {
    if (document.hidden) {
        cancelScheduledTick();
    } else {
        scheduleNextTick();
    }
}

function handlePageHide(event: PageTransitionEvent): void {
    cancelScheduledTick();
    if (!event.persisted) {
        teardown();
    }
}

function handlePageShow(event: PageTransitionEvent): void {
    if (event.persisted && !disposed) {
        scene?.resize();
        scheduleNextTick();
    }
}

function handleMotionChange(event: MediaQueryListEvent): void {
    if (disposed) {
        return;
    }
    reducedMotion = event.matches;
    cancelScheduledTick();
    if (reducedMotion && state.status === "playing") {
        dispatch({ type: "pause" });
    }
    view.setReducedMotion(reducedMotion);
    view.update(state);
    scene?.dispose();
    scene = null;
    mountScene();
    scheduleNextTick();
}

function handleViewportChange(): void {
    if (disposed) return;
    if (window.innerWidth <= 700 && scene !== null) {
        webglRequested = false;
        scene.dispose();
        scene = null;
        view.setSceneAvailable(false);
    } else if (window.innerWidth > 700 && !webglRequested) {
        webglRequested = true;
        mountScene();
    }
}

function handleDocumentScroll(): void {
    const bounds = document
        .querySelector(".transport")
        ?.getBoundingClientRect();
    if (bounds !== undefined) view.setDockVisible(bounds.bottom < 0);
}

function setupObservers(): void {
    handleDocumentScroll();
    if (typeof IntersectionObserver === "undefined") return;
    const transport = document.querySelector(".transport");
    if (transport !== null) {
        dockObserver = new IntersectionObserver((entries) => {
            const entry = entries[entries.length - 1];
            if (entry !== undefined) {
                view.setDockVisible(
                    !entry.isIntersecting &&
                        entry.boundingClientRect.bottom < 0,
                );
            }
        });
        dockObserver.observe(transport);
    }
    const sections = document.querySelectorAll<HTMLElement>(".paper-section");
    sectionObserver = new IntersectionObserver(
        (entries) => {
            for (const entry of entries) {
                if (!entry.isIntersecting) continue;
                const index = Array.from(sections).indexOf(
                    entry.target as HTMLElement,
                );
                if (index >= 0) view.setActiveFigure(index);
            }
        },
        { rootMargin: "-18% 0px -68% 0px" },
    );
    for (const section of sections) sectionObserver.observe(section);
}

function teardown(): void {
    if (disposed) {
        return;
    }
    disposed = true;
    copyOperation += 1;
    cancelScheduledTick();
    dockObserver?.disconnect();
    sectionObserver?.disconnect();
    document.removeEventListener("visibilitychange", handleVisibilityChange);
    window.removeEventListener("pagehide", handlePageHide);
    window.removeEventListener("pageshow", handlePageShow);
    window.removeEventListener("resize", handleViewportChange);
    window.removeEventListener("scroll", handleDocumentScroll);
    motionPreference.removeEventListener("change", handleMotionChange);
    scene?.dispose();
    scene = null;
}

document.addEventListener("visibilitychange", handleVisibilityChange);
window.addEventListener("pagehide", handlePageHide);
window.addEventListener("pageshow", handlePageShow);
window.addEventListener("resize", handleViewportChange, { passive: true });
window.addEventListener("scroll", handleDocumentScroll, { passive: true });
motionPreference.addEventListener("change", handleMotionChange);

setupObservers();
view.update(state);
mountScene();
