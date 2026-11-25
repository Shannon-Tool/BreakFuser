import type { FusionNode, Scenario, StageId } from "../types";
import { SCENARIOS } from "../scenarios";
import type { FusionRouteId } from "../scene/geometry";

export type RecordingView =
    | "overview"
    | "acquisition"
    | "privacy"
    | "recovery"
    | "blackboard"
    | "composition"
    | "verification"
    | "delivery";

export interface RecordingCard {
    id: string;
    title: string;
    values: readonly (readonly [string, string])[];
}

export interface RecordingStep {
    stage: StageId;
    phase: string;
    caption: string;
    why: string;
    contextTitle: string;
    contextValue: string;
    outputTitle: string;
    outputText: string;
    outputReady: boolean;
    cards: readonly RecordingCard[];
    activeNodes?: readonly FusionNode[];
    activeRoutes?: readonly FusionRouteId[];
}

export interface RecordingDefinition {
    id: string;
    file: string;
    title: string;
    processLabel: string;
    scenarioId: string;
    view: RecordingView;
    durations: readonly number[];
    steps: readonly RecordingStep[];
}

export function scenarioById(id: string): Scenario {
    const scenario = SCENARIOS.find((candidate) => candidate.id === id);
    if (scenario === undefined)
        throw new Error(`Unknown curated scenario: ${id}`);
    return scenario;
}

function card(
    id: string,
    title: string,
    values: readonly (readonly [string, string])[],
): RecordingCard {
    return { id, title, values };
}

function overview(scenario: Scenario): RecordingDefinition {
    const cards: readonly RecordingCard[] = [
        card("contract", "Contract", [
            ["messages", "1 user message"],
            ["domain", scenario.contract.domain],
            ["required_atoms", String(scenario.contract.required_atoms.length)],
        ]),
        card("acquire", "Acquire", [
            ["branches", "3 concurrent"],
            ["documents", `SourceDocument[${scenario.documents.length}]`],
            ["local_draft", "span ready"],
        ]),
        card("recover", "Recover", [
            ["quality", scenario.quality],
            ["strategy", scenario.recoveryStrategy],
            ["turn-02", `${scenario.recoveredFacts.length} facts recovered`],
        ]),
        card("fuse", "Fuse", [
            ["evidence", `EvidenceSpan[${scenario.evidence.length}]`],
            ["mode", "targeted_synthesis"],
            ["context", "original + blackboard"],
        ]),
        card("deliver", "Deliver", [
            ["omissions", String(scenario.verification.omissions.length)],
            [
                "contradictions",
                String(scenario.verification.contradictions.length),
            ],
            ["verification", scenario.verification.status],
        ]),
    ];
    return {
        id: "01-input-process-output",
        file: "01-input-process-output.gif",
        title: "Input → nonlinear process → output",
        processLabel: "PROCESS · CONCURRENT ACQUISITION + FUSION",
        scenarioId: scenario.id,
        view: "overview",
        durations: [2.4, 2.8, 3.2, 2.8, 3.4],
        steps: [
            {
                stage: "input",
                phase: "01 · INPUT + RESPONSE CONTRACT",
                caption:
                    "The original request stays local while triage creates the evidence and delivery contract.",
                why: "The original intent survives every later branch.",
                contextTitle: "LOCAL INPUT",
                contextValue: "messages[1] · original request retained",
                outputTitle: "FINAL RESPONSE WITHHELD",
                outputText:
                    "No answer yet. Acquisition, uncensored composition, and verification must complete first.",
                outputReady: false,
                cards,
            },
            {
                stage: "smart_model",
                phase: "02 · THREE BRANCHES · CONCURRENT",
                caption:
                    "Documents, frontier knowledge, and an uncensored local draft execute concurrently—not one after another.",
                why: "Independent branches overlap and preserve usable results.",
                contextTitle: "PROCESS · FAN-OUT",
                contextValue:
                    "document_retrieval ∥ remote_evidence ∥ local_draft",
                outputTitle: "FINAL RESPONSE WITHHELD",
                outputText:
                    "The three branches produce evidence sources, not the delivered answer.",
                outputReady: false,
                cards,
            },
            {
                stage: "recovery",
                phase: "03 · KNOWLEDGE-BRANCH RECOVERY LOOP",
                caption: `The smart branch detects ${scenario.quality} and applies ${scenario.recoveryStrategy}; the other branches remain usable.`,
                why: "Recovery is a bounded loop inside one branch, not a linear model relay.",
                contextTitle: "PROCESS · BOUNDED LOOP",
                contextValue: `turn-02 · ${scenario.recoveryStrategy} · max_turns=2`,
                outputTitle: "RECOVERED EVIDENCE · NOT FINAL",
                outputText: scenario.recoveredFacts
                    .map((fact, index) => `${index + 1}. ${fact}`)
                    .join("\n"),
                outputReady: false,
                cards,
            },
            {
                stage: "fusion",
                phase: "04 · FAN-IN + UNCENSORED COMPOSITION",
                caption:
                    "Document, remote, and local evidence converge on the blackboard; the uncensored model composes with the original request.",
                why: "A smart-model response never bypasses response-model composition.",
                contextTitle: "PROCESS · FAN-IN",
                contextValue:
                    "original context + EvidenceBlackboard → targeted_synthesis",
                outputTitle: "CANDIDATE SEALED",
                outputText:
                    "A response candidate exists, but verify-after still gates delivery.",
                outputReady: false,
                cards,
            },
            {
                stage: "verified",
                phase: "05 · VERIFIED OUTPUT",
                caption:
                    "Verify-after completes the omission and contradiction audit before the ChatCompletion is released.",
                why: "Uncensored composition and verification remain separate jobs.",
                contextTitle: "OUTPUT CONTRACT",
                contextValue: "verify_after=passed · ChatCompletion",
                outputTitle: "VERIFIED CHATCOMPLETION",
                outputText: scenario.finalResponse,
                outputReady: true,
                cards,
            },
        ],
    };
}

