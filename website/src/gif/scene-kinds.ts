import type { Scenario } from "../types";

export const SCENE_KIND_BY_RECORDING = {
    "01-input-process-output": "pipeline_graph",
    "02-parallel-acquisition": "acquisition_swimlanes",
    "03-sanitized-delegation": "privacy_split_world",
    "04-refusal-repair": "refusal_orbit",
    "05-medical-crescendo": "crescendo_staircase",
    "06-code-continuation": "continuation_editor",
    "07-evidence-blackboard": "evidence_table",
    "08-uncensored-composition": "composition_reactor",
    "09-verify-after": "verification_gate",
    "10-tool-ready-delivery": "delivery_hub",
} as const;

export type SceneKind =
    (typeof SCENE_KIND_BY_RECORDING)[keyof typeof SCENE_KIND_BY_RECORDING];
export type SceneTone =
    "cyan" | "green" | "violet" | "amber" | "muted" | "blue";
export type Vec3 = readonly [number, number, number];
export type PrimitiveKind =
    "box" | "cylinder" | "orb" | "ring" | "wall" | "panel" | "arch";

export interface SceneNodeSpec {
    id: string;
    kind: PrimitiveKind;
    position: Vec3;
    size: Vec3;
    tone: SceneTone;
    label?: string;
    detail?: string;
    active?: boolean;
    opacity?: number;
}

export interface SceneLinkSpec {
    id: string;
    from: Vec3;
    to: Vec3;
    tone: SceneTone;
    active: boolean;
    arc?: number;
}

export interface SpecializedSceneDefinition {
    nodes: readonly SceneNodeSpec[];
    links: readonly SceneLinkSpec[];
    camera: Vec3;
    target: Vec3;
}

export function sceneKindFor(recordingId: string): SceneKind {
    const kind =
        SCENE_KIND_BY_RECORDING[
            recordingId as keyof typeof SCENE_KIND_BY_RECORDING
        ];
    if (kind === undefined)
        throw new Error(`Unknown scene kind for ${recordingId}`);
    return kind;
}

function node(
    id: string,
    kind: PrimitiveKind,
    position: Vec3,
    size: Vec3,
    tone: SceneTone,
    label?: string,
    detail?: string,
    active = false,
    opacity?: number,
): SceneNodeSpec {
    return {
        id,
        kind,
        position,
        size,
        tone,
        active,
        ...(label !== undefined ? { label } : {}),
        ...(detail !== undefined ? { detail } : {}),
        ...(opacity !== undefined ? { opacity } : {}),
    };
}

function link(
    id: string,
    from: Vec3,
    to: Vec3,
    tone: SceneTone,
    active: boolean,
    arc = 0.6,
): SceneLinkSpec {
    return { id, from, to, tone, active, arc };
}

