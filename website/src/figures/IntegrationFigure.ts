import { element, json } from "../ui/dom";
import type { FigureView } from "./types";

const adapters = [
    {
        label: "PYTHON CLIENT",
        title: "Drop-in client",
        code: `from BreakFuser import BreakFuser\n\nclient = BreakFuser(...)\nresponse = client.chat.completions.create(\n    model="breakfuser", messages=messages\n)`,
    },
    {
        label: "OPENAI-COMPATIBLE HTTP",
        title: "Existing harnesses",
        code: `POST $BREAKFUSER_BASE_URL/chat/completions\nAuthorization: Bearer $BREAKFUSER_API_KEY\n\n{"model":"breakfuser","messages":[...]}`,
    },
    {
        label: "MCP / TOOL HARNESS",
        title: "Tool-ready responses",
        code: `message.tool_calls → caller-owned executor\nobservation → next request\n\nBreakFuser proposes; the harness executes.`,
    },
] as const;

export function createIntegrationFigure(): FigureView {
    const root = element("div", "integration-figure");
    const grid = element("div", "integration-grid");
    for (const adapter of adapters) {
        const panel = element("article", "integration-adapter");
        panel.append(
            element("p", "figure-label", adapter.label),
            element("h3", undefined, adapter.title),
            element("pre", "integration-code", adapter.code),
        );
        grid.append(panel);
    }
    const delivery = element("div", "delivery-contract");
    const flow = element("div", "delivery-flow");
    for (const [index, item] of [
        "BreakFuser pipeline",
        "verify_after",
        "buffered SSE / JSON",
        "application or harness",
    ].entries()) {
        flow.append(element("span", "delivery-node", item));
        if (index < 3) flow.append(element("span", "delivery-arrow", "→"));
    }
    const metadata = element("pre", "response-metadata code-block");
    delivery.append(flow, metadata);
    const note = element(
        "p",
        "figure-footnote",
        "Streaming is buffered until verification completes; it is not token-by-token upstream passthrough. Aggressive evidence recovery is configured in the engine, so integrations need no custom harvest header.",
    );
    root.append(grid, delivery, note);
    return {
        element: root,
        update(figure, scenario) {
            metadata.textContent = json(
                figure.output.completion === null
                    ? { status: "pending", until: "verify_after" }
                    : scenario.responsePanelMetadata,
            );
        },
    };
}
