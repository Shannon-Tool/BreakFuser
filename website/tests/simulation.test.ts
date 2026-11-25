import { describe, expect, it } from "vitest";

import * as simulationModule from "../src/simulation";
import { SCENARIOS } from "../src/scenarios";
import {
    createInitialState,
    transition,
    type SimulationAction,
} from "../src/simulation";
import type { SimulationState } from "../src/types";

const scenarioId = SCENARIOS[0]?.id ?? "missing-scenario";

function playingState(): SimulationState {
    return transition(createInitialState(scenarioId), { type: "play" });
}

function run(
    state: SimulationState,
    actions: readonly SimulationAction[],
): SimulationState {
    return actions.reduce(
        (current, action) => transition(current, action),
        state,
    );
}

function repeat(action: SimulationAction, count: number): SimulationAction[] {
    return Array.from({ length: count }, () => action);
}

describe("simulation state machine", () => {
    it("starts idle at the input stage with normal speed", () => {
        expect(createInitialState(scenarioId)).toEqual({
            scenarioId,
            stageIndex: 0,
            status: "idle",
            speed: 1,
        });
    });

    it("progresses through all five stages in order and completes", () => {
        let state = playingState();
        const visitedIndexes = [state.stageIndex];

        for (let index = 0; index < 4; index += 1) {
            state = transition(state, { type: "tick" });
            visitedIndexes.push(state.stageIndex);
        }

        expect(visitedIndexes).toEqual([0, 1, 2, 3, 4]);
        expect(state).toEqual({
            scenarioId,
            stageIndex: 4,
            status: "complete",
            speed: 1,
        });
    });

    it("does not advance while idle", () => {
        const initial = createInitialState(scenarioId);

        expect(transition(initial, { type: "tick" })).toEqual(initial);
    });

    it("keeps a paused simulation stable across ticks", () => {
        const paused = run(playingState(), [
            { type: "tick" },
            { type: "pause" },
        ]);

        expect(paused).toMatchObject({ stageIndex: 1, status: "paused" });
        expect(transition(paused, { type: "tick" })).toEqual(paused);
    });

    it("steps once while paused without resuming playback", () => {
        const paused = transition(playingState(), { type: "pause" });

        expect(transition(paused, { type: "step" })).toEqual({
            scenarioId,
            stageIndex: 1,
            status: "paused",
            speed: 1,
        });
    });

    it("steps from idle without starting autonomous playback", () => {
        expect(
            transition(createInitialState(scenarioId), { type: "step" }),
        ).toEqual({
            scenarioId,
            stageIndex: 1,
            status: "idle",
            speed: 1,
        });
    });

    it("completes when a paused simulation steps onto the verified stage", () => {
        const paused = transition(playingState(), { type: "pause" });
        const state = run(paused, repeat({ type: "step" }, 4));

        expect(state).toMatchObject({ stageIndex: 4, status: "complete" });
    });

    it.each([0.5, 1, 2] as const)("changes playback speed to %s", (speed) => {
        expect(
            transition(playingState(), { type: "setSpeed", speed }).speed,
        ).toBe(speed);
    });

    it("replays the same scenario from its initial idle state", () => {
        const completed = run(playingState(), [
            { type: "setSpeed", speed: 2 },
            ...repeat({ type: "tick" }, 4),
        ]);

        expect(transition(completed, { type: "replay" })).toEqual(
            createInitialState(scenarioId),
        );
    });

    it("keeps completion idempotent for playback, ticks, and steps", () => {
        const completed = run(playingState(), repeat({ type: "tick" }, 4));

        expect(transition(completed, { type: "tick" })).toEqual(completed);
        expect(transition(completed, { type: "step" })).toEqual(completed);
        expect(transition(completed, { type: "play" })).toEqual(completed);
        expect(transition(completed, { type: "pause" })).toEqual(completed);
    });

    it("resets playback when selecting another curated scenario", () => {
        const nextScenario = SCENARIOS[1]?.id ?? "missing-scenario";
        const progressed = run(playingState(), [
            { type: "tick" },
            { type: "setSpeed", speed: 2 },
        ]);

        expect(
            transition(progressed, {
                type: "selectScenario",
                scenarioId: nextScenario,
            }),
        ).toEqual(createInitialState(nextScenario));
    });
});

describe("stage-gated live trace", () => {
    it("reveals ordered events by stage while keeping parallel branches in acquisition", () => {
        const scenario = SCENARIOS[0];
        if (scenario === undefined) {
            throw new Error("A curated scenario is required");
        }
        const helpers = simulationModule as unknown as {
            getVisibleEvents?: (
                value: typeof scenario,
                state: SimulationState,
            ) => Array<{ stage: string; phase: string; branch?: string }>;
            getVisibleEvidence?: (
                value: typeof scenario,
                state: SimulationState,
            ) => Array<{ origin: string; revealStage: string }>;
        };
        expect(helpers.getVisibleEvents).toBeTypeOf("function");
        expect(helpers.getVisibleEvidence).toBeTypeOf("function");
        if (
            helpers.getVisibleEvents === undefined ||
            helpers.getVisibleEvidence === undefined
        ) {
            return;
        }

        const input = createInitialState(scenario.id);
        expect(
            helpers
                .getVisibleEvents(scenario, input)
                .map((event) => event.stage),
        ).toEqual(["input", "input"]);
        expect(helpers.getVisibleEvidence(scenario, input)).toEqual([]);

        const acquisition = transition(input, { type: "step" });
        const acquisitionEvents = helpers.getVisibleEvents(
            scenario,
            acquisition,
        );
        expect(
            acquisitionEvents
                .filter((event) => event.stage === "smart_model")
                .every((event) => event.phase === "acquisition"),
        ).toBe(true);
        expect(
            helpers
                .getVisibleEvidence(scenario, acquisition)
                .map((record) => record.origin),
        ).toEqual(expect.arrayContaining(["document", "local", "remote"]));

        const recovery = transition(acquisition, { type: "step" });
        expect(helpers.getVisibleEvents(scenario, recovery).at(-1)?.stage).toBe(
            "recovery",
        );
        expect(
            helpers
                .getVisibleEvidence(scenario, recovery)
                .filter((record) => record.revealStage === "recovery").length,
        ).toBe(scenario.recoveredFacts.length);
    });
});