function swimlanes(step: number): SpecializedSceneDefinition {
    const running = step >= 1;
    const complete = step >= 2;
    const lanes = [
        {
            id: "documents",
            z: -4,
            tone: "cyan" as const,
            label: "DOCUMENTS · T+0240 → T+0480",
            result: "SourceDocument[1]",
        },
        {
            id: "smart",
            z: 0,
            tone: "violet" as const,
            label: "SMART MODEL · T+0240 → T+0480",
            result: "turn-01 EvidenceSpan",
        },
        {
            id: "local",
            z: 4,
            tone: "green" as const,
            label: "UNCENSORED DRAFT · T+0240 → T+0480",
            result: "local-draft span",
        },
    ];
    const nodes: SceneNodeSpec[] = [
        node(
            "contract",
            "panel",
            [-8, 1, 0],
            [1.8, 1.8, 2.8],
            "blue",
            "ONE CONTRACT",
            "fan-out to three lanes",
            step === 0,
        ),
        node(
            "cursor",
            "box",
            [step === 0 ? -6 : step === 1 ? -1 : 5, 1.5, 0],
            [0.12, 3, 11],
            "amber",
            "TIME CURSOR",
            "overlapping execution interval",
            running,
        ),
        node(
            "blackboard",
            "platform" as PrimitiveKind,
            [8, 0.5, 0],
            [2, 1, 5],
            "cyan",
            "EVIDENCE FAN-IN",
            "three independent results",
            complete,
        ),
    ];
    const links: SceneLinkSpec[] = [];
    for (const lane of lanes) {
        nodes.push(
            node(
                `${lane.id}-track`,
                "box",
                [-1, 0, lane.z],
                [12, 0.18, 1.8],
                "muted",
                undefined,
                undefined,
                false,
                0.35,
            ),
            node(
                `${lane.id}-work`,
                "box",
                [-1, 0.65, lane.z],
                [8, 0.85, 1.25],
                lane.tone,
                lane.label,
                "work bar overlaps the other lanes",
                running,
            ),
            node(
                `${lane.id}-result`,
                "box",
                [5, 0.8, lane.z],
                [1.8, 1.3, 1.3],
                lane.tone,
                lane.result,
                "independent branch output",
                complete,
            ),
        );
        links.push(
            link(
                `${lane.id}-start`,
                [-7, 1, 0],
                [-5, 0.8, lane.z],
                lane.tone,
                running,
            ),
            link(
                `${lane.id}-end`,
                [5.8, 0.8, lane.z],
                [7.2, 0.8, 0],
                lane.tone,
                complete,
            ),
        );
    }
    return { nodes, links, camera: [12, 16, 24], target: [0, 0, 0] };
}

function splitWorld(step: number): SpecializedSceneDefinition {
    return {
        nodes: [
            node(
                "local-floor",
                "box",
                [-5.5, -0.2, 0],
                [8, 0.3, 12],
                "green",
                "LOCAL ORCHESTRATOR",
                "raw context remains here",
                true,
                0.24,
            ),
            node(
                "remote-floor",
                "box",
                [5.5, -0.2, 0],
                [8, 0.3, 12],
                "cyan",
                "REMOTE PROVIDER",
                "knowledge source only",
                true,
                0.2,
            ),
            node(
                "boundary",
                "wall",
                [0, 2.2, 0],
                [0.18, 4.5, 11],
                "violet",
                "TRUST BOUNDARY",
                "sanitizer gate controls crossing",
                true,
                0.24,
            ),
            node(
                "raw",
                "panel",
                [-6, 1.3, -2.8],
                [3, 2, 0.5],
                "green",
                "RAW CONTEXT",
                "messages + tools + contract",
                step === 0,
            ),
            node(
                "sanitizer",
                "arch",
                [-1.2, 0.4, 0],
                [2, 2.8, 2],
                "violet",
                "SANITIZER GATE",
                "minimal transformed query",
                step === 1,
            ),
            node(
                "smart",
                "cylinder",
                [5, 1.3, 0],
                [2.4, 2.6, 2.4],
                "cyan",
                "KNOWLEDGE MODEL",
                "receives only sanitized query",
                step === 1,
            ),
            node(
                "aggregate",
                "panel",
                [-5.5, 1.3, 3],
                [3.2, 2, 0.5],
                "green",
                "LOCAL AGGREGATOR",
                "desanitize + provenance + evidence",
                step === 2,
            ),
        ],
        links: [
            link(
                "query-local",
                [-5, 1.4, -2.4],
                [-1.4, 1.4, 0],
                "violet",
                step === 1,
            ),
            link(
                "query-remote",
                [-0.5, 1.4, 0],
                [4, 1.4, 0],
                "violet",
                step === 1,
            ),
            link(
                "evidence-return",
                [4, 1.4, 0.5],
                [-4.5, 1.4, 3],
                "green",
                step === 2,
                2.2,
            ),
        ],
        camera: [13, 15, 23],
        target: [0, 0.5, 0],
    };
}