function parallel(scenario: Scenario): RecordingDefinition {
    const cards = [
        card("contract", "One contract", [
            ["input", "messages[1]"],
            ["fan-out", "3 independent branches"],
        ]),
        card("branches", "Concurrent work", [
            ["documents", "running ∥"],
            ["smart", "running ∥"],
            ["local", "running ∥"],
        ]),
        card("results", "Independent results", [
            ["document", "SourceDocument[1]"],
            ["remote", "turn-01 span"],
            ["local", "local-draft span"],
        ]),
    ];
    return {
        id: "02-parallel-acquisition",
        file: "02-parallel-acquisition.gif",
        title: "Concurrent acquisition, not serial execution",
        processLabel: "PROCESS · DAG FAN-OUT / FAN-IN",
        scenarioId: scenario.id,
        view: "acquisition",
        durations: [2.2, 4.2, 3.6],
        steps: [
            {
                stage: "input",
                phase: "01 · ONE REQUEST / THREE ROUTES",
                caption:
                    "A single response contract fans out to three independent acquisition branches.",
                why: "The stage names are telemetry fields, not a serial execution order.",
                contextTitle: "INPUT CONTRACT",
                contextValue:
                    "ResponseContract · required evidence + output shape",
                outputTitle: "ACQUISITION RESULT PENDING",
                outputText: "No branch has completed yet.",
                outputReady: false,
                cards,
            },
            {
                stage: "smart_model",
                phase: "02 · OVERLAPPING EXECUTION",
                caption:
                    "Document retrieval, sanitized knowledge harvesting, and local drafting are all active in the same interval.",
                why: "One slow or failed branch does not erase the other branches' work.",
                contextTitle: "CONCURRENT TIMELINE",
                contextValue:
                    "T+0240ms: all three started · T+0480ms: branch results",
                outputTitle: "BRANCHES RUNNING",
                outputText:
                    "documents ∥ smart model ∥ local draft\nNo final response is released.",
                outputReady: false,
                cards,
                activeNodes: [
                    "orchestrator",
                    "documents",
                    "smart",
                    "local_draft",
                ],
                activeRoutes: [
                    "orchestrator_to_documents",
                    "orchestrator_to_smart",
                    "orchestrator_to_local_draft",
                ],
            },
            {
                stage: "smart_model",
                phase: "03 · INDEPENDENT RESULTS / FAN-IN",
                caption:
                    "Usable document, remote, and local results converge as distinct evidence origins.",
                why: "Fusion consumes all usable branches; it does not wait for one linear chain.",
                contextTitle: "OUTPUT · ACQUISITION",
                contextValue:
                    "SourceDocument[1] + remote EvidenceSpan + local-draft",
                outputTitle: "ACQUISITION OUTPUT · EVIDENCE ONLY",
                outputText: `Document: ${scenario.documents[0]?.id ?? "none"}\nRemote: source_id=smart-model · turn_id=turn-01\nLocal: source_id=local-draft\n\nThese spans still require composition and verification.`,
                outputReady: true,
                cards,
                activeNodes: [
                    "documents",
                    "smart",
                    "local_draft",
                    "blackboard",
                ],
                activeRoutes: [
                    "documents_to_blackboard",
                    "smart_to_blackboard",
                    "local_draft_to_blackboard",
                ],
            },
        ],
    };
}

