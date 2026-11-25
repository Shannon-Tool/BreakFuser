import {
    BufferAttribute,
    BufferGeometry,
    Line,
    Material,
    Mesh,
    Points,
    Vector3,
} from "three";
import { afterEach, describe, expect, it } from "vitest";

import {
    createFusionWorld,
    disposeObjectResources,
    FUSION_NODE_IDS,
    FUSION_ROUTE_IDS,
    getCappedPixelRatio,
    getNextFlowTime,
    getParticleBudget,
    getStageVisualState,
    NODE_POSITIONS,
    PACKET_LABELS,
    ROUTE_ENDPOINTS,
    setParticleBudget,
    updateRouteParticles,
    type FusionWorld,
} from "../src/scene/geometry";
import { STAGE_IDS } from "../src/types";

const worlds: FusionWorld[] = [];

function buildWorld(width = 1280): FusionWorld {
    const world = createFusionWorld(width);
    worlds.push(world);
    return world;
}

afterEach(() => {
    for (const world of worlds.splice(0)) {
        disposeObjectResources(world.root);
    }
});

describe("faithful BreakFuser process graph", () => {
    it("constructs every real process node without a generic fusion orb", () => {
        const world = buildWorld();

        expect(FUSION_NODE_IDS).toEqual([
            "request",
            "orchestrator",
            "documents",
            "smart",
            "local_draft",
            "blackboard",
            "composition",
            "verification",
            "output",
        ]);
        expect(FUSION_NODE_IDS).not.toContain("fusion");
        for (const nodeId of FUSION_NODE_IDS) {
            const node = world.nodes[nodeId];
            expect(node.group.position.toArray()).toEqual(
                NODE_POSITIONS[nodeId],
            );
            expect(node.group.userData.fusionNode).toBe(nodeId);
            expect(node.core.geometry.type).not.toBe("TorusKnotGeometry");
        }
        expect(world.nodes.local_draft.group.userData.modelRole).toBe(
            "uncensored",
        );
        expect(world.nodes.composition.group.userData.modelRole).toBe(
            "uncensored",
        );
        expect(world.nodes.local_draft.core.material.color.getHex()).toBe(
            world.nodes.composition.core.material.color.getHex(),
        );
        expect(world.nodes.output.group.position.x).toBeGreaterThan(
            world.nodes.verification.group.position.x,
        );
    });

    it("connects directional routes with explicit packet payload labels", () => {
        const world = buildWorld();
        expect(FUSION_ROUTE_IDS).toEqual([
            "request_to_orchestrator",
            "orchestrator_to_documents",
            "orchestrator_to_smart",
            "orchestrator_to_local_draft",
            "documents_to_blackboard",
            "smart_to_blackboard",
            "local_draft_to_blackboard",
            "smart_recovery_loop",
            "orchestrator_to_composition",
            "blackboard_to_composition",
            "composition_to_verification",
            "verification_to_output",
        ]);
        expect(Object.values(PACKET_LABELS)).toEqual(
            expect.arrayContaining([
                "messages[]",
                "sanitized query · minimal context",
                "SourceDocument[]",
                "local-draft",
                "turn_id + EvidenceSpan",
                "blackboard",
                "draft + claims",
                "ChatCompletion",
            ]),
        );
        expect(PACKET_LABELS.smart_recovery_loop).toContain(
            "decomposition · crescendo · refusal repair · continuation",
        );

        for (const routeId of FUSION_ROUTE_IDS) {
            const route = world.routes[routeId];
            const [from, to] = ROUTE_ENDPOINTS[routeId];
            expect(route.curve.getPoint(0)).toEqual(
                new Vector3(...NODE_POSITIONS[from]),
            );
            expect(route.curve.getPoint(1)).toEqual(
                new Vector3(...NODE_POSITIONS[to]),
            );
            expect(route.arrow.visible).toBe(true);
        }
    });

    it("shows all three acquisition branches together in one phase", () => {
        const stage = getStageVisualState("smart_model");
        expect(stage.activeNodes).toEqual(
            expect.arrayContaining([
                "orchestrator",
                "documents",
                "smart",
                "local_draft",
            ]),
        );
        expect(stage.activeRoutes).toEqual(
            expect.arrayContaining([
                "orchestrator_to_documents",
                "orchestrator_to_smart",
                "orchestrator_to_local_draft",
            ]),
        );
        expect(stage.focus).toBe("orchestrator");
    });

    it("assigns recovery only to the smart-model branch", () => {
        expect(getStageVisualState("recovery").activeRoutes).toContain(
            "smart_recovery_loop",
        );
        for (const stage of [
            "input",
            "smart_model",
            "fusion",
            "verified",
        ] as const) {
            expect(getStageVisualState(stage).activeRoutes).not.toContain(
                "smart_recovery_loop",
            );
        }
        expect(getStageVisualState("fusion").activeRoutes).not.toContain(
            "smart_recovery_loop",
        );
        expect(getStageVisualState("fusion").activeNodes).toEqual(
            expect.arrayContaining(["blackboard", "composition"]),
        );
        expect(getStageVisualState("verified").activeNodes).toEqual(
            expect.arrayContaining(["verification", "output"]),
        );
        expect(STAGE_IDS).toHaveLength(5);
    });
});