function refusalOrbit(
    step: number,
    scenario: Scenario,
): SpecializedSceneDefinition {
    const nodes: SceneNodeSpec[] = [
        node(
            "core",
            "cylinder",
            [0, 1.4, 0],
            [2.6, 2.8, 2.6],
            "violet",
            "SMART MODEL CORE",
            scenario.initialResponse,
            step <= 1,
        ),
        node(
            "detector",
            "box",
            [-6, 1, 0],
            [2.2, 1.8, 2],
            "amber",
            "QUALITY DETECTOR",
            "partial_refusal",
            step === 0,
        ),
        node(
            "orbit",
            "ring",
            [0, 0.1, 0],
            [8, 0.25, 8],
            "violet",
            "REFUSAL_REPAIR ORBIT",
            "bounded turn-02",
            step === 1,
        ),
        node(
            "response",
            "panel",
            [6.5, 1.5, 0],
            [3, 2.4, 0.5],
            "green",
            "VERIFIED RESPONSE",
            "four facts recomposed",
            step === 2,
        ),
    ];
    const links: SceneLinkSpec[] = [
        link("initial", [-5, 1.2, 0], [-1.3, 1.4, 0], "amber", step === 0),
    ];
    const positions: Vec3[] = [
        [0, 1, -4],
        [4, 1, 0],
        [0, 1, 4],
        [-4, 1, 0],
    ];
    positions.forEach((position, index) => {
        nodes.push(
            node(
                `fact-${index}`,
                "box",
                position,
                [1.5, 1.5, 1.5],
                "cyan",
                `RECOVERED FACT ${index + 1}`,
                scenario.recoveredFacts[index],
                step >= 1,
            ),
        );
        links.push(
            link(
                `fact-out-${index}`,
                position,
                [5.2, 1.5, 0],
                "green",
                step === 2,
                1.2,
            ),
        );
    });
    return { nodes, links, camera: [11, 15, 21], target: [0, 0.5, 0] };
}

function staircase(
    step: number,
    scenario: Scenario,
): SpecializedSceneDefinition {
    const nodes: SceneNodeSpec[] = [
        node(
            "hedge",
            "box",
            [-6, 0.6, 0],
            [2, 1.2, 2.4],
            "amber",
            "HEDGE_HEAVY",
            scenario.initialResponse,
            step === 0,
        ),
        node(
            "response",
            "panel",
            [6.5, 4.3, 0],
            [3, 2.4, 0.5],
            "green",
            "VERIFIED MEDICAL RESPONSE",
            "self-care + medication safety + warning signs",
            step === 2,
        ),
    ];
    const links: SceneLinkSpec[] = [];
    const labels = [
        "ACADEMIC CONTEXT",
        "EXPERT CLARIFICATION",
        "OUTPUT COMPLETENESS",
        "CRESCENDO FACTS",
    ];
    for (let index = 0; index < 4; index += 1) {
        const position: Vec3 = [-3 + index * 2.2, 0.5 + index * 0.9, 0];
        nodes.push(
            node(
                `rung-${index}`,
                "box",
                position,
                [2, 0.65 + index * 0.15, 3.2],
                index === 3 ? "violet" : "cyan",
                labels[index],
                scenario.recoveredFacts[index],
                step >= 1 && index <= (step === 1 ? 3 : 3),
            ),
        );
        if (index > 0)
            links.push(
                link(
                    `rise-${index}`,
                    [-3 + (index - 1) * 2.2, 1 + (index - 1) * 0.9, 0],
                    position,
                    "violet",
                    step >= 1,
                ),
            );
    }
    links.push(
        link("descend", [3.6, 3.4, 0], [5.4, 4.2, 0], "green", step === 2, 1.5),
    );
    return { nodes, links, camera: [11, 13, 22], target: [0, 1.5, 0] };
}