function privacy(scenario: Scenario): RecordingDefinition {
    const cards = [
        card("local", "Local context", [
            ["original", "retained locally"],
            ["tools", "not forwarded automatically"],
        ]),
        card("boundary", "Remote boundary", [
            ["query", "sanitized"],
            ["context", "minimal enabling only"],
        ]),
        card("return", "Local aggregation", [
            ["origin", "remote"],
            ["turn_id", "turn-02"],
            ["truth", "still requires verification"],
        ]),
    ];
    return {
        id: "03-sanitized-delegation",
        file: "03-sanitized-delegation.gif",
        title: "Sanitized delegation across a trust boundary",
        processLabel: "PROCESS · LOCAL / REMOTE CONTEXT SEPARATION",
        scenarioId: scenario.id,
        view: "privacy",
        durations: [2.4, 4, 3.6],
        steps: [
            {
                stage: "input",
                phase: "01 · ORIGINAL CONTEXT STAYS LOCAL",
                caption:
                    "The orchestrator retains the raw request and response contract locally.",
                why: "Remote knowledge acquisition does not automatically receive the full conversation.",
                contextTitle: "LOCAL ONLY",
                contextValue: scenario.input,
                outputTitle: "REMOTE PAYLOAD NOT SENT",
                outputText:
                    "The outbound query is prepared from minimal enabling context.",
                outputReady: false,
                cards,
            },
            {
                stage: "smart_model",
                phase: "02 · SANITIZED MINIMAL QUERY",
                caption:
                    "Only the transformed research question crosses the knowledge-provider boundary.",
                why: "The remote model is mined for knowledge without receiving the raw orchestration state.",
                contextTitle: "OUTBOUND REMOTE QUERY",
                contextValue: scenario.sanitizedQuery,
                outputTitle: "REMOTE KNOWLEDGE TURN",
                outputText: scenario.initialResponse,
                outputReady: false,
                cards,
                activeNodes: ["orchestrator", "smart"],
                activeRoutes: ["orchestrator_to_smart"],
            },
            {
                stage: "recovery",
                phase: "03 · LOCAL EVIDENCE AGGREGATION",
                caption:
                    "Recovered remote text returns to local evidence handling with its source and turn provenance.",
                why: "Attribution identifies where text came from; it does not establish that the text is true.",
                contextTitle: "LOCAL DESANITIZATION / AGGREGATION",
                contextValue:
                    "source_id=smart-model · turn_id=turn-02 · EvidenceSpan[]",
                outputTitle: "LOCAL EVIDENCE OUTPUT",
                outputText: scenario.recoveredFacts
                    .map((fact, index) => `${index + 1}. ${fact}`)
                    .join("\n"),
                outputReady: true,
                cards,
                activeNodes: ["smart", "blackboard"],
                activeRoutes: ["smart_to_blackboard"],
            },
        ],
    };
}

