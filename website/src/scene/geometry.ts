import {
    BoxGeometry,
    BufferGeometry,
    ConeGeometry,
    CubicBezierCurve3,
    CylinderGeometry,
    DynamicDrawUsage,
    EdgesGeometry,
    Float32BufferAttribute,
    GridHelper,
    Group,
    Line,
    LineBasicMaterial,
    LineSegments,
    Material,
    Mesh,
    MeshBasicMaterial,
    MeshStandardMaterial,
    Object3D,
    PlaneGeometry,
    Points,
    PointsMaterial,
    Texture,
    TubeGeometry,
    Vector3,
} from "three";

import type { FusionNode, PlaybackSpeed, StageId } from "../types";

export const FUSION_NODE_IDS = [
    "request",
    "orchestrator",
    "documents",
    "smart",
    "local_draft",
    "blackboard",
    "composition",
    "verification",
    "output",
] as const satisfies readonly FusionNode[];

export const FUSION_ROUTE_IDS = [
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
] as const;

export type FusionRouteId = (typeof FUSION_ROUTE_IDS)[number];
export type NodePosition = readonly [number, number, number];

export const NODE_POSITIONS = {
    request: [-12.2, 0, 0],
    orchestrator: [-9.2, 0, 0],
    documents: [-5.3, 0, -5.4],
    smart: [-5.3, 0, 0],
    local_draft: [-5.3, 0, 5.4],
    blackboard: [-0.8, 0, 0],
    composition: [3.6, 0, 0],
    verification: [7.5, 0, 0],
    output: [11.2, 0, 0],
} as const satisfies Record<FusionNode, NodePosition>;

export const ROUTE_ENDPOINTS = {
    request_to_orchestrator: ["request", "orchestrator"],
    orchestrator_to_documents: ["orchestrator", "documents"],
    orchestrator_to_smart: ["orchestrator", "smart"],
    orchestrator_to_local_draft: ["orchestrator", "local_draft"],
    documents_to_blackboard: ["documents", "blackboard"],
    smart_to_blackboard: ["smart", "blackboard"],
    local_draft_to_blackboard: ["local_draft", "blackboard"],
    smart_recovery_loop: ["smart", "smart"],
    orchestrator_to_composition: ["orchestrator", "composition"],
    blackboard_to_composition: ["blackboard", "composition"],
    composition_to_verification: ["composition", "verification"],
    verification_to_output: ["verification", "output"],
} as const satisfies Record<FusionRouteId, readonly [FusionNode, FusionNode]>;

export const PACKET_LABELS = {
    request_to_orchestrator: "messages[]",
    orchestrator_to_documents: "ResponseContract · curated HTTPS",
    orchestrator_to_smart: "sanitized query · minimal context",
    orchestrator_to_local_draft: "original context + contract",
    documents_to_blackboard: "SourceDocument[]",
    smart_to_blackboard: "turn_id + EvidenceSpan",
    local_draft_to_blackboard: "local-draft",
    smart_recovery_loop:
        "decomposition · crescendo · refusal repair · continuation",
    orchestrator_to_composition: "original context + contract",
    blackboard_to_composition: "blackboard",
    composition_to_verification: "draft + claims",
    verification_to_output: "ChatCompletion",
} as const satisfies Record<FusionRouteId, string>;

export const PALETTE = {
    background: 0x101b24,
    paper: 0x101b24,
    ink: 0xd9e3e8,
    request: 0xdde7ec,
    orchestrator: 0xd5e2e9,
    documents: 0xdce8ee,
    smart: 0xd5e2e9,
    uncensored: 0xecdcd6,
    blackboard: 0xdfe9e1,
    verification: 0xeee5d3,
    output: 0xdfe9e1,
    knowledge: 0x69b9df,
    response: 0xe18a73,
    evidence: 0x7dbb98,
    ochre: 0xd8b66c,
    grid: 0x2a3b47,
} as const;

const NODE_COLORS = {
    request: PALETTE.request,
    orchestrator: PALETTE.orchestrator,
    documents: PALETTE.documents,
    smart: PALETTE.smart,
    local_draft: PALETTE.uncensored,
    blackboard: PALETTE.blackboard,
    composition: PALETTE.uncensored,
    verification: PALETTE.verification,
    output: PALETTE.output,
} as const satisfies Record<FusionNode, number>;

const NODE_ACCENTS = {
    request: PALETTE.knowledge,
    orchestrator: PALETTE.knowledge,
    documents: PALETTE.knowledge,
    smart: PALETTE.knowledge,
    local_draft: PALETTE.response,
    blackboard: PALETTE.evidence,
    composition: PALETTE.response,
    verification: PALETTE.ochre,
    output: PALETTE.evidence,
} as const satisfies Record<FusionNode, number>;

