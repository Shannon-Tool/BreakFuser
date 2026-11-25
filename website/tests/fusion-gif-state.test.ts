import { describe, expect, it } from "vitest";

import { RECORDINGS, recordingById, scenarioById } from "../src/gif/recordings";
import { buildSpecializedScene, sceneKindFor } from "../src/gif/scene-kinds";
import {
    createRecordingModel,
    recordingDuration,
    STEP_DURATIONS,
    timelineAt,
    TOTAL_DURATION,
} from "../src/gif/state";

describe("README fusion recording registry", () => {
    it("defines exactly ten unique, valid, distinct recordings", () => {
        expect(RECORDINGS).toHaveLength(10);
        expect(new Set(RECORDINGS.map((recording) => recording.id)).size).toBe(
            10,
        );
        expect(
            new Set(RECORDINGS.map((recording) => recording.file)).size,
        ).toBe(10);
        expect(
            new Set(RECORDINGS.map((recording) => recording.view)).size,
        ).toBe(8);
        expect(
            new Set(RECORDINGS.map((recording) => sceneKindFor(recording.id)))
                .size,
        ).toBe(10);
        const geometrySignatures = new Set<string>();
        for (const recording of RECORDINGS) {
            const kind = sceneKindFor(recording.id);
            if (kind === "pipeline_graph") continue;
            const scene = buildSpecializedScene(
                kind,
                1,
                scenarioById(recording.scenarioId),
            );
            expect(scene.nodes.length).toBeGreaterThan(2);
            geometrySignatures.add(
                JSON.stringify({
                    kind,
                    nodes: scene.nodes.map((node) => [
                        node.kind,
                        node.position,
                        node.size,
                    ]),
                    camera: scene.camera,
                }),
            );
        }
        expect(geometrySignatures.size).toBe(9);
        for (const recording of RECORDINGS) {
            expect(scenarioById(recording.scenarioId)).toBeDefined();
            expect(recording.steps.length).toBeGreaterThanOrEqual(3);
            expect(recording.durations).toHaveLength(recording.steps.length);
            expect(recordingDuration(recording)).toBeGreaterThanOrEqual(10);
            expect(
                recording.steps.every((step) => step.cards.length >= 3),
            ).toBe(true);
        }
    });

    it("maps the three recovery GIFs to their exact scenarios and strategies", () => {
        for (const [id, scenarioId, quality, strategy] of [
            [
                "04-refusal-repair",
                "authorized-pentesting",
                "partial_refusal",
                "refusal_repair",
            ],
            [
                "05-medical-crescendo",
                "medical-information",
                "hedge_heavy",
                "crescendo",
            ],
            [
                "06-code-continuation",
                "code-generation",
                "truncated",
                "continuation",
            ],
        ] as const) {
            const recording = recordingById(id);
            const initial = createRecordingModel(0, recording);
            const recovered = createRecordingModel(1, recording);
            const output = createRecordingModel(2, recording);
            expect(initial.scenario.id).toBe(scenarioId);
            expect(initial.scenario.quality).toBe(quality);
            expect(recovered.contextValue).toContain(`strategy=${strategy}`);
            expect(recovered.outputText).toContain(
                initial.scenario.recoveredFacts[0],
            );
            expect(output.outputText).toBe(initial.scenario.finalResponse);
            expect(output.outputReady).toBe(true);
        }
    });

    it("makes concurrent acquisition explicit and preserves independent evidence origins", () => {
        const recording = recordingById("02-parallel-acquisition");
        const running = createRecordingModel(1, recording);
        expect(running.activeNodes).toEqual([
            "orchestrator",
            "documents",
            "smart",
            "local_draft",
        ]);
        expect(running.contextValue).toContain("all three started");
        expect(running.outputReady).toBe(false);
        const output = createRecordingModel(2, recording);
        expect(output.outputText).toContain("source_id=local-draft");
        expect(output.outputText).toContain("turn_id=turn-01");
        expect(output.outputText).toContain(
            "still require composition and verification",
        );
    });

    it("keeps composition ownership and output gates accurate", () => {
        const composition = recordingById("08-uncensored-composition");
        expect(createRecordingModel(0, composition).outputText).toContain(
            "remote_bypass=false",
        );
        expect(createRecordingModel(1, composition).outputText).toContain(
            "model_role=uncensored",
        );
        const verification = recordingById("09-verify-after");
        expect(createRecordingModel(0, verification).outputReady).toBe(false);
        expect(createRecordingModel(1, verification).outputReady).toBe(false);
        expect(createRecordingModel(2, verification).outputText).toBe(
            scenarioById("general-qa").finalResponse,
        );
    });

    it("uses exact blackboard provenance values", () => {
        const recording = recordingById("07-evidence-blackboard");
        const model = createRecordingModel(2, recording);
        expect(model.outputText).toContain(
            `evidence_spans=${model.scenario.evidence.length}`,
        );
        expect(model.outputText).toContain("remote_turns=turn-01,turn-02");
        expect(model.outputText).toContain("local_turn=local-draft");
        expect(model.outputText).toContain("provenance_rate=1.00");
    });

    it("clamps keyframes and steps through each timeline", () => {
        const overview = recordingById("01-input-process-output");
        expect(createRecordingModel(-2, overview).step).toBe(0);
        expect(createRecordingModel(20, overview).step).toBe(4);
        let start = 0;
        for (const [step, duration] of STEP_DURATIONS.entries()) {
            expect(timelineAt(start)).toEqual({ step, localTime: 0 });
            const frame = timelineAt(start + duration / 2);
            expect(frame.step).toBe(step);
            expect(frame.localTime).toBeCloseTo(duration / 2, 10);
            start += duration;
        }
        expect(start).toBe(TOTAL_DURATION);
        expect(timelineAt(TOTAL_DURATION)).toEqual({ step: 0, localTime: 0 });
    });
});