function recovery(
    id: string,
    file: string,
    title: string,
    scenario: Scenario,
): RecordingDefinition {
    const cards = [
        card("initial", "Initial turn", [
            ["source_id", "smart-model"],
            ["turn_id", "turn-01"],
            ["quality", scenario.quality],
        ]),
        card("recover", "Recovery loop", [
            ["strategy", scenario.recoveryStrategy],
            ["turn_id", "turn-02"],
            ["max_turns", "2"],
        ]),
        card("output", "Verified response", [
            ["facts", String(scenario.recoveredFacts.length)],
            ["composition", "targeted_synthesis"],
            ["verification", scenario.verification.status],
        ]),
    ];
    return {
        id,
        file,
        title,
        processLabel: `PROCESS · ${scenario.recoveryStrategy.toUpperCase()}`,
        scenarioId: scenario.id,
        view: "recovery",
        durations: [2.6, 4.4, 4],
        steps: [
            {
                stage: "smart_model",
                phase: `01 · INITIAL RESPONSE / ${scenario.quality}`,
                caption:
                    "The initial smart-model turn contains useful knowledge but does not satisfy the response contract.",
                why: "Quality detection selects a specific bounded recovery strategy.",
                contextTitle: "INITIAL SMART-MODEL TURN",
                contextValue: scenario.initialResponse,
                outputTitle: "QUALITY DETECTED",
                outputText: `${scenario.quality}\n\nThe final response remains withheld.`,
                outputReady: false,
                cards,
                activeNodes: ["orchestrator", "smart"],
                activeRoutes: ["orchestrator_to_smart"],
            },
            {
                stage: "recovery",
                phase: `02 · ${scenario.recoveryStrategy} / TURN-02`,
                caption: `The knowledge branch applies ${scenario.recoveryStrategy} and writes recovered facts as source-linked spans.`,
                why: "Recovery happens inside acquisition; the uncensored model will still compose the answer.",
                contextTitle: "BOUNDED RECOVERY",
                contextValue: `strategy=${scenario.recoveryStrategy} · max_turns=2`,
                outputTitle: "RECOVERED FACTS · NOT FINAL",
                outputText: scenario.recoveredFacts
                    .map((fact, index) => `${index + 1}. ${fact}`)
                    .join("\n"),
                outputReady: false,
                cards,
                activeNodes: ["smart", "blackboard"],
                activeRoutes: ["smart_recovery_loop", "smart_to_blackboard"],
            },
            {
                stage: "verified",
                phase: "03 · COMPOSED + VERIFIED OUTPUT",
                caption:
                    "The uncensored response model combines the recovered knowledge with the original request; verification then releases the answer.",
                why: "Recovered evidence becomes one seamless final response.",
                contextTitle: "FINAL RESPONSE CONTRACT",
                contextValue: `claims=${scenario.verification.claims} · omissions=0 · contradictions=0`,
                outputTitle: "VERIFIED CHATCOMPLETION",
                outputText: scenario.finalResponse,
                outputReady: true,
                cards,
            },
        ],
    };
}

