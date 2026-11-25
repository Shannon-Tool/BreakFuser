// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import { SCENARIOS } from "../src/scenarios";
import {
    createFusionWorld,
    disposeObjectResources,
    PALETTE,
    updateRouteParticles,
} from "../src/scene/geometry";
import { getStageCameraPreset } from "../src/scene/state";
import { createInitialState, transition } from "../src/simulation";
import { renderSimulator } from "../src/ui/render";

const scenario = SCENARIOS[0];
if (scenario === undefined) throw new Error("A curated scenario is required");

function mount() {
    const root = document.createElement("div");
    const actions = {
        onPlayPause: vi.fn(),
        onNextStep: vi.fn(),
        onReplay: vi.fn(),
        onSpeedChange: vi.fn(),
        onScenarioSelect: vi.fn(),
        onNodeInspect: vi.fn(),
        onViewReset: vi.fn(),
        onCameraView: vi.fn(),
        onCameraMode: vi.fn(),
        onSceneResize: vi.fn(),
        onCopy: vi.fn(),
    };
    const view = renderSimulator(root, true, actions);
    return { root, view, actions };
}

describe("marketing launch experience", () => {
    it("projects the selected request, branches, and output status into the live cover", () => {
        const { root, view } = mount();
        let state = createInitialState(scenario.id);
        view.update(state);
        expect(root.querySelector(".trace-cover")).not.toBeNull();
        expect(root.querySelector(".cover-request")?.textContent).toContain(
            scenario.input,
        );
        expect(
            root.querySelectorAll(".cover-branch[data-state='pending']"),
        ).toHaveLength(3);
        expect(root.querySelector(".cover-response")?.textContent).toContain(
            "Sealed",
        );

        for (let index = 0; index < 4; index += 1) {
            state = transition(state, { type: "step" });
            view.update(state);
        }
        expect(
            root.querySelectorAll(".cover-branch[data-state='complete']"),
        ).toHaveLength(3);
        expect(root.querySelector(".cover-response")?.textContent).toContain(
            "Verified",
        );
    });

    it("provides stage camera presets with distinct acquisition, recovery, composition, and response targets", () => {
        const acquisition = getStageCameraPreset("smart_model", 1.5);
        const recovery = getStageCameraPreset("recovery", 1.5);
        const composition = getStageCameraPreset("fusion", 1.5);
        const verified = getStageCameraPreset("verified", 1.5);
        expect(acquisition.target.x).toBeLessThan(composition.target.x);
        expect(recovery.zoom).toBeGreaterThan(acquisition.zoom);
        expect(verified.target.x).toBeGreaterThan(composition.target.x);
        expect(PALETTE.background).toBe(0x101b24);
    });

    it("exposes follow/free camera controls and an accessible focus figure dialog", () => {
        const { root, actions } = mount();
        const free = root.querySelector<HTMLButtonElement>(
            "button[data-camera-mode='free']",
        );
        free?.click();
        expect(actions.onCameraMode).toHaveBeenCalledWith(false);
        const focus = root.querySelector<HTMLButtonElement>(
            "button[data-action='focus-figure']",
        );
        const dialog = root.querySelector<HTMLDialogElement>(".focus-dialog");
        expect(dialog).not.toBeNull();
        focus?.click();
        expect(dialog?.hasAttribute("open")).toBe(true);
        expect(actions.onSceneResize).toHaveBeenCalled();
        const close = root.querySelector<HTMLButtonElement>(
            "button[data-action='close-focus']",
        );
        close?.click();
        expect(dialog?.hasAttribute("open")).toBe(false);
        expect(
            root.querySelector("#figure-1 .system-figure-body"),
        ).not.toBeNull();
    });

    it("keeps a short directional trail behind each named payload", () => {
        const world = createFusionWorld();
        try {
            const route = world.routes.request_to_orchestrator;
            expect(route.trail.geometry.getAttribute("position").count).toBe(4);
            updateRouteParticles(world, "request_to_orchestrator", 0.4);
            const trailPosition = route.trail.geometry.getAttribute("position");
            const expected = route.curve.getPointAt(0.382);
            expect(trailPosition.getX(0)).toBeCloseTo(expected.x);
            expect(trailPosition.getY(0)).toBeCloseTo(expected.y + 0.18);
            expect(trailPosition.getZ(0)).toBeCloseTo(expected.z);
        } finally {
            disposeObjectResources(world.root);
        }
    });

    it("uses one shared dock and scrollspy projection", () => {
        const { root, view } = mount();
        const dock = root.querySelector<HTMLElement>(".trace-dock");
        expect(dock).not.toBeNull();
        view.setDockVisible(true);
        expect(dock?.hidden).toBe(false);
        view.setDockVisible(false);
        expect(dock?.hidden).toBe(true);
        view.setActiveFigure(3);
        expect(
            root
                .querySelector("nav.paper-contents a[aria-current='location']")
                ?.getAttribute("href"),
        ).toBe("#figure-4");
    });
});
