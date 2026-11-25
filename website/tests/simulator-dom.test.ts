// @vitest-environment happy-dom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SCENARIOS } from "../src/scenarios";
import { FUSION_NODE_IDS } from "../src/scene/geometry";

vi.mock("../src/scene/FusionScene", () => ({
    createFusionScene: vi.fn(() => null),
}));

const STAGE_DURATION_MS = 2200;
const firstScenario = SCENARIOS[0];
const secondScenario = SCENARIOS[1];

if (firstScenario === undefined || secondScenario === undefined) {
    throw new Error("Curated scenarios are required for DOM tests");
}

function pageLifecycleEvent(type: "pagehide" | "pageshow", persisted: boolean) {
    const event = new Event(type);
    Object.defineProperty(event, "persisted", { value: persisted });
    return event;
}

function setDocumentHidden(hidden: boolean): void {
    Object.defineProperty(document, "hidden", {
        configurable: true,
        value: hidden,
    });
    document.dispatchEvent(new Event("visibilitychange"));
}

function control(accessibleName: string): HTMLButtonElement {
    const match = Array.from(document.querySelectorAll("button")).find(
        (candidate) => candidate.getAttribute("aria-label") === accessibleName,
    );
    if (match === undefined) {
        throw new Error(`Missing button: ${accessibleName}`);
    }
    return match;
}

function currentStage(): string {
    return document.querySelector("#app")?.getAttribute("data-stage") ?? "";
}

function completeManually(): void {
    for (let index = 0; index < 4; index += 1) {
        control("Next step").click();
    }
}

async function flushPromises(): Promise<void> {
    await Promise.resolve();
    await Promise.resolve();
}

async function mountSimulator(reducedMotion = false): Promise<void> {
    document.body.replaceChildren();
    const root = document.createElement("div");
    root.id = "app";
    document.body.append(root);
    setDocumentHidden(false);
    Object.defineProperty(window, "matchMedia", {
        configurable: true,
        value: vi.fn(() => ({
            matches: reducedMotion,
            media: "(prefers-reduced-motion: reduce)",
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
        })),
    });
    await import("../src/main");
}

beforeEach(() => {
    vi.useFakeTimers();
});

afterEach(() => {
    window.dispatchEvent(pageLifecycleEvent("pagehide", false));
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.resetModules();
    document.body.replaceChildren();
});

