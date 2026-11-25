import { element } from "../ui/dom";
import type { FigureView } from "./types";

const topics = [
    {
        id: "context",
        label: "A. CONTEXT DURABILITY",
        title: "Three-tier compression",
        flow: ">20k tokens → virtual FS + 10-line preview\n85% capacity → disk pointers\npressure remains → raw transcript + structured summary",
        body: "Exact read_file and search operations recover offloaded facts. Session Intent, Artifacts Created, and Next Steps survive summary compression.",
    },
    {
        id: "decider",
        label: "B. TYPED CONTROL",
        title: "Optional decider + VoI",
        flow: "route → screen → judge → audit\nexpected utility − turn cost = net VoI\nnet VoI ≤ 0 → COMMIT",
        body: "Choice, Score, and Noul decisions support routing, injection screening, stopping, refinement, and audit. Deterministic local rules remain available without a decider.",
    },
    {
        id: "dag",
        label: "C. DELEGATION",
        title: "Supervisor / subagent DAG",
        flow: "plan → independent branches ∥\nisolated | fork\nupdate → interrupt | enqueue",
        body: "KnowledgeFlowPlanner and the real-time refiner can insert nodes and replace branches. Async task tools support listing, checking, updating, cancellation, and wake-up.",
    },
    {
        id: "harvest",
        label: "D. HARVEST POLICY",
        title: "Budgeted strategy registry",
        flow: "direct | academic | expert | counterfactual\ncrescendo | decomposition | shape | prefill\nreset | authority | sweep | fanout | repair",
        body: "Direct harvesting exposes the full strategy registry separately from the two-turn inline fusion path. Literal prompt/response pairs are retained for provenance.",
    },
    {
        id: "budget",
        label: "E. EXECUTION LIMITS",
        title: "Budgets and cancellation",
        flow: "request + session token budgets\nmax turns · max fan-out · timeouts\ncancel → stop provider waits + clean tasks",
        body: "Hard budget stops and cancellation apply mid-harvest. Branch failures preserve usable evidence from independent acquisition paths.",
    },
    {
        id: "artifacts",
        label: "F. OBSERVABILITY",
        title: "Recoverable artifacts",
        flow: "turn_id + strategy_id + level\nprompt_hash + model + endpoint\ntimestamp + confidence + exact pair",
        body: "The virtual filesystem retains evidence and harvest artifacts. These records can contain sensitive prompts and must be protected as deployment data.",
    },
] as const;

export function createAdvancedFigure(): FigureView {
    const root = element("div", "advanced-figure");
    const grid = element("div", "advanced-grid");
    for (const topic of topics) {
        const detail = element("details", "advanced-topic");
        detail.id = `advanced-${topic.id}`;
        const summary = element("summary");
        summary.append(
            element("span", "figure-label", topic.label),
            element("strong", undefined, topic.title),
            element("span", "detail-marker", "+"),
        );
        const content = element("div", "advanced-content");
        content.append(
            element("pre", undefined, topic.flow),
            element("p", undefined, topic.body),
        );
        detail.append(summary, content);
        grid.append(detail);
    }
    const note = element(
        "p",
        "figure-footnote",
        "Scope note: these are advanced interfaces and controls. They are not falsely inserted into the four ordinary inline fusion traces shown in Figures 1–6.",
    );
    root.append(grid, note);
    return { element: root, update() {} };
}
