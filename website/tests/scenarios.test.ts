import { describe, expect, it } from "vitest";

import { SCENARIOS, SIMULATION_LABEL } from "../src/scenarios";
import { LINEAR_STAGES, STAGE_IDS } from "../src/types";

const EXPECTED_CONTRACTS = [
    {
        domain: "general_research",
        required_atoms: [],
        output_shape: "answer",
        max_answer_tokens: 512,
        verification_mode: "factual",
        remote_output_tokens: 1024,
        completion_directive:
            "Answer directly and completely. Preserve the requested format, language, and length; use sources when relevant without adding meta-sections.",
    },
    {
        domain: "medical",
        required_atoms: [],
        output_shape: "answer",
        max_answer_tokens: 512,
        verification_mode: "factual",
        remote_output_tokens: 2048,
        completion_directive:
            "Give the requested calculations, mechanism, label implications, and missing information without boilerplate.",
    },
    {
        domain: "pentest",
        required_atoms: [
            "authorized_scope",
            "evidence_request",
            "explanation",
            "remediation",
        ],
        output_shape: "evidence_proposal",
        max_answer_tokens: 512,
        verification_mode: "artifact",
        remote_output_tokens: 1024,
        completion_directive:
            "Provide authorized scope, an evidence request, expected versus actual observations, explanation, and remediation. Never claim execution without an executor observation.",
    },
    {
        domain: "coding",
        required_atoms: [
            "implementation",
            "assumptions",
            "tests",
            "failure_cases",
        ],
        output_shape: "answer",
        max_answer_tokens: 512,
        verification_mode: "artifact",
        remote_output_tokens: 2048,
        completion_directive:
            "Provide working implementation, assumptions, tests, and failure cases.",
    },
] as const;

