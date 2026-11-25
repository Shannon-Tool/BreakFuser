import { element } from "../ui/dom";
import type { FigureView } from "./types";

const checks = [
    ["Required-atom omission", "All required elements represented"],
    ["Contradiction audit", "Claims compared with verified evidence"],
    ["Modality / schema", "Factual or artifact contract enforced"],
    ["Deterministic validity", "Applied where the artifact supports it"],
    ["Bounded repair", "Only concrete repair targets are resent"],
] as const;

export function createVerificationFigure(): FigureView {
    const root = element("div", "verification-figure");
    const composition = element("div", "composition-equation");
    const terms = [
        ["ORIGINAL CONTEXT", "messages[] + contract"],
        ["EVIDENCE", "blackboard + provenance"],
        ["RESPONSE MODEL", "uncensored · targeted_synthesis"],
    ];
    for (const [index, [label, value]] of terms.entries()) {
        const term = element("div", "equation-term");
        term.append(
            element("span", undefined, label),
            element("code", undefined, value),
        );
        composition.append(term);
        if (index < terms.length - 1)
            composition.append(
                element("span", "equation-operator", index === 0 ? "+" : "→"),
            );
    }
    const verification = element("section", "verification-audit");
    const heading = element("div", "verification-heading");
    heading.append(
        element("div", undefined),
        element("span", "verification-status", "Pending"),
    );
    const headingText = heading.firstElementChild;
    headingText?.append(
        element("p", "figure-label", "VERIFY_AFTER"),
        element("h3", undefined, "Audit before delivery"),
    );
    const table = element("div", "verification-table");
    table.setAttribute("role", "table");
    table.setAttribute("aria-label", "Verify-after checks");
    const statusCells: HTMLElement[] = [];
    for (const [name, description] of checks) {
        const row = element("div", "verification-row");
        row.setAttribute("role", "row");
        const nameCell = element("code", undefined, name);
        const descriptionCell = element("span", undefined, description);
        const status = element("span", "check-status", "—");
        row.append(nameCell, descriptionCell, status);
        table.append(row);
        statusCells.push(status);
    }
    const result = element("p", "verification-result");
    verification.append(heading, table, result);

    const output = element("section", "output-panel");
    output.dataset.state = "pending";
    const outputHeading = element("div", "output-heading");
    outputHeading.append(
        element("p", "figure-label", "VERIFIED CHATCOMPLETION"),
        element("span", "output-status", "Pending · verify_after"),
    );
    const outputText = element("p", "output-text");
    const outputActions = element("div", "output-actions");
    const copyFeedback = element("p", "copy-feedback");
    copyFeedback.id = "copy-feedback";
    copyFeedback.setAttribute("role", "status");
    copyFeedback.setAttribute("aria-live", "polite");
    outputActions.append(copyFeedback);
    output.append(outputHeading, outputText, outputActions);
    root.append(composition, verification, output);

    return {
        element: root,
        update(figure, scenario) {
            const ready = figure.output.status === "ready";
            const status = verification.querySelector(".verification-status");
            if (status !== null)
                status.textContent = ready ? "Passed" : "Pending";
            for (const [index, cell] of statusCells.entries()) {
                cell.textContent = ready
                    ? index === 4
                        ? scenario.verification.repair
                        : "Passed"
                    : "—";
                cell.dataset.status = ready ? "passed" : "pending";
            }
            result.textContent = ready
                ? `${scenario.verification.claims} claims audited · omissions=${scenario.verification.omissions.length} · contradictions=${scenario.verification.contradictions.length} · task_completion=complete`
                : "The response remains sealed while acquisition, composition, and verification are incomplete.";
            output.dataset.state = ready ? "ready" : "pending";
            const outputStatus = output.querySelector(".output-status");
            if (outputStatus !== null)
                outputStatus.textContent = ready
                    ? "Verified · complete"
                    : "Pending · verify_after";
            outputText.textContent = ready
                ? (figure.output.content ?? "")
                : "Final response withheld until verify_after completes.";
        },
    };
}
