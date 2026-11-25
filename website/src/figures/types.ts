import type { FigureState } from "../simulation";
import type { Scenario, SimulationState } from "../types";

export interface FigureView {
    readonly element: HTMLElement;
    update: (
        figure: FigureState,
        scenario: Scenario,
        state: SimulationState,
    ) => void;
}

export function statusLabel(
    status: "pending" | "complete" | "assembled" | "passed" | "ready",
): string {
    switch (status) {
        case "pending":
            return "Pending";
        case "complete":
            return "Complete";
        case "assembled":
            return "Assembled";
        case "passed":
            return "Passed";
        case "ready":
            return "Verified";
    }
}
