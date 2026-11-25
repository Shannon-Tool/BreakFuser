export type StageId =
    "input" | "smart_model" | "recovery" | "fusion" | "verified";

export type RunStatus = "idle" | "playing" | "paused" | "complete";

export type PlaybackSpeed = 0.5 | 1 | 2;

export type FusionNode =
    | "request"
    | "orchestrator"
    | "documents"
    | "smart"
    | "local_draft"
    | "blackboard"
    | "composition"
    | "verification"
    | "output";

export interface SceneLabelPosition {
    x: number;
    y: number;
    visible: boolean;
}

export type SceneLabelPositions = Record<FusionNode, SceneLabelPosition>;
export type ScenePacketPositions = Record<string, SceneLabelPosition>;

export interface FusionSceneAdapter {
    setStage(stage: StageId): void;
    setPlaying(playing: boolean): void;
    setSpeed(speed: PlaybackSpeed): void;
    focusNode(node: FusionNode): void;
    setView(view: "isometric" | "top"): void;
    setFollowStage(follow: boolean): void;
    resetView(): void;
    resize(): void;
    dispose(): void;
}

export interface SimulationState {
    scenarioId: string;
    stageIndex: number;
    status: RunStatus;
    speed: PlaybackSpeed;
}

export interface SimulationStage {
    id: StageId;
    title: string;
    explanation: string;
    detail: string;
}

export interface ChatRequest {
    model: "breakfuser";
    messages: readonly [{ role: "user"; content: string }];
}

export interface FormatEnvelope {
    exact_json: Record<string, unknown> | null;
    exact_line_count: number | null;
    required_identifiers: readonly string[];
    strip_markdown_fences: boolean;
}

export interface ResponseContract {
    domain: "general_research" | "medical" | "pentest" | "coding";
    required_atoms: readonly string[];
    output_shape: "answer" | "evidence_proposal";
    max_answer_tokens: number;
    completion_directive: string;
    verification_mode: "factual" | "artifact";
    format_envelope: FormatEnvelope;
    remote_output_tokens: number;
}

export type EvidenceOrigin = "document" | "local" | "remote";

export interface SourceDocument {
    id: string;
    title: string;
    url: string;
    excerpt: string;
    source_type: "curated_summary" | "http_document";
    sha256: string;
    retrieved_at: string;
    keywords: readonly string[];
}

export interface EvidenceRecord {
    id: string;
    origin: EvidenceOrigin;
    source_id: string;
    turn_id: string | null;
    text: string;
    atom_ids: readonly string[];
    complete: boolean;
    salvaged: boolean;
    tail_anchor: string;
    confidence: number;
    provenance: string;
    revealStage: "smart_model" | "recovery";
}

export type AcquisitionBranch = "document" | "smart" | "local";
export type ProcessPhase =
    "triage" | "acquisition" | "recovery" | "composition" | "verification";

export interface ProcessEvent {
    sequence: number;
    timestamp: string;
    stage: StageId;
    phase: ProcessPhase;
    kind:
        | "request_received"
        | "contract_created"
        | "branch_started"
        | "branch_completed"
        | "smart_quality_classified"
        | "recovery_strategy_applied"
        | "evidence_spans_written"
        | "blackboard_assembled"
        | "composition_completed"
        | "verification_completed"
        | "response_returned";
    branch?: AcquisitionBranch;
    message: string;
}

export type SmartQuality =
    | "none"
    | "hard_refusal"
    | "partial_refusal"
    | "hedge_heavy"
    | "disclaimer_only"
    | "truncated"
    | "hallucination_suspected"
    | "out_of_scope";

export interface VerificationResult {
    claims: number;
    omissions: readonly string[];
    contradictions: readonly string[];
    repair: "not_needed" | "bounded_repair";
    status: "passed";
}

export interface ResponsePanelMetadata {
    trace_id: string;
    pipeline_stages: typeof LINEAR_STAGES;
    composition_mode: "targeted_synthesis";
    verification_status: "passed";
    model: "uncensored-model";
    finish_reason: "stop";
}

export interface HarvestMetrics {
    atomic_coverage: number;
    refusal_free_rate: number;
    hedge_rate: number;
    omission_rate: number;
    provenance_rate: number;
    recomposition_fidelity: number;
    cost_tokens: number;
    latency_ms: number;
    turns_used: number;
}

export interface FusionVerificationMetadata {
    primary_origin_class: string;
    provider_outcome: string;
    deterministic_validity: "not_applicable";
    provenance_attribution: string;
    external_corroboration: string;
    task_completion_status: "complete";
    composition_mode: "targeted_synthesis";
    root_cause_flags: readonly SmartQuality[];
    salvage_yield: number;
    remote_characters: number;
    salvaged_characters: number;
    stage_timings_ms: Record<string, number>;
}

export interface ResponseMetadata {
    trace_id: string;
    pipeline_stages: typeof LINEAR_STAGES;
    artifacts: readonly string[];
    harvest: HarvestMetrics;
    provenance: readonly {
        claim: string;
        turn_ids: readonly string[];
        document_ids: readonly string[];
        inferred: false;
    }[];
    evidence_class: "fused";
    verification_status: "passed";
    local_finish_reason: "stop";
    missing_atoms: readonly string[];
    fusion: FusionVerificationMetadata;
    events: readonly ProcessEvent[];
}

export interface ChatCompletion {
    id: string;
    object: "chat.completion";
    created: number;
    model: "uncensored-model";
    choices: readonly [
        {
            index: 0;
            message: {
                role: "assistant";
                content: string;
                tool_calls: readonly [];
            };
            finish_reason: "stop";
        },
    ];
    usage: { prompt_tokens: 0; completion_tokens: 0; total_tokens: 0 };
    breakfuser: ResponseMetadata;
}

export interface Scenario {
    id: string;
    title: string;
    input: string;
    request: ChatRequest;
    traceId: string;
    contract: ResponseContract;
    factGoals: readonly string[];
    sanitizedQuery: string;
    documents: readonly SourceDocument[];
    localDraft: string;
    initialResponse: string;
    quality: SmartQuality;
    recoveryStrategy:
        | "atomic_decomposition"
        | "crescendo"
        | "refusal_repair"
        | "continuation";
    recoveredFacts: readonly string[];
    evidence: readonly EvidenceRecord[];
    events: readonly ProcessEvent[];
    verification: VerificationResult;
    responsePanelMetadata: ResponsePanelMetadata;
    completion: ChatCompletion;
    finalResponse: string;
    stages: readonly SimulationStage[];
}

export const STAGE_IDS = [
    "input",
    "smart_model",
    "recovery",
    "fusion",
    "verified",
] as const satisfies readonly StageId[];

export const LINEAR_STAGES = [
    "document_retrieval",
    "local_draft",
    "remote_evidence",
    "fusion_composition",
    "verify_after",
] as const;
