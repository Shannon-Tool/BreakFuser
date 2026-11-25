import {
    Color,
    DirectionalLight,
    DoubleSide,
    FogExp2,
    GridHelper,
    HemisphereLight,
    Mesh,
    MeshBasicMaterial,
    PerspectiveCamera,
    PlaneGeometry,
    RingGeometry,
    Scene,
    SRGBColorSpace,
    Vector2,
    Vector3,
    WebGLRenderer,
} from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

import type { FusionNode, StageId } from "../types";
import {
    createFusionWorld,
    disposeObjectResources,
    FUSION_NODE_IDS,
    FUSION_ROUTE_IDS,
    getStageVisualState,
    updateRouteParticles,
    type FusionRouteId,
    type FusionWorld,
} from "../scene/geometry";
import type { RecordingView } from "./recordings";

export interface SceneProjection {
    nodes: Record<FusionNode, { x: number; y: number; visible: boolean }>;
    routes: Partial<
        Record<FusionRouteId, { x: number; y: number; visible: boolean }>
    >;
}

const ACTIVE_COLORS: Record<FusionNode, number> = {
    request: 0x7dd3fc,
    orchestrator: 0x7dd3fc,
    documents: 0x7dd3fc,
    smart: 0xc4b5fd,
    local_draft: 0x86efac,
    blackboard: 0x7dd3fc,
    composition: 0x86efac,
    verification: 0xfdba74,
    output: 0x86efac,
};

export class FusionGifScene {
    private readonly scene = new Scene();
    private readonly camera = new PerspectiveCamera(36, 1.6, 0.1, 180);
    private readonly renderer: WebGLRenderer;
    private readonly composer: EffectComposer;
    private readonly world: FusionWorld;
    private readonly rings = new Map<
        FusionNode,
        Mesh<RingGeometry, MeshBasicMaterial>
    >();
    private stage: StageId = "input";
    private activeNodes: readonly FusionNode[] | undefined;
    private activeRoutes: readonly FusionRouteId[] | undefined;

    constructor(
        private readonly container: HTMLElement,
        private readonly onProject: (projection: SceneProjection) => void,
    ) {
        this.renderer = new WebGLRenderer({
            antialias: true,
            alpha: false,
            preserveDrawingBuffer: true,
        });
        this.renderer.outputColorSpace = SRGBColorSpace;
        this.renderer.shadowMap.enabled = true;
        this.renderer.setPixelRatio(1);
        this.scene.background = new Color(0x070b11);
        this.scene.fog = new FogExp2(0x070b11, 0.017);
        this.camera.position.set(16, 19, 29);
        this.camera.lookAt(-0.5, 0, 0);
        this.world = createFusionWorld(1200);
        this.world.root.traverse((object) => {
            if (
                object instanceof Mesh &&
                object.geometry instanceof PlaneGeometry
            )
                object.visible = false;
        });
        for (const id of FUSION_NODE_IDS) {
            const node = this.world.nodes[id];
            const previous = node.core.geometry;
            node.core.geometry = new RoundedBoxGeometry(
                2.2,
                1.15,
                1.65,
                3,
                0.09,
            );
            previous.dispose();
            node.core.material.roughness = 0.46;
            node.core.material.metalness = 0.18;
            node.core.material.emissive.set(ACTIVE_COLORS[id]);
            const ring = new Mesh(
                new RingGeometry(1.28, 1.43, 48),
                new MeshBasicMaterial({
                    color: ACTIVE_COLORS[id],
                    transparent: true,
                    opacity: 0.08,
                    side: DoubleSide,
                    depthWrite: false,
                }),
            );
            ring.rotation.x = -Math.PI / 2;
            ring.position.copy(node.group.position);
            ring.position.y = -0.62;
            this.world.root.add(ring);
            this.rings.set(id, ring);
        }
        this.scene.add(this.world.root);
        const grid = new GridHelper(90, 90, 0x173f52, 0x122e40);
        grid.position.y = -0.63;
        const materials = Array.isArray(grid.material)
            ? grid.material
            : [grid.material];
        for (const material of materials) {
            material.transparent = true;
            material.opacity = 0.38;
            material.depthWrite = false;
        }
        this.scene.add(grid);
        const ambient = new HemisphereLight(0xbfeaff, 0x07111b, 1.3);
        const key = new DirectionalLight(0xe5f6ff, 2.1);
        key.position.set(-8, 18, 12);
        key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        key.shadow.camera.left = -20;
        key.shadow.camera.right = 20;
        key.shadow.camera.top = 16;
        key.shadow.camera.bottom = -16;
        const rim = new DirectionalLight(0x86efac, 0.75);
        rim.position.set(8, 8, -12);
        this.scene.add(ambient, key, rim);
        this.composer = new EffectComposer(this.renderer);
        this.composer.addPass(new RenderPass(this.scene, this.camera));
        this.composer.addPass(
            new UnrealBloomPass(new Vector2(1200, 750), 0.55, 0.55, 0.76),
        );
        this.composer.addPass(new OutputPass());
        container.append(this.renderer.domElement);
        this.resize();
    }

