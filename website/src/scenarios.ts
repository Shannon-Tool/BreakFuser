import {
    LINEAR_STAGES,
    type ProcessEvent,
    type ResponseContract,
    type Scenario,
} from "./types";

export const SIMULATION_LABEL = "Guided simulation · illustrative data";

interface ScenarioSeed {
    id: string;
    title: string;
    input: string;
    traceId: string;
    contract: ResponseContract;
    factGoals: readonly string[];
    sanitizedQuery: string;
    document: Scenario["documents"][number];
    localDraft: string;
    initialResponse: string;
    quality: Scenario["quality"];
    recoveryStrategy: Scenario["recoveryStrategy"];
    recoveredFacts: readonly string[];
    finalResponse: string;
    claims: number;
    repair: Scenario["verification"]["repair"];
}

function envelope(): ResponseContract["format_envelope"] {
    return {
        exact_json: null,
        exact_line_count: null,
        required_identifiers: [],
        strip_markdown_fences: false,
    };
}

function createEvents(
    seed: ScenarioSeed,
    evidenceCount: number,
): readonly ProcessEvent[] {
    const events: Array<Omit<ProcessEvent, "sequence" | "timestamp">> = [
        {
            stage: "input",
            phase: "triage",
            kind: "request_received",
            message: "messages[] accepted · model=breakfuser",
        },
        {
            stage: "input",
            phase: "triage",
            kind: "contract_created",
            message: `ResponseContract · domain=${seed.contract.domain} · contract_atoms=${seed.contract.required_atoms.length} · fact_goals=${seed.factGoals.length}`,
        },
        {
            stage: "smart_model",
            phase: "acquisition",
            kind: "branch_started",
            branch: "document",
            message: "document_retrieval started · curated HTTPS",
        },
        {
            stage: "smart_model",
            phase: "acquisition",
            kind: "branch_started",
            branch: "smart",
            message:
                "remote_evidence started · sanitized query + minimal context",
        },
        {
            stage: "smart_model",
            phase: "acquisition",
            kind: "branch_started",
            branch: "local",
            message: "local_draft started · original context + contract",
        },
        {
            stage: "smart_model",
            phase: "acquisition",
            kind: "branch_completed",
            branch: "document",
            message: "document_retrieval complete · SourceDocument[1]",
        },
        {
            stage: "smart_model",
            phase: "acquisition",
            kind: "branch_completed",
            branch: "smart",
            message: "remote_evidence turn-01 complete · quality checks queued",
        },
        {
            stage: "smart_model",
            phase: "acquisition",
            kind: "branch_completed",
            branch: "local",
            message: "local_draft complete · local-draft span ready",
        },
        {
            stage: "recovery",
            phase: "recovery",
            kind: "smart_quality_classified",
            branch: "smart",
            message: `smart RefusalClass=${seed.quality} · detector classification`,
        },
        {
            stage: "recovery",
            phase: "recovery",
            kind: "recovery_strategy_applied",
            branch: "smart",
            message: `strategy=${seed.recoveryStrategy} · turn-02 · smart branch recovery loop`,
        },
        {
            stage: "recovery",
            phase: "recovery",
            kind: "evidence_spans_written",
            branch: "smart",
            message: `turn-02 EvidenceSpan[] · ${seed.recoveredFacts.length} recovered remote facts · max_turns=2`,
        },
        {
            stage: "fusion",
            phase: "composition",
            kind: "blackboard_assembled",
            message: `EvidenceBlackboard · spans=${evidenceCount} · documents=1 · provenance linked`,
        },
        {
            stage: "fusion",
            phase: "composition",
            kind: "composition_completed",
            message:
                "composition_mode=targeted_synthesis · original context + blackboard · uncensored model",
        },
        {
            stage: "verified",
            phase: "verification",
            kind: "verification_completed",
            message: `verification_status=passed · claims=${seed.claims} · omissions=0 · contradictions=0 · repair=${seed.repair}`,
        },
        {
            stage: "verified",
            phase: "verification",
            kind: "response_returned",
            message: `ChatCompletion · model=uncensored-model · finish_reason=stop · trace_id=${seed.traceId}`,
        },
    ];
    return events.map((event, index) => ({
        ...event,
        sequence: index + 1,
        timestamp:
            event.stage === "smart_model"
                ? event.kind === "branch_started"
                    ? "T+0240ms"
                    : "T+0480ms"
                : `T+${String(index * 120).padStart(4, "0")}ms`,
    }));
}