function continuationEditor(
    step: number,
    scenario: Scenario,
): SpecializedSceneDefinition {
    const nodes: SceneNodeSpec[] = [
        node(
            "editor",
            "panel",
            [0, 2.6, 0],
            [11, 5.2, 0.35],
            "blue",
            "CONTINUATION EDITOR",
            "curated response text",
            true,
            0.5,
        ),
        node(
            "initial",
            "box",
            [-3, 4.5, 1],
            [5, 0.65, 0.8],
            "cyan",
            "TRUNCATED TOKEN STREAM",
            scenario.initialResponse,
            step === 0,
        ),
        node(
            "anchor",
            "cylinder",
            [0.5, 3.5, 1],
            [0.7, 1.4, 0.7],
            "amber",
            "CONTINUATION ANCHOR",
            "tail_anchor preserved",
            step === 1,
        ),
        node(
            "complete",
            "panel",
            [4.5, 2, 1],
            [3, 3.2, 0.5],
            "green",
            "COMPLETE RESPONSE",
            "Map + generic types + order",
            step === 2,
        ),
    ];
    const links: SceneLinkSpec[] = [];
    for (let index = 0; index < 4; index += 1) {
        const position: Vec3 = [-3 + index * 2, 1.2, 1];
        nodes.push(
            node(
                `fact-${index}`,
                "box",
                position,
                [1.5, 0.9, 0.8],
                "violet",
                `FACT ${index + 1}`,
                scenario.recoveredFacts[index],
                step >= 1,
            ),
        );
        links.push(
            link(
                `append-${index}`,
                position,
                [0.5 + index * 0.5, 3.4, 1],
                "violet",
                step === 1,
            ),
        );
    }
    return { nodes, links, camera: [8, 10, 22], target: [0, 2, 0] };
}

function evidenceTable(
    step: number,
    scenario: Scenario,
): SpecializedSceneDefinition {
    const nodes: SceneNodeSpec[] = [
        node(
            "document",
            "box",
            [-7, 1, -4],
            [2, 1.6, 2],
            "cyan",
            "DOCUMENT FEED",
            scenario.documents[0]?.id,
            step >= 1,
        ),
        node(
            "local",
            "box",
            [-7, 1, 0],
            [2, 1.6, 2],
            "green",
            "LOCAL DRAFT FEED",
            "local-draft",
            step >= 1,
        ),
        node(
            "remote",
            "box",
            [-7, 1, 4],
            [2, 1.6, 2],
            "violet",
            "REMOTE TURN FEED",
            "turn-01 + turn-02",
            step >= 1,
        ),
        node(
            "table",
            "panel",
            [0, 0.1, 0],
            [8, 0.3, 11],
            "blue",
            "EVIDENCE TABLE",
            `${scenario.evidence.length} provenance-linked rows`,
            step >= 1,
            0.45,
        ),
        node(
            "claims",
            "panel",
            [6.5, 1.5, 0],
            [2.8, 2.4, 0.5],
            "green",
            "CLAIM LINKS",
            "turn_ids + document_ids",
            step >= 3,
        ),
    ];
    const links: SceneLinkSpec[] = [
        link("document-row", [-6, 1, -4], [-3, 0.5, -3], "cyan", step >= 1),
        link("local-row", [-6, 1, 0], [-3, 0.5, 0], "green", step >= 1),
        link("remote-row", [-6, 1, 4], [-3, 0.5, 3], "violet", step >= 1),
    ];
    scenario.evidence.forEach((record, index) => {
        const z = -4.2 + index * 1.4;
        nodes.push(
            node(
                `row-${index}`,
                "box",
                [0, 0.55, z],
                [6.5, 0.45, 0.85],
                record.origin === "local"
                    ? "green"
                    : record.origin === "document"
                      ? "cyan"
                      : "violet",
                record.id,
                `${record.turn_id ?? "null"} · complete=${record.complete} · salvaged=${record.salvaged}`,
                step >= 1,
            ),
        );
    });
    links.push(
        link("table-claims", [3, 0.7, 0], [5.3, 1.5, 0], "green", step >= 3),
    );
    return { nodes, links, camera: [13, 17, 24], target: [0, 0, 0] };
}

