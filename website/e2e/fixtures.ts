import { test as base, expect, type Page } from "@playwright/test";

const unexpectedErrors = new WeakMap<Page, string[]>();
const expectedWebGLFailures = new WeakSet<Page>();

export const test = base.extend({
    page: async ({ page }, use) => {
        const errors: string[] = [];
        unexpectedErrors.set(page, errors);
        page.on("pageerror", (error) => {
            errors.push(`pageerror: ${error.message}`);
        });
        page.on("console", (message) => {
            const isExpectedWebGLFailure =
                expectedWebGLFailures.has(page) &&
                /^(?:THREE\.WebGLRenderer: )+Error creating WebGL context\.$/.test(
                    message.text(),
                );
            if (message.type() === "error" && !isExpectedWebGLFailure) {
                errors.push(`console: ${message.text()}`);
            }
        });
        await use(page);
        unexpectedErrors.delete(page);
        expectedWebGLFailures.delete(page);
        expect(errors, "unexpected browser errors").toEqual([]);
    },
});

export async function forceWebGLFailure(page: Page): Promise<void> {
    expectedWebGLFailures.add(page);
    await page.addInitScript(() => {
        const getContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (
            this: HTMLCanvasElement,
            contextId: string,
            ...args: unknown[]
        ) {
            if (
                contextId === "webgl" ||
                contextId === "webgl2" ||
                contextId === "experimental-webgl"
            ) {
                return null;
            }
            return getContext.call(
                this,
                contextId,
                ...args,
            ) as RenderingContext | null;
        } as typeof getContext;
    });
}

export { expect } from "@playwright/test";