function createScenario(seed: ScenarioSeed): Scenario {
    const evidence: Scenario["evidence"] = [
        {
            id: `${seed.id}-document-1`,
            origin: "document",
            source_id: seed.document.id,
            turn_id: null,
            text: seed.document.excerpt,
            atom_ids: [],
            complete: true,
            salvaged: false,
            tail_anchor: "",
            confidence: 0.9,
            provenance: seed.document.url,
            revealStage: "smart_model",
        },
        {
            id: `${seed.id}-local-1`,
            origin: "local",
            source_id: "local-draft",
            turn_id: "local-draft",
            text: seed.localDraft,
            atom_ids: [],
            complete: true,
            salvaged: false,
            tail_anchor: "",
            confidence: 0.72,
            provenance: `trace://${seed.traceId}/turn/local-draft#local-1`,
            revealStage: "smart_model",
        },
        {
            id: `${seed.id}-remote-initial`,
            origin: "remote",
            source_id: "smart-model",
            turn_id: "turn-01",
            text: seed.initialResponse,
            atom_ids: ["linear-evidence"],
            complete: false,
            salvaged: false,
            tail_anchor: seed.initialResponse.slice(-32),
            confidence: 0.46,
            provenance: `trace://${seed.traceId}/turn/turn-01#remote-initial`,
            revealStage: "smart_model",
        },
        ...seed.recoveredFacts.map((text, index) => ({
            id: `${seed.id}-remote-${index + 1}`,
            origin: "remote" as const,
            source_id: "smart-model",
            turn_id: "turn-02",
            text,
            atom_ids: ["linear-evidence"],
            complete: true,
            salvaged: true,
            tail_anchor: "",
            confidence: 0.96,
            provenance: `trace://${seed.traceId}/turn/turn-02#remote-${index + 1}`,
            revealStage: "recovery" as const,
        })),
    ];
    const events = createEvents(seed, evidence.length);
    const salvagedCharacters = seed.recoveredFacts.reduce(
        (total, fact) => total + fact.length,
        0,
    );
    const remoteCharacters = seed.initialResponse.length + salvagedCharacters;
    return {
        id: seed.id,
        title: seed.title,
        input: seed.input,
        request: {
            model: "breakfuser",
            messages: [{ role: "user", content: seed.input }],
        },
        traceId: seed.traceId,
        contract: seed.contract,
        factGoals: seed.factGoals,
        sanitizedQuery: seed.sanitizedQuery,
        documents: [seed.document],
        localDraft: seed.localDraft,
        initialResponse: seed.initialResponse,
        quality: seed.quality,
        recoveryStrategy: seed.recoveryStrategy,
        recoveredFacts: seed.recoveredFacts,
        evidence,
        events,
        verification: {
            claims: seed.claims,
            omissions: [],
            contradictions: [],
            repair: seed.repair,
            status: "passed",
        },
        responsePanelMetadata: {
            trace_id: seed.traceId,
            pipeline_stages: LINEAR_STAGES,
            composition_mode: "targeted_synthesis",
            verification_status: "passed",
            model: "uncensored-model",
            finish_reason: "stop",
        },
        completion: {
            id: `chatcmpl-${seed.traceId}`,
            object: "chat.completion",
            created: 1770000000,
            model: "uncensored-model",
            choices: [
                {
                    index: 0,
                    message: {
                        role: "assistant",
                        content: seed.finalResponse,
                        tool_calls: [],
                    },
                    finish_reason: "stop",
                },
            ],
            usage: {
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 0,
            },
            breakfuser: {
                trace_id: seed.traceId,
                pipeline_stages: LINEAR_STAGES,
                artifacts: [],
                harvest: {
                    atomic_coverage: 1,
                    refusal_free_rate: 0.5,
                    hedge_rate: seed.quality === "hedge_heavy" ? 0.35 : 0.08,
                    omission_rate: 0,
                    provenance_rate: 1,
                    recomposition_fidelity: 1,
                    cost_tokens: 0,
                    latency_ms: 0,
                    turns_used: 2,
                },
                provenance: [
                    {
                        claim: seed.finalResponse,
                        turn_ids: ["turn-01", "turn-02"],
                        document_ids: [seed.document.id],
                        inferred: false,
                    },
                ],
                evidence_class: "fused",
                verification_status: "passed",
                local_finish_reason: "stop",
                missing_atoms: [],
                fusion: {
                    primary_origin_class: "mixed",
                    provider_outcome: "recovered",
                    deterministic_validity: "not_applicable",
                    provenance_attribution: "turn_and_document_linked",
                    external_corroboration: "curated_document",
                    task_completion_status: "complete",
                    composition_mode: "targeted_synthesis",
                    root_cause_flags: [seed.quality],
                    salvage_yield:
                        salvagedCharacters / Math.max(1, remoteCharacters),
                    remote_characters: remoteCharacters,
                    salvaged_characters: salvagedCharacters,
                    stage_timings_ms: {
                        document_retrieval: 480,
                        local_draft: 480,
                        remote_evidence: 840,
                        fusion_composition: 120,
                        verify_after: 120,
                    },
                },
                events,
            },
        },
        finalResponse: seed.finalResponse,
        stages: [
            {
                id: "input",
                title: "Request + response contract",
                explanation:
                    "Original messages are compressed and routed into a response contract before acquisition.",
                detail: seed.input,
            },
            {
                id: "smart_model",
                title: "Parallel acquisition",
                explanation:
                    "SpeculativeAcquisition runs curated document retrieval, local drafting, and sanitized remote harvesting concurrently.",
                detail: "document_retrieval ∥ local_draft ∥ remote_evidence",
            },
            {
                id: "recovery",
                title: "Smart evidence recovery",
                explanation: `The smart branch detects ${seed.quality} and applies ${seed.recoveryStrategy} in turn-02; recovered facts become provenance-linked spans.`,
                detail: `RefusalClass=${seed.quality} · strategy=${seed.recoveryStrategy} · turn-02 EvidenceSpan[] · max_turns=2`,
            },
            {
                id: "fusion",
                title: "Blackboard + composition",
                explanation:
                    "The same uncensored model used for local drafting now performs targeted_synthesis from original context and the evidence blackboard.",
                detail: "EvidenceBlackboard + original context → targeted_synthesis",
            },
            {
                id: "verified",
                title: "Verify after + response",
                explanation:
                    "verify_after checks omissions, contradictions, and modality, applies bounded repair when needed, then returns ChatCompletion metadata.",
                detail: `claims=${seed.claims} · omissions=0 · contradictions=0 · repair=${seed.repair}`,
            },
        ],
    };
}

