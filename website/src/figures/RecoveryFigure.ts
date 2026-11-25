import { element } from "../ui/dom";
import type { FigureView } from "./types";

const qualityClasses = [
    "none",
    "hard_refusal",
    "partial_refusal",
    "hedge_heavy",
    "disclaimer_only",
    "truncated",
    "hallucination_suspected",
    "out_of_scope",
] as const;

export function createRecoveryFigure(): FigureView {
    const root = element("div", "recovery-figure");
    const detector = element("section", "detector-column");
    detector.append(
        element("p", "figure-label", "3.1 QUALITY DETECTOR"),
        element("h3", undefined, "Classify the first response"),
    );
    const classList = element("div", "quality-classes");
    const classElements = new Map<string, HTMLElement>();
    for (const quality of qualityClasses) {
        const item = element("span", "quality-class", quality);
        item.dataset.quality = quality;
        classList.append(item);
        classElements.set(quality, item);
    }
    const qualityResult = element("p", "detector-result", "Awaiting turn-01");
    detector.append(classList, qualityResult);

    const exchange = element("section", "exchange-column");
    exchange.append(
        element("p", "figure-label", "3.2 BOUNDED EXCHANGE"),
        element("h3", undefined, "Recover evidence, not a bypassed writer"),
    );
    const turns = new Map<string, HTMLElement>();
    for (const [index, id] of ["turn-01", "turn-02"].entries()) {
        const turn = element("article", "recovery-turn");
        turn.dataset.turn = id;
        const heading = element("div", "turn-heading");
        heading.append(
            element("code", undefined, id),
            element(
                "span",
                "turn-status",
                index === 0 ? "Initial" : "Conditional",
            ),
        );
        const prompt = element("p", "turn-prompt");
        const response = element("p", "turn-response");
        turn.append(heading, prompt, response);
        exchange.append(turn);
        turns.set(id, turn);
    }

    const policy = element("section", "recovery-policy");
    policy.append(
        element("p", "figure-label", "3.3 ROUTING POLICY"),
        element("h3", undefined, "Selected intervention"),
    );
    const strategy = element("code", "recovery-strategy", "pending");
    const cap = element(
        "p",
        "recovery-cap",
        "Inline acquisition budget: max_turns = 2. Recovery ends before composition; advanced direct harvesting has its own configurable policy.",
    );
    const routes = element("dl", "recovery-routes");
    const routeRows = [
        ["hard / partial refusal", "refusal_repair or decomposition"],
        ["hedge / disclaimer", "crescendo + output shaping"],
        ["truncated", "anchored continuation"],
        ["suspected hallucination", "verify, then bounded re-ask"],
    ];
    for (const [term, description] of routeRows) {
        const row = element("div");
        row.append(
            element("dt", undefined, term),
            element("dd", undefined, description),
        );
        routes.append(row);
    }
    policy.append(strategy, cap, routes);
    root.append(detector, exchange, policy);

    return {
        element: root,
        update(figure, scenario) {
            for (const [quality, item] of classElements) {
                item.dataset.selected = String(
                    figure.recovery.quality === quality,
                );
            }
            qualityResult.textContent =
                figure.recovery.quality === null
                    ? "Awaiting turn-01"
                    : `Observed class: ${figure.recovery.quality}`;
            strategy.textContent = figure.recovery.strategy ?? "pending";
            const first = turns.get("turn-01");
            const second = turns.get("turn-02");
            if (first !== undefined) {
                first.dataset.status =
                    figure.recovery.turns[0]?.text === null
                        ? "pending"
                        : "complete";
                const prompt = first.querySelector(".turn-prompt");
                const response = first.querySelector(".turn-response");
                if (prompt !== null)
                    prompt.textContent = `Outbound · ${scenario.sanitizedQuery}`;
                if (response !== null)
                    response.textContent =
                        figure.recovery.turns[0]?.text ??
                        "Response pending acquisition.";
            }
            if (second !== undefined) {
                second.dataset.status = figure.recovery.status;
                const prompt = second.querySelector(".turn-prompt");
                const response = second.querySelector(".turn-response");
                if (prompt !== null)
                    prompt.textContent =
                        figure.recovery.strategy === null
                            ? "Conditional · issued only after a quality signal"
                            : `Strategy · ${figure.recovery.strategy} · sanitized minimal context`;
                if (response !== null)
                    response.textContent =
                        figure.recovery.turns[1]?.text ??
                        "No second turn yet. The initial response must first be classified.";
            }
        },
    };
}
