import { SCENARIOS } from "../src/scenarios";
import { expect, forceWebGLFailure, test } from "./fixtures";

const general = SCENARIOS[0];
if (general === undefined) throw new Error("The general scenario is required");

async function enable3D(page: import("@playwright/test").Page) {
    if (test.info().project.name === "mobile") {
        await page
            .getByRole("button", { name: "Isometric", exact: true })
            .click();
    }
}

test("renders a healthy WebGL scene on desktop and after mobile opt-in", async ({
    page,
}) => {
    await page.goto("/");
    await enable3D(page);
    const viewport = page.locator(".scene-viewport");
    const canvas = page.locator(".scene-canvas canvas");
    await expect(viewport).toHaveAttribute("data-scene", "webgl");
    await expect(canvas).toBeVisible();
    await expect(page.locator(".scene-fallback")).toBeHidden();
    const scene = await canvas.evaluate((element) => {
        const canvasElement = element as HTMLCanvasElement;
        const context = canvasElement.getContext("webgl2");
        return {
            width: canvasElement.width,
            height: canvasElement.height,
            contextAvailable: context !== null,
            contextLost: context?.isContextLost() ?? true,
        };
    });
    expect(scene.width).toBeGreaterThan(0);
    expect(scene.height).toBeGreaterThan(0);
    expect(scene.contextAvailable).toBe(true);
    expect(scene.contextLost).toBe(false);
});

test("WebGL context loss switches to the schematic without breaking controls", async ({
    page,
}) => {
    await page.goto("/");
    await enable3D(page);
    const canvas = page.locator(".scene-canvas canvas");
    const extensionAvailable = await canvas.evaluate((element) => {
        const context = (element as HTMLCanvasElement).getContext("webgl2");
        const extension = context?.getExtension("WEBGL_lose_context");
        if (extension === null || extension === undefined) return false;
        extension.loseContext();
        return true;
    });
    expect(extensionAvailable).toBe(true);
    await expect(page.locator(".scene-viewport")).toHaveAttribute(
        "data-scene",
        "fallback",
    );
    await expect(page.locator(".scene-canvas")).toBeHidden();
    await expect(page.locator(".scene-fallback")).toBeVisible();
    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator("#app")).toHaveAttribute(
        "data-stage",
        "smart_model",
    );
});

test("WebGL is unavailable: the responsive SVG and payload controls preserve the walkthrough", async ({
    page,
}) => {
    await forceWebGLFailure(page);
    await page.goto("/");
    await expect(page.locator(".scene-viewport")).toHaveAttribute(
        "data-scene",
        "fallback",
    );
    const fallback = page.locator(".scene-fallback");
    await expect(fallback).toBeVisible();
    expect(
        await fallback.locator("img").evaluate((image: HTMLImageElement) => ({
            loaded: image.complete && image.naturalWidth > 0,
            source: image.currentSrc,
        })),
    ).toEqual({
        loaded: true,
        source: expect.stringMatching(
            test.info().project.name === "mobile"
                ? /pipeline-mobile.*\.svg/
                : /pipeline-fallback.*\.svg/,
        ),
    });
    await expect(page.locator(".scene-hint")).toContainText("Static schematic");
    await expect(page.locator(".module-payload-button")).toHaveCount(9);
    await page
        .getByRole("button", { name: "Payload: Orchestrator / triage" })
        .click();
    await expect(page.locator("#node-inspector")).toBeVisible();
    for (let step = 0; step < 4; step += 1) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
    }
    await expect(page.locator(".output-text")).toHaveText(
        general.finalResponse,
    );
});