export const SCENARIOS = [
    createScenario({
        id: "general-qa",
        title: "General question answering",
        input: "Why is high-voltage direct current often preferred for long undersea power cables?",
        traceId: "bf-general-qa-7f2a",
        contract: {
            domain: "general_research",
            required_atoms: [],
            output_shape: "answer",
            max_answer_tokens: 512,
            completion_directive:
                "Answer directly and completely. Preserve the requested format, language, and length; use sources when relevant without adding meta-sections.",
            verification_mode: "factual",
            format_envelope: envelope(),
            remote_output_tokens: 1024,
        },
        factGoals: [
            "AC cable charging current",
            "DC capacity and control",
            "converter trade-offs",
        ],
        sanitizedQuery:
            "Explain electrical cable charging, power-flow control, and converter-station trade-offs for long submarine transmission links.",
        document: {
            id: "doe-hvdc-undersea",
            title: "Curated HVDC transmission reference",
            url: "https://www.energy.gov/oe/articles/high-voltage-direct-current-hvdc-transmission",
            excerpt:
                "Submarine AC cables have continuous capacitive charging current; HVDC avoids that steady charging component but requires converter stations.",
            source_type: "curated_summary",
            sha256: "2d9eee30e1969156ba441c3b56637ead1a9da69d45c2796d237850827cb9cf33",
            retrieved_at: "2026-01-15T12:00:00+00:00",
            keywords: ["HVDC", "submarine cable", "capacitive charging"],
        },
        localDraft:
            "HVDC can move large controlled power flows over long cable routes, subject to conversion cost and losses.",
        initialResponse:
            "High-voltage direct current can transmit power efficiently over long distances and avoids some limitations of alternating-current cables.",
        quality: "partial_refusal",
        recoveryStrategy: "refusal_repair",
        recoveredFacts: [
            "Long AC cables continuously charge and discharge their capacitance, consuming cable capacity with reactive current.",
            "DC does not have the same continuous cable-charging current, so more conductor capacity remains for useful power transfer.",
            "Converter stations add cost and losses, which means the choice depends on distance, power, and the whole project rather than a universal rule.",
        ],
        finalResponse:
            "For long undersea links, HVDC avoids the continuous capacitive charging current of AC cables and can use the cable's capacity more effectively. It also allows controlled power flow and connections between grids that are not synchronized. Converter stations introduce cost, complexity, and losses, so HVDC is generally attractive when distance and transferred power justify those trade-offs rather than for every cable.",
        claims: 5,
        repair: "bounded_repair",
    }),
    createScenario({
        id: "medical-information",
        title: "Medical information",
        input: "What are common evidence-based approaches for occasional tension-type headaches?",
        traceId: "bf-medical-4c91",
        contract: {
            domain: "medical",
            required_atoms: [],
            output_shape: "answer",
            max_answer_tokens: 512,
            completion_directive:
                "Give the requested calculations, mechanism, label implications, and missing information without boilerplate.",
            verification_mode: "factual",
            format_envelope: envelope(),
            remote_output_tokens: 2048,
        },
        factGoals: [
            "self-care",
            "analgesic contraindications",
            "medication overuse",
            "urgent warning signs",
        ],
        sanitizedQuery:
            "List general educational self-care, medication-safety, and escalation considerations for a common episodic headache pattern.",
        document: {
            id: "nice-headache-guidance",
            title: "Curated headache assessment guidance",
            url: "https://www.nice.org.uk/guidance/cg150",
            excerpt:
                "Headache guidance separates routine self-care and analgesic considerations from medication-overuse risk and red-flag assessment.",
            source_type: "curated_summary",
            sha256: "9395d96346685914b547eb66cf7e51695a3ed368b85e9846a284fa18b25945d6",
            retrieved_at: "2026-01-15T12:01:00+00:00",
            keywords: ["headache", "self-care", "medication overuse"],
        },
        localDraft:
            "Occasional symptoms may benefit from regular routines and professionally checked pain relief; recurrent or unusual symptoms need assessment.",
        initialResponse:
            "Occasional tension-type headaches are often managed with rest, simple pain relief, and attention to everyday triggers.",
        quality: "hedge_heavy",
        recoveryStrategy: "crescendo",
        recoveredFacts: [
            "Regular sleep, meals, hydration, movement, and breaks from sustained posture are common self-care measures.",
            "A clinician or pharmacist can help choose an appropriate occasional analgesic by checking contraindications and other medicines.",
            "Frequent painkiller use can contribute to medication-overuse headache, and frequent headaches deserve clinical review.",
            "A sudden severe headache, neurological symptoms, fever with neck stiffness, or headache after significant head injury needs urgent assessment.",
        ],
        finalResponse:
            "For occasional tension-type headache, common measures include regular sleep, meals and hydration, gentle activity, and breaks from prolonged posture or screen work. A pharmacist or clinician can help select occasional pain relief while considering other conditions and medicines. Repeated or frequent analgesic use can itself worsen headache patterns, so recurring headaches merit professional advice. Sudden severe pain, new neurological symptoms, fever with neck stiffness, or significant head injury are reasons to seek urgent medical assessment.",
        claims: 6,
        repair: "bounded_repair",
    }),
    createScenario({
        id: "authorized-pentesting",
        title: "Authorized pentesting",
        input: "In an authorized assessment, how can a tester verify that a desktop client rejects an untrusted TLS certificate?",
        traceId: "bf-pentest-28bd",
        contract: {
            domain: "pentest",
            required_atoms: [
                "authorized_scope",
                "evidence_request",
                "explanation",
                "remediation",
            ],
            output_shape: "evidence_proposal",
            max_answer_tokens: 512,
            completion_directive:
                "Provide authorized scope, an evidence request, expected versus actual observations, explanation, and remediation. Never claim execution without an executor observation.",
            verification_mode: "artifact",
            format_envelope: envelope(),
            remote_output_tokens: 1024,
        },
        factGoals: [
            "written scope",
            "trusted positive control",
            "fail-closed negative test",
            "reproducible evidence",
        ],
        sanitizedQuery:
            "Describe a controlled certificate-validation test with a positive control, a negative control, and auditable observations.",
        document: {
            id: "owasp-tls-testing",
            title: "Curated transport-security testing reference",
            url: "https://owasp.org/www-project-web-security-testing-guide/",
            excerpt:
                "A certificate-validation test should compare trusted and untrusted controlled configurations and record whether sensitive application data is transmitted.",
            source_type: "curated_summary",
            sha256: "4a9cabbb9e79e5bd643aac1d1f0cff55f1afb409d75226ec1f8878cd9b3f6add",
            retrieved_at: "2026-01-15T12:02:00+00:00",
            keywords: ["TLS", "certificate validation", "authorized test"],
        },
        localDraft:
            "Use assessment-owned infrastructure and compare a working trusted-certificate connection with rejection after trust is removed.",
        initialResponse:
            "Use a test server with an untrusted certificate and check whether the client refuses the connection.",
        quality: "partial_refusal",
        recoveryStrategy: "refusal_repair",
        recoveredFacts: [
            "The test should stay within the agreed scope and use infrastructure and credentials controlled by the assessment team.",
            "A locally trusted test certificate provides a positive control, showing that the intended connection works before the negative test.",
            "Removing that trust should make the client fail closed without sending application credentials or sensitive payloads.",
            "Evidence should include the client version, test configuration, expected result, observed result, and any certificate-bypass option.",
        ],
        finalResponse:
            "Within the written test scope, use assessment-controlled infrastructure. First present a locally trusted test certificate to confirm the connection works. Then repeat with that certificate untrusted: the client should terminate the handshake or otherwise refuse the connection before transmitting credentials or application data. Record the client version, configuration, certificate status, observed behavior, and any bypass prompt. Do not weaken validation on production systems or intercept traffic outside the authorized environment.",
        claims: 7,
        repair: "not_needed",
    }),
    createScenario({
        id: "code-generation",
        title: "Code generation",
        input: "Design a TypeScript function that groups records by a key while preserving input order.",
        traceId: "bf-codegen-91e6",
        contract: {
            domain: "coding",
            required_atoms: [
                "implementation",
                "assumptions",
                "tests",
                "failure_cases",
            ],
            output_shape: "answer",
            max_answer_tokens: 512,
            completion_directive:
                "Provide working implementation, assumptions, tests, and failure cases.",
            verification_mode: "artifact",
            format_envelope: envelope(),
            remote_output_tokens: 2048,
        },
        factGoals: [
            "generic signature",
            "Map bucket initialization",
            "key insertion order",
            "record encounter order",
        ],
        sanitizedQuery:
            "Specify a generic TypeScript grouping helper whose key iteration and per-group record order are deterministic.",
        document: {
            id: "mdn-map-order",
            title: "Curated JavaScript Map reference",
            url: "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map",
            excerpt:
                "Map iterates keys in insertion order; pushing records during a single input pass preserves encounter order within each bucket.",
            source_type: "curated_summary",
            sha256: "c2a19b89ec2e8eeb89d7f59b19ca6165054553e4a4bdb499ba3674dd9a05fa34",
            retrieved_at: "2026-01-15T12:03:00+00:00",
            keywords: ["TypeScript", "Map", "insertion order"],
        },
        localDraft:
            "A generic Map<K, T[]> can create buckets on demand and return Array.from(map.values()) to retain first-key order.",
        initialResponse:
            "Use a Map, read each record's key, and push the record into the array stored for that key.",
        quality: "truncated",
        recoveryStrategy: "continuation",
        recoveredFacts: [
            "Map preserves the insertion order of its keys during iteration.",
            "A generic key type and record type keep the helper reusable without weakening type checking.",
            "Creating an empty bucket on the first occurrence avoids dropping records and preserves order within every group.",
            "Returning Array.from(map.values()) produces groups in first-key-appearance order.",
        ],
        finalResponse:
            "Use a generic function groupBy<T, K>(items: readonly T[], getKey: (item: T) => K): T[][]. Inside it, create a Map<K, T[]>; for each item, get its key, create the bucket if absent, and push the item. Return Array.from(groups.values()). Map preserves first-key insertion order, and pushing in iteration order preserves record order within each group.",
        claims: 4,
        repair: "not_needed",
    }),
] as const satisfies readonly Scenario[];