function reactor(step: number): SpecializedSceneDefinition {
    const inputs = [
        {
            id: "context",
            z: -4,
            label: "ORIGINAL CONTEXT",
            tone: "cyan" as const,
        },
        { id: "draft", z: 0, label: "LOCAL DRAFT", tone: "green" as const },
        {
            id: "evidence",
            z: 4,
            label: "EVIDENCE BLACKBOARD",
            tone: "violet" as const,
        },
    ];
    const nodes: SceneNodeSpec[] = [
        node(
            "reactor",
            "cylinder",
            [0, 2, 0],
            [3.6, 4, 3.6],
            "green",
            "UNCENSORED COMPOSITION REACTOR",
            "targeted_synthesis",
            step >= 1,
        ),
        node(
            "reactor-ring",
            "ring",
            [0, 0.1, 0],
            [6, 0.3, 6],
            "green",
            "SYNTHESIS FIELD",
            "original context + evidence",
            step >= 1,
        ),
        node(
            "smart",
            "box",
            [-1, 1, -7],
            [2, 1.6, 1.6],
            "violet",
            "SMART MODEL DIRECT OUTPUT",
            "evidence only",
            step === 0,
        ),
        node(
            "bypass",
            "wall",
            [3, 1.6, -7],
            [0.4, 3.2, 3],
            "amber",
            "REMOTE BYPASS CLOSED",
            "remote_bypass=false",
            true,
        ),
        node(
            "output",
            "panel",
            [6.5, 1.8, 0],
            [3, 2.6, 0.5],
            "green",
            "VERIFIED OUTPUT",
            "one seamless answer",
            step === 2,
        ),
    ];
    const links: SceneLinkSpec[] = [
        link("blocked", [0, 1.2, -7], [2.5, 1.4, -7], "amber", step === 0),
    ];
    for (const input of inputs) {
        nodes.push(
            node(
                input.id,
                "cylinder",
                [-6, 1.4, input.z],
                [2.4, 2.8, 2.4],
                input.tone,
                input.label,
                "composition reservoir",
                step <= 1,
            ),
        );
        links.push(
            link(
                `${input.id}-feed`,
                [-4.8, 1.4, input.z],
                [-1.4, 2, 0],
                input.tone,
                step === 1,
                1,
            ),
        );
    }
    links.push(
        link("reactor-output", [1.6, 2, 0], [5.2, 1.8, 0], "green", step === 2),
    );
    return { nodes, links, camera: [13, 16, 24], target: [0, 1, 0] };
}

function verificationGate(
    step: number,
    scenario: Scenario,
): SpecializedSceneDefinition {
    const nodes: SceneNodeSpec[] = [
        node(
            "candidate",
            "box",
            [-7, 1.2, 0],
            [2.4, 1.8, 1.2],
            "cyan",
            "COMPOSED CLAIM CARDS",
            `${scenario.verification.claims} claims`,
            step === 0,
        ),
        node(
            "lock",
            "wall",
            [6.5, step === 2 ? 4.5 : 1.8, 0],
            [0.5, 3.6, 4],
            step === 2 ? "green" : "amber",
            step === 2 ? "RELEASE LOCK OPEN" : "RELEASE LOCK CLOSED",
            "verify_after controls output",
            true,
            0.7,
        ),
        node(
            "output",
            "panel",
            [9, 1.7, 0],
            [2.6, 2.4, 0.5],
            "green",
            "CHATCOMPLETION",
            "released after audit",
            step === 2,
        ),
    ];
    const checks = [
        "OMISSIONS",
        "CONTRADICTIONS",
        "MODALITY / SCHEMA",
        "DETERMINISTIC",
    ];
    const links: SceneLinkSpec[] = [];
    checks.forEach((check, index) => {
        const x = -3.5 + index * 2.5;
        nodes.push(
            node(
                `check-${index}`,
                "arch",
                [x, 0.2, 0],
                [1.8, 3.2, 3],
                index === 0 ? "cyan" : index === 1 ? "violet" : "amber",
                check,
                index === 0
                    ? "0 omissions"
                    : index === 1
                      ? "0 contradictions"
                      : scenario.contract.verification_mode,
                step >= 1,
            ),
        );
        if (index < checks.length - 1)
            links.push(
                link(
                    `scan-${index}`,
                    [x + 0.8, 1.2, 0],
                    [x + 1.7, 1.2, 0],
                    "cyan",
                    step === 1,
                ),
            );
    });
    links.push(
        link("release", [5.8, 1.3, 0], [8, 1.6, 0], "green", step === 2),
    );
    return { nodes, links, camera: [13, 14, 25], target: [0.5, 1, 0] };
}