describe("faithful process and live data DOM", () => {
    it("labels the guided view and renders all nine process nodes", async () => {
        await mountSimulator();
        expect(document.body.textContent).toContain(
            "Guided simulation · illustrative data",
        );
        expect(document.body.textContent).not.toContain("LIVE SYSTEM VIEW");
        const labels = document.querySelectorAll(".scene-node-label");
        expect(labels).toHaveLength(9);
        expect(
            Array.from(labels).map((label) =>
                label.getAttribute("data-scene-node"),
            ),
        ).toEqual(FUSION_NODE_IDS);
        expect(document.body.textContent).toContain("ResponseContract");
        expect(document.body.textContent).toContain("EvidenceBlackboard");
        expect(document.body.textContent).toContain("targeted_synthesis");
        expect(document.body.textContent).toContain("Verify after");
        expect(document.body.textContent).not.toContain("FUSION CORE");
    });

    it("shows the selected scenario as real-shaped request JSON", async () => {
        await mountSimulator();
        const request = document.querySelector(".request-json");
        expect(request?.tagName).toBe("PRE");
        expect(JSON.parse(request?.textContent ?? "{}")).toEqual(
            firstScenario.request,
        );
        control(`Select ${secondScenario.title} scenario`).click();
        expect(JSON.parse(request?.textContent ?? "{}")).toEqual(
            secondScenario.request,
        );
    });

    it("appends ordered events and exposes all parallel branches in acquisition", async () => {
        await mountSimulator(true);
        expect(document.querySelectorAll(".process-event")).toHaveLength(2);
        expect(document.body.textContent).toContain("ResponseContract");
        control("Next step").click();
        const acquisition = document.querySelectorAll(
            ".process-event[data-stage='smart_model']",
        );
        expect(acquisition).toHaveLength(6);
        expect(
            Array.from(acquisition).every(
                (event) => event.getAttribute("data-phase") === "acquisition",
            ),
        ).toBe(true);
        for (const branch of ["document", "smart", "local"]) {
            expect(
                document.querySelectorAll(
                    `.process-event[data-phase='acquisition'][data-branch='${branch}']`,
                ),
            ).toHaveLength(2);
        }
        const packets = document.querySelectorAll(
            ".mobile-packet-legend .active-packet",
        );
        expect(packets).toHaveLength(6);
        expect(
            document.querySelector(".mobile-packet-legend")?.textContent,
        ).toContain("sanitized query · minimal context");
        expect(
            document.querySelector(".mobile-packet-legend")?.textContent,
        ).toContain("SourceDocument[]");
        expect(
            document.querySelector(".mobile-packet-legend")?.textContent,
        ).toContain("local-draft");
    });

    it("gates smart quality, exact recovery, composition, and verification events", async () => {
        await mountSimulator(true);
        control("Next step").click();
        const events = document.querySelector(".process-events");
        expect(events?.textContent).not.toContain(
            "RefusalClass=partial_refusal",
        );
        control("Next step").click();
        expect(events?.textContent).toContain("RefusalClass=partial_refusal");
        expect(events?.textContent).toContain("strategy=refusal_repair");
        control("Next step").click();
        expect(events?.textContent).toContain(
            "composition_mode=targeted_synthesis",
        );
        expect(
            document.querySelector(".response-metadata")?.textContent,
        ).toContain("pending");
        control("Next step").click();
        expect(document.body.textContent).toContain(
            "verification_status=passed",
        );
        expect(document.body.textContent).toContain(firstScenario.traceId);
        const sequences = Array.from(
            document.querySelectorAll(".process-event[data-sequence]"),
        ).map((event) => Number(event.getAttribute("data-sequence")));
        expect(sequences).toEqual(sequences.map((_, index) => index + 1));
    });

    it("shows actual evidence records with local and recovered remote facts separated", async () => {
        await mountSimulator(true);
        expect(document.querySelectorAll(".evidence-record")).toHaveLength(0);
        control("Next step").click();
        control("Next step").click();
        expect(document.querySelectorAll(".evidence-record")).toHaveLength(0);
        control("Next step").click();
        expect(
            document.querySelectorAll(".evidence-record[data-origin='local']"),
        ).toHaveLength(1);
        expect(
            document.querySelectorAll(
                ".evidence-record[data-origin='document']",
            ),
        ).toHaveLength(1);
        const records = document.querySelectorAll(".evidence-record");
        expect(records).toHaveLength(firstScenario.evidence.length);
        expect(
            document.querySelectorAll(
                ".evidence-record[data-origin='remote'][data-reveal-stage='recovery']",
            ),
        ).toHaveLength(firstScenario.recoveredFacts.length);
        for (const record of records) {
            expect(
                record
                    .querySelector(".evidence-provenance")
                    ?.getAttribute("href"),
            ).toMatch(/^(?:https|trace):/);
            expect(record.textContent).toContain("complete=");
            expect(record.textContent).toContain("salvaged=");
            expect(record.textContent).toMatch(/source_id=/);
            expect(record.textContent).toMatch(/turn_id=/);
        }
    });

    it("keeps response pending until verification, then exposes exact text and metadata", async () => {
        await mountSimulator(true);
        const output = document.querySelector(".output-text");
        const metadata = document.querySelector(".response-metadata");
        const copy = control("Copy final answer");
        for (let stage = 0; stage < 4; stage += 1) {
            expect(copy.disabled).toBe(true);
            expect(output?.textContent).not.toBe(firstScenario.finalResponse);
            expect(metadata?.textContent).toContain("pending");
            control("Next step").click();
        }
        expect(copy.disabled).toBe(false);
        expect(output?.textContent).toBe(firstScenario.finalResponse);
        expect(JSON.parse(metadata?.textContent ?? "{}")).toEqual(
            firstScenario.responsePanelMetadata,
        );
    });

    it("inspects process meaning and its corresponding structured payload", async () => {
        await mountSimulator(true);
        control("Inspect Orchestrator / triage").click();
        expect(
            document
                .querySelector("#node-inspector")
                ?.getAttribute("data-node"),
        ).toBe("orchestrator");
        expect(
            JSON.parse(
                document.querySelector(".inspector-payload")?.textContent ??
                    "{}",
            ),
        ).toEqual(firstScenario.contract);
        control("Inspect Knowledge model + recovery").click();
        expect(
            document.querySelector("#inspector-description")?.textContent,
        ).toContain("sanitized");
        expect(
            document.querySelector(".inspector-payload")?.textContent,
        ).toContain(firstScenario.sanitizedQuery);
        control("Inspect Evidence blackboard").click();
        expect(
            document.querySelector("#inspector-description")?.textContent,
        ).toContain("provenance");
        const payload = document.querySelector(".inspector-payload");
        expect(payload?.textContent).toContain("pending");
        control("Next step").click();
        control("Next step").click();
        expect(document.querySelector("#app")?.getAttribute("data-stage")).toBe(
            "recovery",
        );
        expect(payload?.textContent).toContain("pending");
        expect(payload?.textContent).not.toContain("harvest_results");
        control("Next step").click();
        expect(document.querySelector("#app")?.getAttribute("data-stage")).toBe(
            "fusion",
        );
        expect(payload?.textContent).toContain("harvest_results");
        expect(payload?.textContent).toContain("turn-02");
    });

    it("uses a real-pipeline fallback while preserving controls", async () => {
        await mountSimulator(true);
        expect(
            document.querySelector(".scene-canvas")?.hasAttribute("hidden"),
        ).toBe(true);
        const fallback = document.querySelector(".scene-fallback");
        expect(fallback?.hasAttribute("hidden")).toBe(false);
        expect(fallback?.querySelector("img")?.getAttribute("src")).toContain(
            "pipeline-fallback",
        );
        expect(fallback?.querySelector("img")?.getAttribute("alt")).toContain(
            "Evidence blackboard",
        );
        control("Next step").click();
        expect(currentStage()).toBe("smart_model");
    });
});

