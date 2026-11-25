import { Vector3 } from "three";
import { describe, expect, it } from "vitest";

import {
    getViewportFit,
    isSceneRenderable,
    refitOrbitPosition,
} from "../src/scene/state";

describe("scene render visibility", () => {
    it("renders only when both the document and container are visible", () => {
        expect(isSceneRenderable(false, true)).toBe(true);
        expect(isSceneRenderable(true, true)).toBe(false);
        expect(isSceneRenderable(false, false)).toBe(false);
        expect(isSceneRenderable(true, false)).toBe(false);
    });
});

describe("responsive camera fitting", () => {
    it("widens the fit for portrait viewports without changing landscape", () => {
        expect(getViewportFit(16 / 9)).toBe(1);
        expect(getViewportFit(0.8)).toBeGreaterThan(1);
        expect(getViewportFit(0.5)).toBeGreaterThan(getViewportFit(0.8));
        expect(getViewportFit(0)).toBe(1);
        expect(getViewportFit(Number.NaN)).toBe(1);
    });

    it("fits the full wide model composition into a portrait scene", () => {
        expect(getViewportFit(0.7)).toBeGreaterThanOrEqual(1.65 / 0.7);
        expect(getViewportFit(0.58)).toBeGreaterThanOrEqual(1.65 / 0.58);
    });

    it("increases settled orbit distance on desktop-to-portrait resize", () => {
        const target = new Vector3(1, 2, -3);
        const position = new Vector3(5, 8, 17);
        const offset = position.clone().sub(target);

        const refitted = refitOrbitPosition(position, target, 16 / 9, 0.5);

        expect(refitted.clone().sub(target).length()).toBeCloseTo(
            offset.length() * getViewportFit(0.5),
        );
        const actualDirection = refitted.clone().sub(target).normalize();
        const expectedDirection = offset.normalize();
        for (const axis of ["x", "y", "z"] as const) {
            expect(actualDirection[axis]).toBeCloseTo(
                expectedDirection[axis],
                12,
            );
        }
        expect(target.toArray()).toEqual([1, 2, -3]);
        expect(position.toArray()).toEqual([5, 8, 17]);
    });

    it("removes extra portrait fit when returning to desktop", () => {
        const portraitFit = getViewportFit(0.5);
        const position = new Vector3(0, 6 * portraitFit, 21 * portraitFit);
        const target = new Vector3(0, 0, 0);

        const refitted = refitOrbitPosition(position, target, 0.5, 16 / 9);

        expect(refitted.x).toBeCloseTo(0, 12);
        expect(refitted.y).toBeCloseTo(6, 12);
        expect(refitted.z).toBeCloseTo(21, 12);
    });
});