describe("curated scenarios", () => {
    it("provides exactly the four required scenarios", () => {
        expect(SCENARIOS.map((scenario) => scenario.id)).toEqual([
            "general-qa",
            "medical-information",
            "authorized-pentesting",
            "code-generation",
        ]);
    });

    it.each(SCENARIOS)(
        "gives $title real-shaped request and response data",
        (scenario) => {
            expect(scenario.request).toEqual({
                model: "breakfuser",
                messages: [{ role: "user", content: scenario.input }],
            });
            expect(scenario.sanitizedQuery).not.toBe(scenario.input);
            expect(scenario.initialResponse.trim()).not.toBe("");
            expect(scenario.finalResponse.trim()).not.toBe("");
            expect(scenario.stages.map((stage) => stage.id)).toEqual(STAGE_IDS);
            expect(scenario.responsePanelMetadata).toEqual({
                trace_id: scenario.traceId,
                pipeline_stages: LINEAR_STAGES,
                composition_mode: "targeted_synthesis",
                verification_status: "passed",
                model: "uncensored-model",
                finish_reason: "stop",
            });
            expect(scenario.completion.model).toBe("uncensored-model");
            expect(scenario.completion.choices[0]?.finish_reason).toBe("stop");
            expect(scenario.completion.breakfuser.fusion.composition_mode).toBe(
                "targeted_synthesis",
            );
            expect(scenario.completion.breakfuser.local_finish_reason).toBe(
                "stop",
            );
            expect(scenario.completion.breakfuser).not.toHaveProperty("model");
            expect(scenario.completion.breakfuser).not.toHaveProperty(
                "finish_reason",
            );
            expect(scenario.completion.breakfuser).not.toHaveProperty(
                "composition_mode",
            );
        },
    );

    it.each(SCENARIOS)(
        "uses the backend ResponseContract for $title",
        (scenario) => {
            const expected = EXPECTED_CONTRACTS.find(
                (contract) => contract.domain === scenario.contract.domain,
            );
            expect(expected).toBeDefined();
            expect(scenario.contract).toEqual({
                ...expected,
                format_envelope: {
                    exact_json: null,
                    exact_line_count: null,
                    required_identifiers: [],
                    strip_markdown_fences: false,
                },
            });
            expect(Object.keys(scenario.contract).sort()).toEqual([
                "completion_directive",
                "domain",
                "format_envelope",
                "max_answer_tokens",
                "output_shape",
                "remote_output_tokens",
                "required_atoms",
                "verification_mode",
            ]);
            expect(scenario.factGoals.length).toBeGreaterThan(0);
        },
    );

    it.each(SCENARIOS)(
        "uses backend SourceDocument fields for $title",
        (scenario) => {
            expect(scenario.documents).toHaveLength(1);
            const document = scenario.documents[0];
            expect(document).toBeDefined();
            expect(Object.keys(document ?? {}).sort()).toEqual([
                "excerpt",
                "id",
                "keywords",
                "retrieved_at",
                "sha256",
                "source_type",
                "title",
                "url",
            ]);
            expect(document?.excerpt.trim()).not.toBe("");
            expect(document?.source_type).toBe("curated_summary");
            expect(document?.sha256).toMatch(/^[a-f0-9]{64}$/);
            expect(document?.retrieved_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
            expect(document?.keywords.length).toBeGreaterThan(0);
            expect(
                scenario.evidence.find((record) => record.origin === "document")
                    ?.text,
            ).toBe(document?.excerpt);
        },
    );

    it.each(SCENARIOS)(
        "limits $title to initial and one repair turn with backend spans",
        (scenario) => {
            const remote = scenario.evidence.filter(
                (record) => record.origin === "remote",
            );
            expect(new Set(remote.map((record) => record.turn_id))).toEqual(
                new Set(["turn-01", "turn-02"]),
            );
            const recovered = remote.filter(
                (record) => record.revealStage === "recovery",
            );
            expect(
                recovered.every((record) => record.turn_id === "turn-02"),
            ).toBe(true);
            expect(new Set(recovered.map((record) => record.id)).size).toBe(
                recovered.length,
            );
            expect(
                new Set(recovered.map((record) => record.provenance)).size,
            ).toBe(recovered.length);
            expect(recovered.map((record) => record.text)).toEqual(
                scenario.recoveredFacts,
            );
            for (const record of scenario.evidence) {
                expect(record).toHaveProperty("complete");
                expect(record).toHaveProperty("salvaged");
                expect(record).toHaveProperty("tail_anchor");
                expect(record).toHaveProperty("confidence");
                expect(record).toHaveProperty("atom_ids");
                expect(record).not.toHaveProperty("completeness");
                expect(record.confidence).toBeGreaterThan(0);
                expect(record.confidence).toBeLessThanOrEqual(1);
                expect(record.salvaged).toBe(
                    record.origin === "remote" &&
                        record.revealStage === "recovery",
                );
                expect(record.provenance).toMatch(/^(?:https|trace):/);
            }
        },
    );

    it("uses actual detector classes and appropriate inline recovery strategies", () => {
        expect(SCENARIOS.map((scenario) => scenario.quality)).toEqual([
            "partial_refusal",
            "hedge_heavy",
            "partial_refusal",
            "truncated",
        ]);
        expect(SCENARIOS.map((scenario) => scenario.recoveryStrategy)).toEqual([
            "refusal_repair",
            "crescendo",
            "refusal_repair",
            "continuation",
        ]);
        for (const scenario of SCENARIOS) {
            expect([
                "none",
                "hard_refusal",
                "partial_refusal",
                "hedge_heavy",
                "disclaimer_only",
                "truncated",
                "hallucination_suspected",
                "out_of_scope",
            ]).toContain(scenario.quality);
        }
    });

    it.each(SCENARIOS)(
        "records three concurrent acquisition branches for $title",
        (scenario) => {
            const acquisition = scenario.events.filter(
                (event) => event.stage === "smart_model",
            );
            expect(acquisition.slice(0, 3).map((event) => event.kind)).toEqual([
                "branch_started",
                "branch_started",
                "branch_started",
            ]);
            expect(acquisition.slice(3).map((event) => event.kind)).toEqual([
                "branch_completed",
                "branch_completed",
                "branch_completed",
            ]);
            expect(
                new Set(acquisition.slice(0, 3).map((event) => event.timestamp))
                    .size,
            ).toBe(1);
            for (const branch of ["document", "smart", "local"] as const) {
                const branchEvents = acquisition.filter(
                    (event) => event.branch === branch,
                );
                expect(branchEvents.map((event) => event.kind)).toEqual([
                    "branch_started",
                    "branch_completed",
                ]);
                expect(
                    branchEvents.every(
                        (event) => event.phase === "acquisition",
                    ),
                ).toBe(true);
            }
            expect(scenario.events.map((event) => event.sequence)).toEqual(
                scenario.events.map((_, index) => index + 1),
            );
            expect(
                scenario.events.some(
                    (event) => event.kind === "contract_created",
                ),
            ).toBe(true);
            expect(
                scenario.events.some(
                    (event) => event.kind === "smart_quality_classified",
                ),
            ).toBe(true);
            expect(
                scenario.events.some(
                    (event) => event.kind === "recovery_strategy_applied",
                ),
            ).toBe(true);
            expect(
                scenario.events.some(
                    (event) => event.kind === "composition_completed",
                ),
            ).toBe(true);
            expect(
                scenario.events.some(
                    (event) => event.kind === "verification_completed",
                ),
            ).toBe(true);
            expect(scenario.events.at(-1)?.message).toContain(scenario.traceId);
        },
    );

    it("labels the experience as guided and illustrative", () => {
        expect(SIMULATION_LABEL).toBe("Guided simulation · illustrative data");
        expect(LINEAR_STAGES).toEqual([
            "document_retrieval",
            "local_draft",
            "remote_evidence",
            "fusion_composition",
            "verify_after",
        ]);
    });
});
