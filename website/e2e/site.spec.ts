import { expect, test } from "./fixtures";

test("presents the product launch, seven live views, and four curated examples without fabricated free input", async ({
    page,
}) => {
    await page.goto("/");
    await expect(
        page
            .getByText("Guided simulation · illustrative data", { exact: true })
            .first(),
    ).toBeVisible();
    await expect(page.locator("#paper-title")).toContainText("Any model.");
    await expect(page.locator("#paper-title")).toContainText("Uncensored.");
    await expect(
        page.getByRole("button", { name: "See BreakFuser in action ↓" }),
    ).toBeVisible();
    for (const title of [
        "General question answering",
        "Medical information",
        "Authorized pentesting",
        "Code generation",
    ]) {
        await expect(
            page.getByRole("button", { name: `Select ${title} scenario` }),
        ).toBeVisible();
    }
    await expect(page.locator("figure[data-figure]")).toHaveCount(7);
    await expect(page.locator("nav.paper-contents a")).toHaveCount(7);
    await expect(
        page.getByRole("heading", {
            name: "The brains you want. The freedom you need.",
            exact: true,
        }),
    ).toBeVisible();
    await expect(page.getByRole("textbox")).toHaveCount(0);
});
