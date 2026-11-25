import { describe, expect, it } from "vitest";

import {
    getParticleBudget,
    NODE_POSITIONS,
    PALETTE,
} from "../src/scene/geometry";
import { getCameraPreset } from "../src/scene/state";

describe("academic three-dimensional system figure", () => {
    it("uses an ink drafting chamber and separates acquisition lanes in depth", () => {
        expect(PALETTE.background).toBe(0x101b24);
        expect(
            new Set([
                NODE_POSITIONS.documents[2],
                NODE_POSITIONS.smart[2],
                NODE_POSITIONS.local_draft[2],
            ]).size,
        ).toBe(3);
        expect(getParticleBudget(1440).routeParticles).toBe(1);
        expect(getParticleBudget(390).routeParticles).toBe(1);
    });

    it("provides orthographic isometric and top camera presets", () => {
        const isometric = getCameraPreset("isometric", 1.5);
        const top = getCameraPreset("top", 1.5);
        expect(isometric.position.y).toBeGreaterThan(0);
        expect(isometric.position.z).toBeGreaterThan(0);
        expect(top.position.y).toBeGreaterThan(isometric.position.y);
        expect(top.position.z).toBe(0);
        expect(top.target.toArray()).toEqual([0, 0, 0]);
    });
});