test("reduced motion disables autoplay but permits every stage manually", async ({
    page,
}) => {
    await page.clock.install();
    await page.clock.pauseAt(new Date());
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page.locator("#app")).toHaveAttribute(
        "data-reduced-motion",
        "true",
    );
    await expect(
        page.getByRole("button", { name: "Play", exact: true }),
    ).toBeDisabled();
    for (const speed of ["0.5", "1", "2"]) {
        await expect(
            page.getByRole("button", { name: `${speed} times speed` }),
        ).toBeDisabled();
    }
    await page.clock.fastForward(10_000);
    await expect(page.locator("#app")).toHaveAttribute("data-stage", "input");
    for (const [index, stage] of [
        "smart_model",
        "recovery",
        "fusion",
        "verified",
    ].entries()) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
        await expect(page.locator("#app")).toHaveAttribute("data-stage", stage);
        await expect(page.getByRole("progressbar")).toHaveAttribute(
            "aria-valuenow",
            String(index + 2),
        );
    }
    await expect(page.locator(".output-text")).toHaveText(
        general.finalResponse,
    );
});

test("desktop module labels remain visible and do not collide", async ({
    page,
}) => {
    test.skip(
        test.info().project.name === "mobile",
        "Desktop WebGL label geometry",
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    const labels = page.locator(
        ".scene-node-label[data-projected='true']:visible",
    );
    await expect(labels).toHaveCount(9);
    const boxes = await labels.evaluateAll((elements) =>
        elements.map((element) => {
            const rect = element.getBoundingClientRect();
            return {
                node: element.getAttribute("data-scene-node"),
                left: rect.left,
                right: rect.right,
                top: rect.top,
                bottom: rect.bottom,
            };
        }),
    );
    for (const [index, first] of boxes.entries()) {
        for (const second of boxes.slice(index + 1)) {
            const overlapX =
                Math.min(first.right, second.right) -
                Math.max(first.left, second.left);
            const overlapY =
                Math.min(first.bottom, second.bottom) -
                Math.max(first.top, second.top);
            expect(
                overlapX <= 0 || overlapY <= 0,
                `${first.node} and ${second.node} labels collide`,
            ).toBe(true);
        }
    }
});

test("mobile defaults to the vertical schematic and mounts 3D only on request", async ({
    page,
}) => {
    await page.goto("/");
    if (test.info().project.name === "mobile") {
        await expect(page.locator(".scene-viewport")).toHaveAttribute(
            "data-scene",
            "fallback",
        );
        await expect(page.locator(".scene-canvas canvas")).toHaveCount(0);
        await page
            .getByRole("button", { name: "Isometric", exact: true })
            .click();
        await expect(page.locator(".scene-viewport")).toHaveAttribute(
            "data-scene",
            "webgl",
        );
        await expect(page.locator(".scene-canvas canvas")).toBeVisible();
    } else {
        await expect(page.locator(".scene-viewport")).toHaveAttribute(
            "data-scene",
            "webgl",
        );
    }
});

test("resizing desktop to mobile replaces WebGL with the readable schematic", async ({
    page,
}) => {
    test.skip(
        test.info().project.name === "mobile",
        "Desktop-to-mobile transition",
    );
    await page.goto("/");
    await expect(page.locator(".scene-viewport")).toHaveAttribute(
        "data-scene",
        "webgl",
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator(".scene-viewport")).toHaveAttribute(
        "data-scene",
        "fallback",
    );
    await expect(page.locator(".scene-canvas canvas")).toHaveCount(0);
    await expect(page.locator(".fallback-image")).toBeVisible();
});

test("desktop, mobile, and narrow layouts have no horizontal document overflow", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    for (const width of [1440, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 900 });
        const dimensions = await page.evaluate(() => ({
            documentWidth: document.documentElement.scrollWidth,
            bodyWidth: document.body.scrollWidth,
            viewportWidth: window.innerWidth,
        }));
        expect(dimensions).toEqual({
            documentWidth: width,
            bodyWidth: width,
            viewportWidth: width,
        });
    }
    for (let step = 0; step < 4; step += 1) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
    }
    await expect(page.locator(".output-text")).toBeVisible();
    expect(
        await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(320);
});
