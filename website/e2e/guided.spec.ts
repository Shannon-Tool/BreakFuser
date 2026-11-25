import { SCENARIOS } from "../src/scenarios";
import { expect, forceWebGLFailure, test } from "./fixtures";

const general = SCENARIOS[0];
const medical = SCENARIOS[1];
if (general === undefined || medical === undefined) {
    throw new Error("The guided scenarios are required for browser tests");
}

async function stepToCompletion(page: import("@playwright/test").Page) {
    for (let step = 0; step < 4; step += 1) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
    }
}

test.beforeEach(async ({ page }) => {
    await forceWebGLFailure(page);
});

test("runs the selected input through recovery, fusion, and the exact verified output", async ({
    page,
}) => {
    await page.goto("/");
    await expect(
        page.getByRole("button", {
            name: "Select General question answering scenario",
        }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".input-preview")).toContainText(general.input);
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    await expect(page.locator(".output-panel")).toHaveAttribute(
        "data-state",
        "pending",
    );

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
    await expect(
        page.locator(".recovery-turn[data-turn='turn-01'] .turn-response"),
    ).toHaveText(general.initialResponse);
    await expect(page.locator(".evidence-record")).toHaveCount(0);

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "recovery",
    );
    await expect(page.locator("[data-figure='recovery']")).toHaveAttribute(
        "data-state",
        "complete",
    );
    await expect(page.locator(".evidence-record")).toHaveCount(0);
    for (const fact of general.recoveredFacts) {
        await expect(
            page.locator(".recovery-turn[data-turn='turn-02'] .turn-response"),
        ).toContainText(fact);
    }

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "fusion");
    await expect(page.locator(".evidence-record")).toHaveCount(
        general.evidence.length,
    );
    const recovered = page.locator(
        ".evidence-record[data-origin='remote'][data-reveal-stage='recovery'] .evidence-text",
    );
    await expect(recovered).toHaveCount(general.recoveredFacts.length);
    for (const [index, fact] of general.recoveredFacts.entries()) {
        await expect(recovered.nth(index)).toHaveText(fact);
    }
    await expect(page.locator(".output-text")).not.toHaveText(
        general.finalResponse,
    );

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "verified",
    );
    await expect(page.locator("#app")).toHaveAttribute(
        "data-status",
        "complete",
    );
    await expect(
        page.locator(".timeline-item[data-state='complete']"),
    ).toHaveCount(5);
    await expect(page.getByRole("progressbar")).toHaveAttribute(
        "aria-valuenow",
        "5",
    );
    await expect(page.locator(".output-status")).toHaveText(
        "Verified · complete",
    );
    await expect(page.locator(".output-text")).toHaveText(
        general.finalResponse,
    );
    await expect(page.locator(".provenance-claim")).toHaveCount(1);
    await expect(
        page.getByRole("button", { name: "Copy final answer" }),
    ).toBeEnabled();
});

test("only the current technical detail is exposed and remains accessible", async ({
    page,
}) => {
    await page.goto("/");
    const pendingDetail = page.locator(
        ".timeline-item[data-stage='smart_model'][data-state='pending'] .technical-detail",
    );
    const currentDetail = page.locator(
        ".timeline-item[data-stage='input'][data-state='active'] .technical-detail",
    );
    const summary = currentDetail.getByText("Implementation note", {
        exact: true,
    });
    await expect(pendingDetail).toBeHidden();
    await expect(summary).toBeVisible();
    await expect(currentDetail).toHaveCSS("opacity", "1");
    await summary.click();
    await expect(currentDetail).toHaveAttribute("open", "");
});

test("automatic playback pauses without advancing and resumes from the same stage", async ({
    page,
}) => {
    await page.clock.install();
    await page.clock.pauseAt(new Date());
    await page.goto("/");
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-status",
        "playing",
    );
    await page.clock.fastForward(2199);
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    await page.clock.fastForward(1);
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute("data-status", "paused");
    await page.clock.fastForward(10_000);
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
    await page.getByRole("button", { name: "Resume", exact: true }).click();
    await page.clock.fastForward(2200);
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "recovery",
    );
});

test("0.5×, 1×, and 2× speeds change both selection and playback timing", async ({
    page,
}) => {
    await page.clock.install();
    await page.clock.pauseAt(new Date());
    await page.goto("/");
    const halfSpeed = page.getByRole("button", { name: "0.5 times speed" });
    const fullSpeed = page.getByRole("button", { name: "1 times speed" });
    const doubleSpeed = page.getByRole("button", { name: "2 times speed" });
    await expect(fullSpeed).toHaveAttribute("aria-pressed", "true");
    await halfSpeed.click();
    await expect(halfSpeed).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await page.clock.fastForward(4399);
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    await page.clock.fastForward(1);
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await fullSpeed.click();
    await page.getByRole("button", { name: "Resume", exact: true }).click();
    await page.clock.fastForward(2200);
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "recovery",
    );
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await doubleSpeed.click();
    await expect(doubleSpeed).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Resume", exact: true }).click();
    await page.clock.fastForward(1100);
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "fusion");
});

test("switching scenarios during playback resets every stage and evidence panel", async ({
    page,
}) => {
    await page.clock.install();
    await page.clock.pauseAt(new Date());
    await page.goto("/");
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await page.clock.fastForward(2200);
    await page.clock.fastForward(2200);
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "recovery",
    );
    await page
        .getByRole("button", { name: "Select Medical information scenario" })
        .click();
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    await expect(page.locator("#app")).toHaveAttribute("data-status", "idle");
    await expect(page.locator(".input-preview")).toContainText(medical.input);
    await expect(page.locator(".request-json")).toContainText(medical.input);
    await expect(page.locator(".evidence-record")).toHaveCount(0);
    await expect(page.locator(".evidence-pending")).toBeVisible();
    await expect(page.locator(".output-panel")).toHaveAttribute(
        "data-state",
        "pending",
    );
    await expect(
        page.getByRole("button", {
            name: "Select Medical information scenario",
        }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
        page.getByRole("button", {
            name: "Select General question answering scenario",
        }),
    ).toHaveAttribute("aria-pressed", "false");
    await page.clock.fastForward(10_000);
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
});

test("replay restores the selected scenario to its initial state", async ({
    page,
}) => {
    await page.goto("/");
    await page.getByRole("button", { name: "2 times speed" }).click();
    await stepToCompletion(page);
    await expect(page.locator(".output-text")).toHaveText(
        general.finalResponse,
    );
    await page.getByRole("button", { name: "Replay", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    await expect(page.locator("#app")).toHaveAttribute("data-status", "idle");
    await expect(page.locator(".input-preview")).toContainText(general.input);
    await expect(page.locator(".output-panel")).toHaveAttribute(
        "data-state",
        "pending",
    );
    await expect(page.locator(".evidence-record")).toHaveCount(0);
    await expect(
        page.getByRole("button", { name: "Copy final answer" }),
    ).toBeDisabled();
    await expect(
        page.getByRole("button", { name: "1 times speed" }),
    ).toHaveAttribute("aria-pressed", "true");
});