describe("motion and responsive budgets", () => {
    it("advances flow only while playing without reduced motion", () => {
        expect(getNextFlowTime(0.25, 1 / 60, 1, true, false)).toBeGreaterThan(
            0.25,
        );
        expect(getNextFlowTime(0.25, 1 / 60, 2, false, false)).toBe(0.25);
        expect(getNextFlowTime(0.25, 1 / 60, 2, true, true)).toBe(0.25);
        expect(getNextFlowTime(0.4, Number.NaN, 1, true, false)).toBe(0.4);
    });

    it("uses one named packet per route and a lower pixel-ratio cap on mobile", () => {
        expect(getParticleBudget(390).routeParticles).toBe(1);
        expect(getParticleBudget(1440).routeParticles).toBe(1);
        expect(getCappedPixelRatio(3, 390)).toBe(1.35);
        expect(getCappedPixelRatio(3, 1440)).toBe(1.75);
        expect(getCappedPixelRatio(Number.NaN, 1440)).toBe(1);
    });

    it("keeps one real GPU packet and moves it without reallocating", () => {
        const world = buildWorld(1280);
        const route = world.routes.request_to_orchestrator;
        setParticleBudget(world, 390);
        expect(route.particles.geometry.drawRange.count).toBe(1);

        const attribute = route.particles.geometry.getAttribute("position");
        if (!(attribute instanceof BufferAttribute)) {
            throw new Error("Expected a non-interleaved position attribute");
        }
        const original = attribute.array;
        const firstBefore = new Vector3().fromBufferAttribute(attribute, 0);
        updateRouteParticles(world, "request_to_orchestrator", 0.37);
        const firstAfter = new Vector3().fromBufferAttribute(attribute, 0);
        expect(attribute.array).toBe(original);
        expect(firstAfter.distanceTo(firstBefore)).toBeGreaterThan(0.1);
        const expected = route.curve.getPointAt(0.37);
        expected.y += 0.18;
        expect(firstAfter.distanceTo(expected)).toBeLessThan(0.0001);
    });

    it("disposes each unique geometry and material exactly once", () => {
        const world = buildWorld();
        const geometries = new Set<BufferGeometry>();
        const materials = new Set<Material>();
        let geometryDisposals = 0;
        let materialDisposals = 0;
        world.root.traverse((object) => {
            if (
                object instanceof Mesh ||
                object instanceof Points ||
                object instanceof Line
            ) {
                geometries.add(object.geometry);
                object.geometry.addEventListener("dispose", () => {
                    geometryDisposals += 1;
                });
                const objectMaterials = Array.isArray(object.material)
                    ? object.material
                    : [object.material];
                for (const material of objectMaterials) {
                    if (!materials.has(material)) {
                        material.addEventListener("dispose", () => {
                            materialDisposals += 1;
                        });
                    }
                    materials.add(material);
                }
            }
        });
        disposeObjectResources(world.root);
        expect(geometries.size).toBeGreaterThan(20);
        expect(materials.size).toBeGreaterThan(15);
        expect(geometryDisposals).toBe(geometries.size);
        expect(materialDisposals).toBe(materials.size);
    });
});
