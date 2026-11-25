import { SCENARIOS } from "../src/scenarios";
import { expect, test } from "./fixtures";

test("isometric and top cameras are selectable and resettable", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    if (test.info().project.name === "mobile") {
        await page
            .getByRole("button", { name: "Isometric", exact: true })
            .click();
    }
    const isometric = page.getByRole("button", {
        name: "Isometric",
        exact: true,
    });
    const top = page.getByRole("button", {
        name: "Top / schematic",
        exact: true,
    });
    await expect(isometric).toHaveAttribute("aria-pressed", "true");
    await top.click();
    await expect(top).toHaveAttribute("aria-pressed", "true");
    await expect(isometric).toHaveAttribute("aria-pressed", "false");
    await page.getByRole("button", { name: "Reset view", exact: true }).click();
    await expect(page.locator(".scene-viewport")).toHaveAttribute(
        "data-scene",
        "webgl",
    );
    await isometric.click();
    await expect(isometric).toHaveAttribute("aria-pressed", "true");
});

test("all four worked examples produce their exact verified answers across the shared figures", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    for (const scenario of SCENARIOS) {
        await page
            .getByRole("button", { name: `Select ${scenario.title} scenario` })
            .click();
        await expect(page.locator(".request-json")).toHaveText(
            JSON.stringify(scenario.request, null, 2),
        );
        for (let step = 0; step < 4; step += 1) {
            await page
                .getByRole("button", { name: "Next step", exact: true })
                .click();
        }
        await expect(page.locator(".output-text")).toHaveText(
            scenario.finalResponse,
        );
        await expect(page.locator(".response-metadata")).toContainText(
            scenario.traceId,
        );
        await expect(
            page.locator(".quality-class[data-selected='true']"),
        ).toHaveText(scenario.quality);
        await expect(page.locator(".recovery-strategy")).toHaveText(
            scenario.recoveryStrategy,
        );
        await expect(page.locator(".provenance-claim")).toHaveCount(1);
    }
});

test("claim selection highlights and restores its provenance records", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    for (let step = 0; step < 4; step += 1) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
    }
    const claim = page.locator(".provenance-claim");
    const sources = page.locator(".provenance-source");
    await expect(claim).toHaveAttribute("data-selected", "true");
    await claim.click();
    await expect(claim).toHaveAttribute("data-selected", "false");
    for (const source of await sources.all()) {
        await expect(source).toHaveAttribute("data-dimmed", "true");
    }
    await claim.click();
    await expect(claim).toHaveAttribute("data-selected", "true");
    for (const source of await sources.all()) {
        await expect(source).toHaveAttribute("data-dimmed", "false");
    }
});

test("advanced paper figures disclose implementation detail without changing the inline trace", async ({
    page,
}) => {
    await page.goto("/");
    const context = page.locator("#advanced-context");
    await context.locator("summary").click();
    await expect(context).toHaveAttribute("open", "");
    await expect(context).toContainText("20k tokens");
    await expect(context).toContainText("85% capacity");
    const dag = page.locator("#advanced-dag");
    await dag.locator("summary").click();
    await expect(dag).toContainText("interrupt | enqueue");
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    await expect(page.locator(".recovery-turn")).toHaveCount(2);
});
