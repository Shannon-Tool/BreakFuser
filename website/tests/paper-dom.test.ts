// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";

import { SCENARIOS } from "../src/scenarios";
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
        onCopy: vi.fn(),
    };
    const view = renderSimulator(root, true, actions);
    return { root, view, actions };
}

describe("interactive product launch", () => {
    it("pairs a bold launch message with seven live views and four examples", () => {
        const { root } = mount();
        expect(root.querySelectorAll("figure[data-figure]")).toHaveLength(7);
        expect(root.querySelectorAll(".scenario-select")).toHaveLength(4);
        expect(root.textContent).toContain("Any model.");
        expect(root.textContent).toContain("Uncensored.");
        expect(root.textContent).toContain("See BreakFuser in action");
        expect(root.textContent).toContain(
            "Guided simulation · illustrative data",
        );
        expect(root.textContent).toContain(
            "The brains you want. The freedom you need.",
        );
    });

    it("updates acquisition, recovery, provenance, and response from shared state", () => {
        const { root, view } = mount();
        let state = createInitialState(scenario.id);
        view.update(state);
        expect(
            root
                .querySelector("[data-figure='acquisition']")
                ?.getAttribute("data-state"),
        ).toBe("pending");
        expect(root.querySelectorAll(".recovery-turn")).toHaveLength(2);
        expect(root.querySelector(".output-text")?.textContent).not.toContain(
            scenario.finalResponse,
        );

        for (let index = 0; index < 4; index += 1) {
            state = transition(state, { type: "step" });
        }
        view.update(state);
        expect(
            root
                .querySelector("[data-figure='acquisition']")
                ?.getAttribute("data-state"),
        ).toBe("complete");
        expect(
            root
                .querySelector("[data-figure='recovery']")
                ?.getAttribute("data-state"),
        ).toBe("complete");
        expect(root.querySelectorAll(".provenance-claim")).toHaveLength(1);
        expect(root.querySelector(".output-text")?.textContent).toBe(
            scenario.finalResponse,
        );
        expect(
            root.querySelector(".verification-table")?.textContent,
        ).toContain("Passed");
    });

    it("offers schematic and 3D views plus accessible figure navigation", () => {
        const { root, actions } = mount();
        const top = root.querySelector<HTMLButtonElement>(
            "button[data-camera-view='top']",
        );
        expect(top).not.toBeNull();
        top?.click();
        expect(actions.onCameraView).toHaveBeenCalledWith("top");
        expect(root.querySelectorAll("nav.paper-contents a")).toHaveLength(7);
        expect(
            root.querySelector(".scene-fallback img")?.getAttribute("alt"),
        ).toContain("Evidence blackboard");
    });
});