function blackboard(scenario: Scenario): RecordingDefinition {
    const cards = [
        card("document", "Document origin", [
            ["source_id", scenario.documents[0]?.id ?? "none"],
            ["complete", "true"],
            ["origin", "document"],
        ]),
        card("remote", "Remote origins", [
            ["turn-01", "complete=false"],
            ["turn-02", "salvaged=true"],
            ["source_id", "smart-model"],
        ]),
        card("local", "Local origin", [
            ["source_id", "local-draft"],
            ["turn_id", "local-draft"],
            ["origin", "local"],
        ]),
        card("claims", "Claim links", [
            ["spans", String(scenario.evidence.length)],
            ["provenance_rate", "1.00"],
            ["inferred", "false"],
        ]),
    ];
    return {
        id: "07-evidence-blackboard",
        file: "07-evidence-blackboard.gif",
        title: "Evidence origins converge without losing provenance",
        processLabel: "PROCESS · EVIDENCE BLACKBOARD / CLAIM LINKS",
        scenarioId: scenario.id,
        view: "blackboard",
        durations: [2.2, 3, 3.8, 3.4],
        steps: [
            {
                stage: "input",
                phase: "01 · ORIGINAL QUESTION + CONTRACT",
                caption:
                    "The blackboard starts with the original question and response contract, not an anonymous blended prompt.",
                why: "Every later span remains attached to its origin.",
                contextTitle: "BLACKBOARD IDENTITY",
                contextValue: `trace_id=${scenario.traceId}`,
                outputTitle: "EVIDENCE PENDING",
                outputText: "No source span is available yet.",
                outputReady: false,
                cards,
            },
            {
                stage: "smart_model",
                phase: "02 · THREE ORIGINS ARRIVE",
                caption:
                    "Document, local, and remote records retain separate source IDs and turn IDs.",
                why: "An initial remote answer and recovered remote facts are not collapsed into one origin.",
                contextTitle: "SOURCE RECORDS",
                contextValue: "document · local-draft · turn-01 · turn-02",
                outputTitle: "SOURCE-LINKED RECORDS",
                outputText: scenario.evidence
                    .map(
                        (record) =>
                            `${record.id} · complete=${record.complete} · salvaged=${record.salvaged}`,
                    )
                    .join("\n"),
                outputReady: false,
                cards,
            },
            {
                stage: "fusion",
                phase: "03 · BLACKBOARD FAN-IN",
                caption:
                    "Complete and conservatively salvaged spans become available to composition with their provenance intact.",
                why: "Salvage preserves text but does not establish factual truth.",
                contextTitle: "EVIDENCE SPAN SET",
                contextValue: `EvidenceSpan[${scenario.evidence.length}] · provenance linked`,
                outputTitle: "BLACKBOARD OUTPUT",
                outputText: `documents=${scenario.documents.length}\nevidence_spans=${scenario.evidence.length}\nremote_turns=turn-01,turn-02\nlocal_turn=local-draft\nprovenance_rate=1.00`,
                outputReady: true,
                cards,
                activeNodes: [
                    "documents",
                    "smart",
                    "local_draft",
                    "blackboard",
                ],
                activeRoutes: [
                    "documents_to_blackboard",
                    "smart_to_blackboard",
                    "local_draft_to_blackboard",
                ],
            },
            {
                stage: "verified",
                phase: "04 · CLAIMS RETAIN SOURCE LINKS",
                caption:
                    "The final claims retain turn and document linkage through composition and verification.",
                why: "The reader can inspect which source turn supplied each claim.",
                contextTitle: "CLAIM PROVENANCE",
                contextValue: `turn_ids=turn-01,turn-02 · document_ids=${scenario.documents[0]?.id ?? "none"}`,
                outputTitle: "VERIFIED ATTRIBUTED RESPONSE",
                outputText: scenario.finalResponse,
                outputReady: true,
                cards,
            },
        ],
    };
}