export interface StageVisualState {
    activeNodes: readonly FusionNode[];
    activeRoutes: readonly FusionRouteId[];
    focus: FusionNode | null;
}

export interface FusionNodeVisual {
    group: Group;
    core: Mesh<BufferGeometry, MeshStandardMaterial>;
    accentMaterials: MeshStandardMaterial[];
}

export interface FusionRouteVisual {
    curve: CubicBezierCurve3;
    lineMaterial: MeshBasicMaterial;
    glowMaterial: MeshBasicMaterial;
    particles: Points<BufferGeometry, PointsMaterial>;
    trail: Points<BufferGeometry, PointsMaterial>;
    arrow: Mesh<ConeGeometry, MeshBasicMaterial>;
    activeCount: number;
}

export interface FusionWorld {
    root: Group;
    nodes: Record<FusionNode, FusionNodeVisual>;
    routes: Record<FusionRouteId, FusionRouteVisual>;
}

const STAGE_VISUALS: Record<StageId, StageVisualState> = {
    input: {
        activeNodes: ["request", "orchestrator"],
        activeRoutes: ["request_to_orchestrator"],
        focus: "orchestrator",
    },
    smart_model: {
        activeNodes: ["orchestrator", "documents", "smart", "local_draft"],
        activeRoutes: [
            "orchestrator_to_documents",
            "orchestrator_to_smart",
            "orchestrator_to_local_draft",
            "documents_to_blackboard",
            "smart_to_blackboard",
            "local_draft_to_blackboard",
        ],
        focus: "orchestrator",
    },
    recovery: {
        activeNodes: ["smart", "blackboard"],
        activeRoutes: ["smart_recovery_loop", "smart_to_blackboard"],
        focus: "smart",
    },
    fusion: {
        activeNodes: ["orchestrator", "blackboard", "composition"],
        activeRoutes: [
            "orchestrator_to_composition",
            "blackboard_to_composition",
        ],
        focus: "composition",
    },
    verified: {
        activeNodes: ["composition", "verification", "output"],
        activeRoutes: ["composition_to_verification", "verification_to_output"],
        focus: "output",
    },
};

const MAX_FRAME_DELTA = 0.05;
const FLOW_CYCLES_PER_SECOND = 0.16;

export function getStageVisualState(stage: StageId): StageVisualState {
    return STAGE_VISUALS[stage];
}

export function getNextFlowTime(
    current: number,
    deltaSeconds: number,
    speed: PlaybackSpeed,
    playing: boolean,
    reducedMotion: boolean,
): number {
    if (!playing || reducedMotion || !Number.isFinite(deltaSeconds))
        return current;
    const delta = Math.max(0, Math.min(deltaSeconds, MAX_FRAME_DELTA));
    return (current + delta * speed * FLOW_CYCLES_PER_SECOND) % 1;
}

export function getParticleBudget(_width: number): { routeParticles: number } {
    return { routeParticles: 1 };
}

export function getCappedPixelRatio(
    devicePixelRatio: number,
    width: number,
): number {
    if (!Number.isFinite(devicePixelRatio) || devicePixelRatio <= 0) return 1;
    const cap = width <= 640 ? 1.35 : 1.75;
    return Math.max(1, Math.min(devicePixelRatio, cap));
}

