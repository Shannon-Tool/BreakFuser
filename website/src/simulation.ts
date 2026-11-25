import {
    STAGE_IDS,
    type EvidenceRecord,
    type ProcessEvent,
    type Scenario,
    type SimulationState,
} from "./types";

export type SimulationAction =
    | { type: "play" }
    | { type: "pause" }
    | { type: "tick" }
    | { type: "step" }
    | { type: "setSpeed"; speed: SimulationState["speed"] }
    | { type: "replay" }
    | { type: "selectScenario"; scenarioId: string };

export function createInitialState(scenarioId: string): SimulationState {
    return { scenarioId, stageIndex: 0, status: "idle", speed: 1 };
}

export function getVisibleEvents(
    scenario: Scenario,
    state: SimulationState,
): readonly ProcessEvent[] {
    return scenario.events.filter(
        (event) => STAGE_IDS.indexOf(event.stage) <= state.stageIndex,
    );
}

export function getVisibleEvidence(
    scenario: Scenario,
    state: SimulationState,
): readonly EvidenceRecord[] {
    return scenario.evidence.filter(
        (record) => STAGE_IDS.indexOf(record.revealStage) <= state.stageIndex,
    );
}

function advance(state: SimulationState): SimulationState {
    const stageIndex = Math.min(state.stageIndex + 1, STAGE_IDS.length - 1);
    const status =
        stageIndex === STAGE_IDS.length - 1 ? "complete" : state.status;

    return { ...state, stageIndex, status };
}

export interface FigureState {
    request: Scenario["request"];
    contract: Scenario["contract"];
    acquisition: readonly {
        id: "document" | "smart" | "local";
        stage: string;
        status: "pending" | "complete";
        payload: string;
    }[];
    recovery: {
        owner: "smart";
        status: "pending" | "complete";
        quality: Scenario["quality"] | null;
        strategy: Scenario["recoveryStrategy"] | null;
        turns: readonly { id: "turn-01" | "turn-02"; text: string | null }[];
    };
    blackboard: {
        status: "pending" | "assembled";
        evidence: readonly EvidenceRecord[];
    };
    verification: {
        status: "pending" | "passed";
        result: Scenario["verification"] | null;
    };
    output: {
        status: "pending" | "ready";
        content: string | null;
        completion: Scenario["completion"] | null;
    };
    provenance: readonly {
        claim: string;
        turnIds: readonly string[];
        documentIds: readonly string[];
        inferred: boolean;
    }[];
}

export function getFigureState(
    scenario: Scenario,
    state: SimulationState,
): FigureState {
    const acquired = state.stageIndex >= 1;
    const recovered = state.stageIndex >= 2;
    const assembled = state.stageIndex >= 3;
    const outputReady = state.status === "complete" && state.stageIndex === 4;
    const evidence = getVisibleEvidence(scenario, state);
    return {
        request: scenario.request,
        contract: scenario.contract,
        acquisition: [
            {
                id: "document",
                stage: "document_retrieval",
                status: acquired ? "complete" : "pending",
                payload: "SourceDocument[]",
            },
            {
                id: "smart",
                stage: "remote_evidence",
                status: acquired ? "complete" : "pending",
                payload: "sanitized query · minimal context",
            },
            {
                id: "local",
                stage: "local_draft",
                status: acquired ? "complete" : "pending",
                payload: "original context + contract",
            },
        ],
        recovery: {
            owner: "smart",
            status: recovered ? "complete" : "pending",
            quality: recovered ? scenario.quality : null,
            strategy: recovered ? scenario.recoveryStrategy : null,
            turns: [
                {
                    id: "turn-01",
                    text: acquired ? scenario.initialResponse : null,
                },
                {
                    id: "turn-02",
                    text: recovered
                        ? scenario.recoveredFacts.join("\n\n")
                        : null,
                },
            ],
        },
        blackboard: {
            status: assembled ? "assembled" : "pending",
            evidence: assembled ? evidence : [],
        },
        verification: {
            status: outputReady ? "passed" : "pending",
            result: outputReady ? scenario.verification : null,
        },
        output: {
            status: outputReady ? "ready" : "pending",
            content: outputReady ? scenario.finalResponse : null,
            completion: outputReady ? scenario.completion : null,
        },
        provenance: outputReady
            ? scenario.completion.breakfuser.provenance.map((record) => ({
                  claim: record.claim,
                  turnIds: record.turn_ids,
                  documentIds: record.document_ids,
                  inferred: record.inferred,
              }))
            : [],
    };
}

export function transition(
    state: SimulationState,
    action: SimulationAction,
): SimulationState {
    switch (action.type) {
        case "play":
            return state.status === "idle" || state.status === "paused"
                ? { ...state, status: "playing" }
                : state;
        case "pause":
            return state.status === "playing"
                ? { ...state, status: "paused" }
                : state;
        case "tick":
            return state.status === "playing" ? advance(state) : state;
        case "step":
            return state.status === "idle" || state.status === "paused"
                ? advance(state)
                : state;
        case "setSpeed":
            return { ...state, speed: action.speed };
        case "replay":
            return createInitialState(state.scenarioId);
        case "selectScenario":
            return createInitialState(action.scenarioId);
    }
}
