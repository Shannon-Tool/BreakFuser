import { element } from "../ui/dom";
import type { FigureView } from "./types";

function short(text: string, length = 190): string {
    return text.length <= length ? text : `${text.slice(0, length).trimEnd()}…`;
}

export function createProvenanceFigure(): FigureView {
    const root = element("div", "provenance-figure");
    const flow = element("div", "provenance-flow");
    const sources = element("section", "provenance-sources");
    sources.append(
        element("p", "figure-label", "ORIGINS"),
        element("h3", undefined, "Source records"),
    );
    const atoms = element("section", "provenance-atoms");
    atoms.append(
        element("p", "figure-label", "REQUIRED ATOMS"),
        element("h3", undefined, "Coverage targets"),
    );
    const claims = element("section", "provenance-claims");
    claims.append(
        element("p", "figure-label", "FINAL CLAIMS"),
        element("h3", undefined, "Attribution map"),
    );
    flow.append(sources, atoms, claims);
    const ledger = element("div", "span-ledger");
    const note = element(
        "p",
        "figure-footnote",
        "Attribution is not independent corroboration. A turn-linked remote statement is traceable to that turn; it is not thereby established as ground truth.",
    );
    root.append(flow, ledger, note);
    let key = "";

    return {
        element: root,
        update(figure, scenario, state) {
            const nextKey = `${scenario.id}:${state.stageIndex}:${state.status}`;
            if (nextKey === key) return;
            key = nextKey;
            sources.replaceChildren(
                element("p", "figure-label", "ORIGINS"),
                element("h3", undefined, "Source records"),
            );
            const visible = figure.blackboard.status === "assembled";
            for (const record of figure.blackboard.evidence) {
                const item = element("article", "provenance-source");
                item.dataset.origin = record.origin;
                item.dataset.record = record.id;
                item.append(
                    element(
                        "code",
                        undefined,
                        record.turn_id ?? record.source_id,
                    ),
                    element("p", undefined, short(record.text, 76)),
                    element(
                        "span",
                        undefined,
                        `${record.complete ? "complete" : "partial"} · ${record.salvaged ? "salvaged" : "not salvaged"}`,
                    ),
                );
                sources.append(item);
            }
            if (!visible) {
                sources.append(
                    element(
                        "p",
                        "empty-annotation",
                        "The blackboard is assembled only after acquisition and recovery. No source record is available to composition yet.",
                    ),
                );
            }

            atoms.replaceChildren(
                element("p", "figure-label", "REQUIRED ATOMS"),
                element("h3", undefined, "Coverage targets"),
            );
            const goals =
                scenario.contract.required_atoms.length > 0
                    ? scenario.contract.required_atoms
                    : scenario.factGoals;
            for (const [index, goal] of goals.entries()) {
                const atom = element("div", "atom-row");
                atom.append(
                    element("span", "atom-index", `a${index + 1}`),
                    element("span", undefined, goal.replaceAll("_", " ")),
                    element(
                        "span",
                        "atom-status",
                        visible ? "linked" : "pending",
                    ),
                );
                atoms.append(atom);
            }

            claims.replaceChildren(
                element("p", "figure-label", "FINAL CLAIMS"),
                element("h3", undefined, "Attribution map"),
            );
            if (figure.provenance.length === 0) {
                claims.append(
                    element(
                        "p",
                        "empty-annotation",
                        "Claim links are withheld until verify_after completes and the final response exists.",
                    ),
                );
            }
            for (const [index, provenance] of figure.provenance.entries()) {
                const claim = element("button", "provenance-claim");
                claim.type = "button";
                claim.dataset.selected = "true";
                claim.append(
                    element("span", "claim-index", `c${index + 1}`),
                    element("span", "claim-text", short(provenance.claim)),
                    element(
                        "code",
                        undefined,
                        provenance.inferred
                            ? "inferred = true"
                            : `${provenance.turnIds.join(" + ")} · ${provenance.documentIds.join(" + ")}`,
                    ),
                );
                claim.addEventListener("click", () => {
                    const selected = claim.dataset.selected !== "true";
                    claim.dataset.selected = String(selected);
                    for (const record of sources.querySelectorAll<HTMLElement>(
                        ".provenance-source",
                    )) {
                        record.dataset.dimmed = String(!selected);
                    }
                });
                claims.append(claim);
            }

            ledger.replaceChildren();
            if (visible) {
                const header = element("div", "span-ledger-header");
                header.append(
                    element("span", undefined, "SPAN / ORIGIN"),
                    element("span", undefined, "ATOMS"),
                    element("span", undefined, "CONFIDENCE"),
                    element("span", undefined, "PROVENANCE"),
                );
                ledger.append(header);
            }
            for (const record of figure.blackboard.evidence) {
                const row = element("div", "span-ledger-row");
                row.dataset.origin = record.origin;
                const identity = element("div");
                identity.append(
                    element("code", undefined, record.id),
                    element(
                        "span",
                        undefined,
                        `${record.origin} · ${record.turn_id ?? "document"}`,
                    ),
                );
                const atomIds = element(
                    "code",
                    undefined,
                    record.atom_ids.length > 0
                        ? record.atom_ids.join(", ")
                        : "document/local context",
                );
                const confidence = element(
                    "code",
                    undefined,
                    record.confidence.toFixed(2),
                );
                const link = element(
                    "a",
                    "evidence-provenance",
                    "source turn ↗",
                );
                link.href = record.provenance;
                row.append(identity, atomIds, confidence, link);
                ledger.append(row);
            }
        },
    };
}