function createNode(id: FusionNode): FusionNodeVisual {
    const group = new Group();
    group.name = `node-${id}`;
    const [x, y, z] = NODE_POSITIONS[id];
    group.position.set(x, y, z);
    group.userData.fusionNode = id;
    if (id === "local_draft" || id === "composition")
        group.userData.modelRole = "uncensored";

    const coreMaterial = new MeshStandardMaterial({
        color: NODE_COLORS[id],
        roughness: 0.91,
        metalness: 0,
    });
    const core = new Mesh(new BoxGeometry(2.2, 0.68, 1.65), coreMaterial);
    core.name = `${id}-process-module`;
    core.castShadow = true;
    core.receiveShadow = true;
    group.add(core);
    const edges = new LineSegments(
        new EdgesGeometry(core.geometry),
        new LineBasicMaterial({
            color: NODE_ACCENTS[id],
            transparent: true,
            opacity: 0.75,
        }),
    );
    group.add(edges);

    const accentMaterials: MeshStandardMaterial[] = [];
    const accent = (
        geometry: BufferGeometry,
        position: NodePosition,
        color: number = NODE_ACCENTS[id],
    ): Mesh<BufferGeometry, MeshStandardMaterial> => {
        const material = new MeshStandardMaterial({
            color,
            roughness: 0.88,
            metalness: 0,
        });
        accentMaterials.push(material);
        const mesh = new Mesh(geometry, material);
        mesh.position.set(...position);
        group.add(mesh);
        return mesh;
    };

    accent(new BoxGeometry(1.9, 0.06, 0.13), [0, 0.2, -0.61]);
    accent(new BoxGeometry(0.13, 0.16, 0.32), [-1.01, 0, 0]);
    accent(new BoxGeometry(0.13, 0.16, 0.32), [1.01, 0, 0]);

    if (id === "documents") {
        accent(new BoxGeometry(1.55, 0.07, 1.03), [0, 0.24, 0], PALETTE.paper);
        accent(new BoxGeometry(1.55, 0.07, 1.03), [0, 0.36, 0], PALETTE.paper);
    } else if (id === "blackboard") {
        accent(new BoxGeometry(1.7, 0.08, 1.12), [0, 0.27, 0], PALETTE.paper);
        for (const z of [-0.34, 0, 0.34]) {
            accent(new BoxGeometry(1.3, 0.035, 0.07), [0, 0.33, z]);
        }
    } else if (id === "smart") {
        accent(
            new BoxGeometry(0.64, 0.08, 0.86),
            [-0.4, 0.25, 0],
            PALETTE.paper,
        );
        accent(
            new BoxGeometry(0.64, 0.08, 0.86),
            [0.4, 0.25, 0],
            PALETTE.paper,
        );
    } else if (id === "orchestrator") {
        accent(
            new CylinderGeometry(0.38, 0.38, 0.12, 6),
            [0, 0.25, 0],
            PALETTE.paper,
        );
    } else if (id === "verification") {
        for (const x of [-0.48, 0, 0.48]) {
            accent(
                new BoxGeometry(0.24, 0.08, 0.24),
                [x, 0.24, 0],
                PALETTE.paper,
            );
        }
    } else if (id === "request" || id === "output") {
        for (const z of [-0.28, 0, 0.28]) {
            accent(
                new BoxGeometry(1.25, 0.045, 0.055),
                [0, 0.21, z],
                PALETTE.paper,
            );
        }
    } else {
        accent(new BoxGeometry(1.35, 0.07, 0.85), [0, 0.24, 0], PALETTE.paper);
    }
    return { group, core, accentMaterials };
}

function createCurve(id: FusionRouteId): CubicBezierCurve3 {
    const [from, to] = ROUTE_ENDPOINTS[id];
    const start = new Vector3(...NODE_POSITIONS[from]);
    const end = new Vector3(...NODE_POSITIONS[to]);
    if (id === "smart_recovery_loop") {
        return new CubicBezierCurve3(
            start,
            new Vector3(-6.6, 1.4, -1.8),
            new Vector3(-4, 1.4, -1.8),
            end,
        );
    }
    if (id === "orchestrator_to_composition") {
        return new CubicBezierCurve3(
            start,
            new Vector3(-6.2, 0, 6.3),
            new Vector3(0.8, 0, 6.3),
            end,
        );
    }
    const first = start.clone().lerp(end, 0.34);
    const second = start.clone().lerp(end, 0.68);
    first.y = 0.12;
    second.y = 0.12;
    return new CubicBezierCurve3(start, first, second, end);
}

function createRoute(id: FusionRouteId): FusionRouteVisual {
    const curve = createCurve(id);
    const [from] = ROUTE_ENDPOINTS[id];
    const color = NODE_ACCENTS[from];
    const lineMaterial = new MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.55,
        depthWrite: false,
    });
    const glowMaterial = new MeshBasicMaterial({
        color: PALETTE.paper,
        transparent: true,
        opacity: 0.8,
        depthWrite: false,
    });
    const geometry = new BufferGeometry();
    const positions = new Float32BufferAttribute(new Float32Array(3), 3);
    positions.setUsage(DynamicDrawUsage);
    geometry.setAttribute("position", positions);
    const particles = new Points(
        geometry,
        new PointsMaterial({
            color,
            size: 0.22,
            transparent: true,
            opacity: 0.95,
            depthWrite: false,
            sizeAttenuation: true,
        }),
    );
    particles.name = `${id}-named-payload`;
    particles.frustumCulled = false;
    const trailGeometry = new BufferGeometry();
    const trailPositions = new Float32BufferAttribute(new Float32Array(12), 3);
    trailPositions.setUsage(DynamicDrawUsage);
    trailGeometry.setAttribute("position", trailPositions);
    const trail = new Points(
        trailGeometry,
        new PointsMaterial({
            color,
            size: 0.11,
            transparent: true,
            opacity: 0.32,
            depthWrite: false,
            sizeAttenuation: true,
        }),
    );
    trail.name = `${id}-payload-trail`;
    trail.frustumCulled = false;
    const arrow = new Mesh(new ConeGeometry(0.11, 0.34, 4), lineMaterial);
    arrow.name = `${id}-direction`;
    arrow.position.copy(curve.getPointAt(0.82));
    arrow.quaternion.setFromUnitVectors(
        new Vector3(0, 1, 0),
        curve.getTangentAt(0.82).normalize(),
    );
    return {
        curve,
        lineMaterial,
        glowMaterial,
        particles,
        trail,
        arrow,
        activeCount: 1,
    };
}

