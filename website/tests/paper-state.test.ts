import { describe, expect, it } from "vitest";

import { SCENARIOS } from "../src/scenarios";
import {
    createInitialState,
    getFigureState,
    transition,
} from "../src/simulation";

const scenario = SCENARIOS[0];
if (scenario === undefined) throw new Error("A curated scenario is required");

function atStage(count: number) {
    let state = createInitialState(scenario.id);
    for (let index = 0; index < count; index += 1) {
        state = transition(state, { type: "step" });
    }
    return state;
}

describe("shared research-paper figure state", () => {
    it("exposes the request and contract before acquisition begins", () => {
        const figure = getFigureState(scenario, atStage(0));
        expect(figure.request).toEqual(scenario.request);
        expect(figure.contract).toEqual(scenario.contract);
        expect(
            figure.acquisition.every((branch) => branch.status === "pending"),
        ).toBe(true);
        expect(figure.blackboard.status).toBe("pending");
        expect(figure.output.status).toBe("pending");
    });

    it("marks all three acquisition branches active together", () => {
        const figure = getFigureState(scenario, atStage(1));
        expect(figure.acquisition.map((branch) => branch.id)).toEqual([
            "document",
            "smart",
            "local",
        ]);
        expect(
            figure.acquisition.every((branch) => branch.status === "complete"),
        ).toBe(true);
        expect(figure.recovery.status).toBe("pending");
        expect(figure.blackboard.status).toBe("pending");
    });

    it("keeps recovery on the smart branch and limits the inline exchange to two turns", () => {
        const figure = getFigureState(scenario, atStage(2));
        expect(figure.recovery.status).toBe("complete");
        expect(figure.recovery.owner).toBe("smart");
        expect(figure.recovery.turns.map((turn) => turn.id)).toEqual([
            "turn-01",
            "turn-02",
        ]);
        expect(figure.recovery.quality).toBe(scenario.quality);
        expect(figure.recovery.strategy).toBe(scenario.recoveryStrategy);
        expect(figure.blackboard.status).toBe("pending");
    });

    it("assembles evidence only for composition and links claims after verification", () => {
        const composition = getFigureState(scenario, atStage(3));
        expect(composition.blackboard.status).toBe("assembled");
        expect(composition.blackboard.evidence).toHaveLength(
            scenario.evidence.length,
        );
        expect(composition.output.status).toBe("pending");
        expect(composition.provenance).toEqual([]);

        const verified = getFigureState(scenario, atStage(4));
        expect(verified.output.status).toBe("ready");
        expect(verified.output.content).toBe(scenario.finalResponse);
        expect(verified.verification.status).toBe("passed");
        expect(verified.provenance[0]?.turnIds).toEqual(["turn-01", "turn-02"]);
    });
});