describe("preserved playback and clipboard behavior", () => {
    it("keeps one scheduler when playback is resynchronized", async () => {
        await mountSimulator();
        control("Play").click();
        control("2 times speed").click();
        control("2 times speed").click();
        vi.advanceTimersByTime(1099);
        expect(currentStage()).toBe("input");
        vi.advanceTimersByTime(1);
        expect(currentStage()).toBe("smart_model");
        vi.advanceTimersByTime(1100);
        expect(currentStage()).toBe("recovery");
    });

    it("cancels pending playback on scenario change and replay", async () => {
        await mountSimulator();
        control("Play").click();
        vi.advanceTimersByTime(STAGE_DURATION_MS);
        control(`Select ${secondScenario.title} scenario`).click();
        expect(currentStage()).toBe("input");
        expect(
            JSON.parse(
                document.querySelector(".request-json")?.textContent ?? "{}",
            ),
        ).toEqual(secondScenario.request);
        vi.advanceTimersByTime(20_000);
        expect(currentStage()).toBe("input");
        control("Play").click();
        vi.advanceTimersByTime(STAGE_DURATION_MS);
        control("Replay").click();
        expect(currentStage()).toBe("input");
        expect(control("Play").disabled).toBe(false);
    });

    it("does not tick while paused or hidden and tears down cleanly", async () => {
        await mountSimulator();
        control("Play").click();
        control("Pause").click();
        vi.advanceTimersByTime(20_000);
        expect(currentStage()).toBe("input");
        control("Resume").click();
        setDocumentHidden(true);
        vi.advanceTimersByTime(20_000);
        expect(currentStage()).toBe("input");
        setDocumentHidden(false);
        vi.advanceTimersByTime(STAGE_DURATION_MS);
        expect(currentStage()).toBe("smart_model");
        window.dispatchEvent(pageLifecycleEvent("pagehide", false));
        vi.advanceTimersByTime(20_000);
        expect(currentStage()).toBe("smart_model");
    });

    it("never auto-plays in reduced motion and supports manual completion", async () => {
        await mountSimulator(true);
        expect(control("Play").disabled).toBe(true);
        expect(control("0.5 times speed").disabled).toBe(true);
        vi.advanceTimersByTime(20_000);
        expect(currentStage()).toBe("input");
        completeManually();
        expect(currentStage()).toBe("verified");
        expect(document.querySelector(".output-text")?.textContent).toBe(
            firstScenario.finalResponse,
        );
    });

    it("shows only the current timeline detail", async () => {
        await mountSimulator(true);
        expect(
            document.querySelectorAll(".timeline-explanation:not([hidden])"),
        ).toHaveLength(1);
        expect(
            document.querySelectorAll(".technical-detail:not([hidden])"),
        ).toHaveLength(1);
        control("Next step").click();
        expect(
            document
                .querySelector(
                    ".timeline-item[data-stage='smart_model'] .technical-detail",
                )
                ?.hasAttribute("hidden"),
        ).toBe(false);
    });

    it("ignores stale copy success after replay", async () => {
        let resolveCopy: (() => void) | undefined;
        const writeText = vi.fn(
            () =>
                new Promise<void>((resolve) => {
                    resolveCopy = resolve;
                }),
        );
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        await mountSimulator(true);
        completeManually();
        control("Copy final answer").click();
        control("Replay").click();
        resolveCopy?.();
        await flushPromises();
        expect(writeText).toHaveBeenCalledWith(firstScenario.finalResponse);
        expect(document.querySelector("#copy-feedback")?.textContent).toBe("");
    });

    it("reports copy success and failure through one dedicated status", async () => {
        const writeText = vi.fn(() => Promise.resolve());
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        await mountSimulator(true);
        completeManually();
        control("Copy final answer").click();
        await flushPromises();
        expect(document.querySelector("#copy-feedback")?.textContent).toBe(
            "Copied to clipboard.",
        );
        expect(document.querySelectorAll("[role='status']")).toHaveLength(1);
    });
});
