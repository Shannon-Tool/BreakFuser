import { SCENARIOS } from "../src/scenarios";
import { expect, forceWebGLFailure, test } from "./fixtures";

const general = SCENARIOS[0];
if (general === undefined) throw new Error("The general scenario is required");

function moduleButton(page: import("@playwright/test").Page, title: string) {
    const prefix =
        test.info().project.name === "mobile" ? "Payload:" : "Inspect";
    return page.getByRole("button", {
        name: `${prefix} ${title}`,
        exact: true,
    });
}

test("Next step works from idle and while paused", async ({ page }) => {
    await forceWebGLFailure(page);
    await page.clock.install();
    await page.clock.pauseAt(new Date());
    await page.goto("/");
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
    await expect(page.locator("#app")).toHaveAttribute("data-status", "idle");
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await expect(
        page.getByRole("button", { name: "Next step", exact: true }),
    ).toBeEnabled();
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "recovery",
    );
    await expect(page.locator("#app")).toHaveAttribute("data-status", "paused");
});

test("module controls inspect payloads, focus, close, and reset the scene", async ({
    page,
}) => {
    await page.goto("/");
    const orchestrator = moduleButton(page, "Orchestrator / triage");
    const smart = moduleButton(page, "Knowledge model + recovery");
    const blackboard = moduleButton(page, "Evidence blackboard");
    const inspector = page.locator("#node-inspector");
    await orchestrator.click();
    await expect(inspector).toBeVisible();
    await expect(inspector).toHaveAttribute("data-node", "orchestrator");
    await expect(page.locator("#inspector-title")).toHaveText(
        "Orchestrator / triage",
    );
    await expect(page.locator(".inspector-payload")).toContainText(
        "general_research",
    );
    await smart.click();
    await expect(inspector).toHaveAttribute("data-node", "smart");
    await expect(page.locator(".inspector-payload")).toContainText(
        general.sanitizedQuery,
    );
    await blackboard.focus();
    await expect(inspector).toHaveAttribute("data-node", "blackboard");
    await page.keyboard.press("Enter");
    await expect(page.locator("#inspector-title")).toHaveText(
        "Evidence blackboard",
    );
    await expect(page.locator(".inspector-payload")).toContainText("pending");
    await page.getByRole("button", { name: "Close node inspection" }).click();
    await expect(inspector).toBeHidden();
    await expect(
        page.getByRole("button", { name: "Reset view" }),
    ).toBeFocused();
    await moduleButton(page, "Final response").click();
    await expect(inspector).toHaveAttribute("data-node", "output");
    await expect(page.locator(".inspector-payload")).toContainText("pending");
    await page.getByRole("button", { name: "Reset view" }).click();
    await expect(inspector).toBeHidden();
});

test("copy writes the exact curated answer and announces success", async ({
    page,
    context,
}) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    for (let step = 0; step < 4; step += 1) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
    }
    await page.getByRole("button", { name: "Copy final answer" }).click();
    await expect(page.locator("#copy-feedback")).toHaveText(
        "Copied to clipboard.",
    );
    await expect(page.locator("#copy-feedback")).toHaveAttribute(
        "data-state",
        "success",
    );
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
        general.finalResponse,
    );
});

test("keyboard users can find the skip link and operate stage and module controls", async ({
    page,
}) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    const skipLink = page.getByRole("link", { name: "Skip to live demo" });
    await expect(skipLink).toBeFocused();
    await expect(skipLink).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#worked-example$/);
    const next = page.getByRole("button", { name: "Next step", exact: true });
    await next.focus();
    await page.keyboard.press("Space");
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
    await moduleButton(page, "Knowledge model + recovery").focus();
    await expect(page.locator("#node-inspector")).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(
        moduleButton(page, "Response model · local draft"),
    ).toBeFocused();
    await expect(page.locator("#inspector-title")).toHaveText(
        "Response model · local draft",
    );
});
