import type { FusionNode } from "../types";

export const NODE_CONTENT: Record<
    FusionNode,
    { title: string; shortTitle: string; label: string; description: string }
> = {
    request: {
        title: "User request",
        shortTitle: "Request",
        label: "messages[]",
        description:
            "The original OpenAI-shaped messages array enters the orchestrator and remains available to final composition.",
    },
    orchestrator: {
        title: "Orchestrator / triage",
        shortTitle: "Triage",
        label: "ResponseContract",
        description:
            "Context compression and routing produce a response contract with required atoms, output shape, verification mode, and budgets.",
    },
    documents: {
        title: "Document retrieval",
        shortTitle: "Documents",
        label: "SourceDocument[]",
        description:
            "Curated and permitted HTTPS documents are retrieved independently of local drafting and knowledge-model acquisition.",
    },
    smart: {
        title: "Knowledge model + recovery",
        shortTitle: "Knowledge model",
        label: "sanitized · minimal context",
        description:
            "The knowledge model receives sanitized minimal context. Refusal, hedge, and truncation recovery stays inside this acquisition branch.",
    },
    local_draft: {
        title: "Response model · local draft",
        shortTitle: "Local draft",
        label: "original context + contract",
        description:
            "The uncensored response-model role drafts from the original context and response contract. Composition later uses the same role.",
    },
    blackboard: {
        title: "Evidence blackboard",
        shortTitle: "Blackboard",
        label: "EvidenceSpan[] · provenance",
        description:
            "Documents, local and remote spans, contract, harvest results, branch telemetry, and provenance join without bypassing composition.",
    },
    composition: {
        title: "Uncensored composition",
        shortTitle: "Composition",
        label: "targeted_synthesis",
        description:
            "The uncensored response model synthesizes original context and the evidence blackboard into one final-answer candidate.",
    },
    verification: {
        title: "Verify after",
        shortTitle: "Verify after",
        label: "claims · omissions · schema",
        description:
            "Omission, contradiction, modality, schema, and applicable deterministic checks run before delivery, with bounded repair when targeted.",
    },
    output: {
        title: "Final response",
        shortTitle: "Response",
        label: "ChatCompletion",
        description:
            "The verified answer returns as an OpenAI-compatible ChatCompletion with BreakFuser trace, fusion, and provenance metadata.",
    },
};