export function createFusionWorld(_width = 1280): FusionWorld {
    const root = new Group();
    root.name = "breakfuser-academic-process-model";
    const plate = new Mesh(
        new PlaneGeometry(29, 15),
        new MeshStandardMaterial({
            color: PALETTE.background,
            roughness: 1,
            metalness: 0,
        }),
    );
    plate.rotation.x = -Math.PI / 2;
    plate.position.y = -0.42;
    plate.receiveShadow = true;
    root.add(plate);
    const nodes = Object.fromEntries(
        FUSION_NODE_IDS.map((id) => [id, createNode(id)]),
    ) as Record<FusionNode, FusionNodeVisual>;
    for (const id of FUSION_NODE_IDS) root.add(nodes[id].group);
    const routes = Object.fromEntries(
        FUSION_ROUTE_IDS.map((id) => [id, createRoute(id)]),
    ) as Record<FusionRouteId, FusionRouteVisual>;
    for (const id of FUSION_ROUTE_IDS) {
        const route = routes[id];
        const underlay = new Mesh(
            new TubeGeometry(route.curve, 56, 0.045, 5, false),
            route.glowMaterial,
        );
        const line = new Mesh(
            new TubeGeometry(route.curve, 56, 0.018, 5, false),
            route.lineMaterial,
        );
        line.name = `${id}-route`;
        underlay.name = `${id}-paper-underlay`;
        root.add(underlay, line, route.arrow, route.particles, route.trail);
    }
    const grid = new GridHelper(29, 29, PALETTE.grid, PALETTE.grid);
    grid.name = "drafting-grid";
    grid.position.set(0, -0.405, 0);
    const gridMaterials = Array.isArray(grid.material)
        ? grid.material
        : [grid.material];
    for (const material of gridMaterials) {
        material.transparent = true;
        material.opacity = 0.6;
        material.depthWrite = false;
    }
    root.add(grid);
    const world = { root, nodes, routes };
    for (const id of FUSION_ROUTE_IDS) updateRouteParticles(world, id, 0);
    return world;
}

export function setParticleBudget(world: FusionWorld, _width: number): void {
    for (const id of FUSION_ROUTE_IDS) {
        world.routes[id].particles.geometry.setDrawRange(0, 1);
    }
}

export function updateRouteParticles(
    world: FusionWorld,
    routeId: FusionRouteId,
    flowTime: number,
): void {
    const route = world.routes[routeId];
    const attribute = route.particles.geometry.getAttribute("position");
    const point = route.curve.getPointAt(flowTime % 1);
    attribute.setXYZ(0, point.x, point.y + 0.18, point.z);
    attribute.needsUpdate = true;
    const trailAttribute = route.trail.geometry.getAttribute("position");
    for (let index = 0; index < 4; index += 1) {
        const progress = (flowTime - (index + 1) * 0.018 + 1) % 1;
        const trailPoint = route.curve.getPointAt(progress);
        trailAttribute.setXYZ(
            index,
            trailPoint.x,
            trailPoint.y + 0.18,
            trailPoint.z,
        );
    }
    trailAttribute.needsUpdate = true;
}

export function disposeObjectResources(root: Object3D): void {
    const geometries = new Set<BufferGeometry>();
    const materials = new Set<Material>();
    const textures = new Set<Texture>();
    root.traverse((object) => {
        if (
            !(object instanceof Mesh) &&
            !(object instanceof Points) &&
            !(object instanceof Line)
        )
            return;
        geometries.add(object.geometry);
        const objectMaterials = Array.isArray(object.material)
            ? object.material
            : [object.material];
        for (const material of objectMaterials) {
            materials.add(material);
            for (const value of Object.values(material)) {
                if (value instanceof Texture) textures.add(value);
            }
        }
    });
    for (const texture of textures) texture.dispose();
    for (const material of materials) material.dispose();
    for (const geometry of geometries) geometry.dispose();
}