    setVisible(visible: boolean): void {
        this.renderer.domElement.style.display = visible ? "block" : "none";
    }

    setVisual(
        stage: StageId,
        view: RecordingView,
        activeNodes?: readonly FusionNode[],
        activeRoutes?: readonly FusionRouteId[],
    ): void {
        this.stage = stage;
        this.activeNodes = activeNodes;
        this.activeRoutes = activeRoutes;
        let target = -0.5;
        let offset = 16;
        let height = 19;
        let depth = 29;
        if (view === "acquisition" || view === "privacy") {
            target = -3;
            offset = 11;
            height = 18;
            depth = 26;
        } else if (view === "recovery") {
            target = -2;
            offset = 11;
            height = 17;
            depth = 25;
        } else if (view === "blackboard") {
            target = -1;
            offset = 13;
            height = 18;
            depth = 27;
        } else if (view === "composition") {
            target = 1;
            offset = 14;
            height = 18;
            depth = 27;
        } else if (view === "verification") {
            target = 3;
            offset = 14;
            height = 18;
            depth = 28;
        }
        this.camera.position.set(target + offset, height, depth);
        this.camera.lookAt(target, 0, 0);
    }

    resize(): void {
        const width = this.container.clientWidth || 1200;
        const height = this.container.clientHeight || 750;
        this.renderer.setSize(width, height, false);
        this.composer.setSize(width, height);
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
    }

    draw(time: number): void {
        const defaults = getStageVisualState(this.stage);
        const visual = {
            activeNodes: this.activeNodes ?? defaults.activeNodes,
            activeRoutes: this.activeRoutes ?? defaults.activeRoutes,
        };
        for (const [index, id] of FUSION_NODE_IDS.entries()) {
            const active = visual.activeNodes.includes(id);
            const node = this.world.nodes[id];
            const pulse = active ? 1 + Math.sin(time * 3.2 + index) * 0.035 : 1;
            node.group.scale.set(1, pulse, 1);
            node.core.material.emissiveIntensity = active ? 0.52 : 0.035;
            node.core.material.color.set(active ? 0x397d9b : 0x122633);
            if (id === "local_draft" || id === "composition")
                node.core.material.color.set(active ? 0x397d60 : 0x122b25);
            if (id === "verification")
                node.core.material.color.set(active ? 0x8a5c2d : 0x2b241b);
            for (const material of node.accentMaterials) {
                material.emissive.set(ACTIVE_COLORS[id]);
                material.emissiveIntensity = active ? 0.65 : 0.04;
            }
            const ring = this.rings.get(id);
            if (ring !== undefined) {
                ring.material.opacity = active
                    ? 0.65 + Math.sin(time * 3 + index) * 0.12
                    : 0.035;
                ring.scale.setScalar(
                    active ? 1 + Math.sin(time * 2.4 + index) * 0.08 : 1,
                );
            }
        }
        for (const [index, id] of FUSION_ROUTE_IDS.entries()) {
            const active = visual.activeRoutes.includes(id);
            const route = this.world.routes[id];
            route.lineMaterial.opacity = active ? 0.9 : 0.07;
            route.glowMaterial.opacity = active ? 0.22 : 0.015;
            route.glowMaterial.color.copy(route.lineMaterial.color);
            route.particles.visible = active;
            route.trail.visible = active;
            route.arrow.visible = active;
            route.particles.material.size = active ? 0.32 : 0.2;
            updateRouteParticles(
                this.world,
                id,
                (time * 0.18 + index * 0.071) % 1,
            );
        }
        this.scene.updateMatrixWorld();
        this.camera.updateMatrixWorld();
        const projection: SceneProjection = {
            nodes: {} as SceneProjection["nodes"],
            routes: {},
        };
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        const project = (point: Vector3) => {
            const projected = point.clone().project(this.camera);
            return {
                x: (projected.x * 0.5 + 0.5) * width,
                y: (-projected.y * 0.5 + 0.5) * height,
                visible: projected.z > -1 && projected.z < 1,
            };
        };
        for (const id of FUSION_NODE_IDS) {
            const point = this.world.nodes[id].group.position.clone();
            point.y += 1.55;
            const projected = project(point);
            if (id === "request") {
                const unclampedX = projected.x + 15;
                projected.x = Math.max(340, unclampedX);
                projected.y += 12;
                if (unclampedX < 340) projected.y = Math.max(projected.y, 260);
            }
            if (id === "orchestrator") projected.y -= 58;
            projection.nodes[id] = projected;
        }
        const labelRoutes =
            this.stage === "smart_model"
                ? []
                : visual.activeRoutes.filter(
                      (id) => id !== "smart_recovery_loop",
                  );
        for (const id of labelRoutes) {
            const point = this.world.routes[id].curve.getPointAt(0.57);
            point.y += 0.45;
            projection.routes[id] = project(point);
        }
        this.onProject(projection);
        this.composer.render();
    }

    dispose(): void {
        disposeObjectResources(this.scene);
        this.composer.dispose();
        this.renderer.dispose();
        this.renderer.domElement.remove();
    }
}