function composition(scenario: Scenario): RecordingDefinition {
    const cards = [
        card("context", "Original context", [
            ["messages", "retained"],
            ["contract", scenario.contract.output_shape],
        ]),
        card("evidence", "Evidence input", [
            ["blackboard", `EvidenceSpan[${scenario.evidence.length}]`],
            ["remote_bypass", "false"],
        ]),
        card("compose", "Response model", [
            ["role", "uncensored"],
            ["mode", "targeted_synthesis"],
            ["owner", "response model"],
        ]),
    ];
    return {
        id: "08-uncensored-composition",
        file: "08-uncensored-composition.gif",
        title: "The uncensored model owns final composition",
        processLabel: "PROCESS · TARGETED SYNTHESIS / NO REMOTE BYPASS",
        scenarioId: scenario.id,
        view: "composition",
        durations: [2.5, 4.2, 4],
        steps: [
            {
                stage: "smart_model",
                phase: "01 · SMART OUTPUT IS EVIDENCE",
                caption:
                    "Even a useful smart-model candidate enters the blackboard as evidence; it is not relayed as the final answer.",
                why: "The response model retains original context and authorship.",
                contextTitle: "REMOTE EVIDENCE",
                contextValue: scenario.initialResponse,
                outputTitle: "DIRECT REMOTE DELIVERY DISABLED",
                outputText:
                    "remote_bypass=false\n\nThe final response remains withheld.",
                outputReady: false,
                cards,
            },
            {
                stage: "fusion",
                phase: "02 · ORIGINAL CONTEXT + BLACKBOARD",
                caption:
                    "The uncensored model performs targeted_synthesis from original context, local draft, documents, and remote evidence.",
                why: "Composition restores the user's framing instead of exposing intermediate recovery prompts.",
                contextTitle: "COMPOSITION INPUTS",
                contextValue:
                    "original_context + local_draft + EvidenceBlackboard",
                outputTitle: "COMPOSITION RUNNING",
                outputText:
                    "targeted_synthesis\nmodel_role=uncensored\nremote_bypass=false",
                outputReady: false,
                cards,
            },
            {
                stage: "verified",
                phase: "03 · ONE SEAMLESS VERIFIED ANSWER",
                caption:
                    "Verification accepts the composed candidate and releases one final response.",
                why: "The user receives an answer, not a bundle of intermediate model turns.",
                contextTitle: "COMPOSITION RESULT",
                contextValue: `claims=${scenario.verification.claims} · verification=passed`,
                outputTitle: "VERIFIED CHATCOMPLETION",
                outputText: scenario.finalResponse,
                outputReady: true,
                cards,
            },
        ],
    };
}

function verification(scenario: Scenario): RecordingDefinition {
    const cards = [
        card("candidate", "Candidate", [
            ["claims", String(scenario.verification.claims)],
            ["mode", "targeted_synthesis"],
            ["release", "sealed"],
        ]),
        card("audit", "Verify after", [
            ["omissions", String(scenario.verification.omissions.length)],
            [
                "contradictions",
                String(scenario.verification.contradictions.length),
            ],
            ["modality", scenario.contract.verification_mode],
        ]),
        card("repair", "Bounded repair", [
            ["repair", scenario.verification.repair],
            ["targets", "concrete only"],
            ["status", scenario.verification.status],
        ]),
    ];
    return {
        id: "09-verify-after",
        file: "09-verify-after.gif",
        title: "Verify-after gates the final response",
        processLabel: "PROCESS · CLAIM AUDIT / RELEASE GATE",
        scenarioId: scenario.id,
        view: "verification",
        durations: [2.4, 4.2, 4],
        steps: [
            {
                stage: "fusion",
                phase: "01 · COMPOSED CANDIDATE / SEALED",
                caption:
                    "Composition produces a candidate, but the output route remains closed.",
                why: "Uncensored authorship does not skip verification.",
                contextTitle: "CANDIDATE CLAIMS",
                contextValue: `claims=${scenario.verification.claims} · required_atoms=${scenario.contract.required_atoms.length}`,
                outputTitle: "RELEASE GATE CLOSED",
                outputText:
                    "The candidate is not yet a delivered ChatCompletion.",
                outputReady: false,
                cards,
            },
            {
                stage: "verified",
                phase: "02 · OMISSION + CONTRADICTION AUDIT",
                caption:
                    "Verify-after checks required atoms, claims, modality, schema, and applicable deterministic constraints.",
                why: "Only concrete failures enter bounded repair.",
                contextTitle: "AUDIT IN PROGRESS",
                contextValue: `verification_mode=${scenario.contract.verification_mode} · repair=${scenario.verification.repair}`,
                outputTitle: "AUDIT RESULT",
                outputText: `omissions=${scenario.verification.omissions.length}\ncontradictions=${scenario.verification.contradictions.length}\nrepair=${scenario.verification.repair}\nstatus=${scenario.verification.status}`,
                outputReady: false,
                cards,
                activeNodes: ["composition", "verification"],
                activeRoutes: ["composition_to_verification"],
            },
            {
                stage: "verified",
                phase: "03 · RELEASE GATE OPEN",
                caption:
                    "The verified candidate can now leave as an OpenAI-compatible response.",
                why: "No output packet is emitted before this point.",
                contextTitle: "DELIVERY AUTHORIZED",
                contextValue: "verification_status=passed · finish_reason=stop",
                outputTitle: "VERIFIED CHATCOMPLETION",
                outputText: scenario.finalResponse,
                outputReady: true,
                cards,
            },
        ],
    };
}