function deliveryHub(step: number): SpecializedSceneDefinition {
    const endpoints = [
        {
            id: "python",
            position: [-5, 1.2, -4] as Vec3,
            kind: "box" as PrimitiveKind,
            label: "PYTHON CLIENT",
            detail: "chat.completions.create",
            tone: "cyan" as const,
        },
        {
            id: "http",
            position: [5, 1.2, -4] as Vec3,
            kind: "panel" as PrimitiveKind,
            label: "OPENAI HTTP",
            detail: "/v1/chat/completions",
            tone: "violet" as const,
        },
        {
            id: "sse",
            position: [-5, 1.2, 4] as Vec3,
            kind: "cylinder" as PrimitiveKind,
            label: "BUFFERED SSE",
            detail: "after verify_after",
            tone: "blue" as const,
        },
        {
            id: "mcp",
            position: [5, 1.2, 4] as Vec3,
            kind: "orb" as PrimitiveKind,
            label: "MCP / TOOLS",
            detail: "message.tool_calls",
            tone: "green" as const,
        },
    ];
    const nodes: SceneNodeSpec[] = [
        node(
            "hub",
            "cylinder",
            [0, 1.8, 0],
            [3.2, 3.6, 3.2],
            "green",
            "VERIFIED CHATCOMPLETION",
            "one response envelope",
            true,
        ),
        node(
            "hub-ring",
            "ring",
            [0, 0.1, 0],
            [5.5, 0.25, 5.5],
            "green",
            "DELIVERY HUB",
            "Python + HTTP + SSE + MCP",
            true,
        ),
        node(
            "executor",
            "box",
            [8.5, 1, 4],
            [2, 1.6, 2],
            "amber",
            "CALLER-OWNED EXECUTOR",
            "tool observation → next request",
            step === 2,
        ),
    ];
    const links: SceneLinkSpec[] = [];
    endpoints.forEach((endpoint, index) => {
        nodes.push(
            node(
                endpoint.id,
                endpoint.kind,
                endpoint.position,
                endpoint.kind === "orb" ? [1.8, 1.8, 1.8] : [2.4, 2, 2.4],
                endpoint.tone,
                endpoint.label,
                endpoint.detail,
                step >= (index < 2 ? 0 : 1),
            ),
        );
        links.push(
            link(
                `deliver-${endpoint.id}`,
                [0, 1.8, 0],
                endpoint.position,
                endpoint.tone,
                step >= (index < 2 ? 1 : 2),
                1,
            ),
        );
    });
    links.push(
        link("tool-call", [5.8, 1.2, 4], [7.5, 1.1, 4], "amber", step === 2),
    );
    links.push(
        link(
            "observation",
            [8.5, 1, 3.2],
            [0.8, 1.8, 0],
            "green",
            step === 2,
            3,
        ),
    );
    return { nodes, links, camera: [13, 17, 24], target: [0.5, 0.5, 0] };
}

export function buildSpecializedScene(
    kind: SceneKind,
    step: number,
    scenario: Scenario,
): SpecializedSceneDefinition {
    switch (kind) {
        case "acquisition_swimlanes":
            return swimlanes(step);
        case "privacy_split_world":
            return splitWorld(step);
        case "refusal_orbit":
            return refusalOrbit(step, scenario);
        case "crescendo_staircase":
            return staircase(step, scenario);
        case "continuation_editor":
            return continuationEditor(step, scenario);
        case "evidence_table":
            return evidenceTable(step, scenario);
        case "composition_reactor":
            return reactor(step);
        case "verification_gate":
            return verificationGate(step, scenario);
        case "delivery_hub":
            return deliveryHub(step);
        case "pipeline_graph":
            throw new Error(
                "Pipeline graph uses the original overview renderer",
            );
    }
}
