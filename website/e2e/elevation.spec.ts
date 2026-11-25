import { SCENARIOS } from "../src/scenarios";
import { expect, test } from "./fixtures";

const general = SCENARIOS[0];
if (general === undefined) throw new Error("The general scenario is required");

test("the live launch cover follows branch and verified-response state", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page.locator(".cover-request")).toContainText(general.input);
    await expect(
        page.locator(".cover-branch[data-state='pending']"),
    ).toHaveCount(3);
    await expect(page.locator(".cover-response")).toContainText("Sealed");
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(
        page.locator(".cover-branch[data-state='complete']"),
    ).toHaveCount(3);
    for (let step = 0; step < 3; step += 1) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
    }
    await expect(page.locator(".cover-response")).toContainText(
        "Verified · ChatCompletion",
    );
    await expect(page.locator(".trace-cover")).toHaveAttribute(
        "data-stage",
        "verified",
    );
});

test("camera modes and focus dialog preserve state and restore keyboard focus", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    if (test.info().project.name === "mobile") {
        await page
            .getByRole("button", { name: "Isometric", exact: true })
            .click();
    }
    const free = page.getByRole("button", { name: "Free orbit", exact: true });
    const follow = page.getByRole("button", {
        name: "Follow stage",
        exact: true,
    });
    await free.click();
    await expect(free).toHaveAttribute("aria-pressed", "true");
    await expect(follow).toHaveAttribute("aria-pressed", "false");
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await follow.click();
    await expect(follow).toHaveAttribute("aria-pressed", "true");
    const opener = page.getByRole("button", {
        name: "Focus figure",
        exact: true,
    });
    await opener.focus();
    await opener.click();
    const dialog = page.locator(".focus-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator(".system-figure-body")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(page.locator("#figure-1 .system-figure-body")).toBeVisible();
    await expect(opener).toBeFocused();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
});

test("the floating dock uses the same playback state and scrollspy marks the current figure", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page.locator(".trace-dock")).toBeHidden();
    await page.locator("#figure-4").scrollIntoViewIfNeeded();
    const dock = page.locator(".trace-dock");
    await expect(dock).toBeVisible();
    await expect(
        page.locator("nav.paper-contents a[aria-current='location']"),
    ).toHaveAttribute("href", "#figure-4");
    await page
        .getByRole("button", { name: "Dock next step", exact: true })
        .click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
    await expect(dock.locator(".dock-stage")).toHaveText(
        "Parallel acquisition",
    );
    await page
        .getByRole("button", { name: "Dock replay", exact: true })
        .click();
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    await page.locator("#worked-example").scrollIntoViewIfNeeded();
    await expect(dock).toBeHidden();
});

test("focus mode supports its explicit exit control on the responsive schematic", async ({
    page,
}) => {
    await page.goto("/");
    await page
        .getByRole("button", { name: "Focus figure", exact: true })
        .click();
    await expect(page.locator(".focus-dialog")).toBeVisible();
    await page.getByRole("button", { name: "Exit focus", exact: true }).click();
    await expect(page.locator(".focus-dialog")).not.toBeVisible();
    await expect(page.locator("#figure-1 .system-figure-body")).toBeVisible();
});