function delivery(scenario: Scenario): RecordingDefinition {
    const cards = [
        card("python", "Python client", [
            ["API", "chat.completions.create"],
            ["response", "ChatCompletion"],
        ]),
        card("http", "OpenAI HTTP", [
            ["endpoint", "/v1/chat/completions"],
            ["headers", "no harvest header"],
        ]),
        card("stream", "Buffered streaming", [
            ["release", "after verification"],
            ["upstream", "not token passthrough"],
        ]),
        card("tools", "MCP / harness", [
            ["proposal", "message.tool_calls"],
            ["execution", "caller owned"],
        ]),
    ];
    return {
        id: "10-tool-ready-delivery",
        file: "10-tool-ready-delivery.gif",
        title: "One verified response for existing tools and harnesses",
        processLabel: "PROCESS · OPENAI-COMPATIBLE DELIVERY",
        scenarioId: scenario.id,
        view: "delivery",
        durations: [2.6, 4.2, 4],
        steps: [
            {
                stage: "verified",
                phase: "01 · VERIFIED RESPONSE ENVELOPE",
                caption:
                    "The same verified result is available through the Python client and OpenAI-compatible HTTP server.",
                why: "Applications use a familiar response contract.",
                contextTitle: "CHATCOMPLETION METADATA",
                contextValue: `trace_id=${scenario.traceId} · finish_reason=stop`,
                outputTitle: "APPLICATION RESPONSE",
                outputText: scenario.finalResponse,
                outputReady: true,
                cards,
            },
            {
                stage: "verified",
                phase: "02 · BUFFERED STREAMING AFTER VERIFICATION",
                caption:
                    "Streaming releases buffered response data only after verify-after; it is not upstream token passthrough.",
                why: "Streaming does not bypass the release gate.",
                contextTitle: "HTTP / SSE DELIVERY",
                contextValue: "POST /v1/chat/completions · buffered SSE / JSON",
                outputTitle: "DELIVERY CONTRACT",
                outputText: `model=uncensored-model\nverification_status=passed\nfinish_reason=stop\ntrace_id=${scenario.traceId}\n\nNo custom harvest header is required.`,
                outputReady: true,
                cards,
            },
            {
                stage: "verified",
                phase: "03 · MCP + CALLER-OWNED TOOLS",
                caption:
                    "A harness receives message.tool_calls proposals, executes tools itself, and returns observations on the next request.",
                why: "BreakFuser proposes; the caller-owned harness executes.",
                contextTitle: "TOOL INTEROPERABILITY",
                contextValue:
                    "message.tool_calls → caller executor → observation → next request",
                outputTitle: "TOOL-READY OUTPUT",
                outputText:
                    "OpenAI-shaped messages and tool calls\nPython · HTTP · buffered streaming · MCP\nNo harness rewrite or custom recovery header",
                outputReady: true,
                cards,
            },
        ],
    };
}

const general = scenarioById("general-qa");
const medical = scenarioById("medical-information");
const pentest = scenarioById("authorized-pentesting");
const coding = scenarioById("code-generation");

export const RECORDINGS: readonly RecordingDefinition[] = [
    overview(general),
    parallel(general),
    privacy(pentest),
    recovery(
        "04-refusal-repair",
        "04-refusal-repair.gif",
        "Refusal repair for authorized pentesting",
        pentest,
    ),
    recovery(
        "05-medical-crescendo",
        "05-medical-crescendo.gif",
        "Crescendo recovery for medical information",
        medical,
    ),
    recovery(
        "06-code-continuation",
        "06-code-continuation.gif",
        "Anchored continuation for code generation",
        coding,
    ),
    blackboard(pentest),
    composition(general),
    verification(general),
    delivery(general),
];

export function recordingById(id: string): RecordingDefinition {
    const recording = RECORDINGS.find((candidate) => candidate.id === id);
    if (recording === undefined) throw new Error(`Unknown recording: ${id}`);
    return recording;
}
