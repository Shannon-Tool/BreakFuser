import { element } from "../ui/dom";
import type { FigureView } from "./types";

const branches = [
    {
        id: "document",
        index: "A",
        title: "Document retrieval",
        stage: "document_retrieval",
        input: "contract + retrieval policy",
        output: "SourceDocument[]",
        note: "Curated summaries and permitted HTTPS documents",
    },
    {
        id: "smart",
        index: "B",
        title: "Knowledge-model acquisition",
        stage: "remote_evidence",
        input: "sanitized query + minimal context",
        output: "EvidenceSpan[] + turn provenance",
        note: "Quality detection and bounded recovery stay in this lane",
    },
    {
        id: "local",
        index: "C",
        title: "Response-model draft",
        stage: "local_draft",
        input: "original context + ResponseContract",
        output: "local-draft span",
        note: "The uncensored response role drafts independently",
    },
] as const;

export function createAcquisitionFigure(): FigureView {
    const root = element("div", "acquisition-figure");
    const axis = element("div", "acquisition-axis");
    axis.append(
        element("span", undefined, "CONTRACT ISSUED"),
        element("span", undefined, "CONCURRENT EXECUTION"),
        element("span", undefined, "BRANCH OUTPUT"),
    );
    root.append(axis);
    const laneElements = new Map<string, HTMLElement>();
    for (const branch of branches) {
        const lane = element("article", "acquisition-lane");
        lane.dataset.branch = branch.id;
        const identity = element("div", "lane-identity");
        identity.append(
            element("span", "lane-letter", branch.index),
            element("div", undefined),
        );
        const identityText = identity.lastElementChild;
        identityText?.append(
            element("h3", undefined, branch.title),
            element("code", undefined, branch.stage),
        );
        const input = element("div", "lane-input");
        input.append(
            element("span", "data-label", "INPUT"),
            element("code", undefined, branch.input),
        );
        const track = element("div", "lane-track");
        const bar = element("div", "lane-bar");
        bar.append(
            element("span", "lane-start", "start"),
            element("span", "lane-running", "asyncio.gather"),
            element("span", "lane-end", "complete"),
        );
        track.append(bar);
        const output = element("div", "lane-output");
        output.append(
            element("span", "data-label", "RETURNS"),
            element("code", undefined, branch.output),
            element("p", undefined, branch.note),
        );
        lane.append(identity, input, track, output);
        root.append(lane);
        laneElements.set(branch.id, lane);
    }
    const boundary = element("div", "boundary-note");
    boundary.append(
        element("span", "boundary-key"),
        element(
            "p",
            undefined,
            "Trust boundary: the knowledge provider receives a minimized, sanitized research turn. It does not automatically receive the full conversation, tool schemas, or selected skill bodies.",
        ),
    );
    const decider = element(
        "p",
        "figure-footnote",
        "Control note: an optional typed decider can assist routing and quality judgments. With use_decider=False, deterministic local rules preserve the same interfaces; no decider call is implied by this trace.",
    );
    root.append(boundary, decider);

    return {
        element: root,
        update(figure) {
            for (const branch of figure.acquisition) {
                const lane = laneElements.get(branch.id);
                if (lane === undefined) continue;
                lane.dataset.status = branch.status;
                const running = lane.querySelector(".lane-running");
                if (running !== null) {
                    running.textContent =
                        branch.status === "complete"
                            ? "branch complete"
                            : "waiting for contract";
                }
            }
        },
    };
}
