import {
    Color,
    DirectionalLight,
    HemisphereLight,
    OrthographicCamera,
    PCFSoftShadowMap,
    Raycaster,
    Scene,
    SRGBColorSpace,
    Vector2,
    Vector3,
    WebGLRenderer,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import type {
    FusionNode,
    FusionSceneAdapter,
    PlaybackSpeed,
    SceneLabelPositions,
    ScenePacketPositions,
    StageId,
} from "../types";
import {
    createFusionWorld,
    disposeObjectResources,
    FUSION_NODE_IDS,
    FUSION_ROUTE_IDS,
    getCappedPixelRatio,
    getNextFlowTime,
    getStageVisualState,
    PALETTE,
    updateRouteParticles,
    type FusionRouteId,
    type FusionWorld,
} from "./geometry";
import {
    getCameraPreset,
    getStageCameraPreset,
    isSceneRenderable,
} from "./state";

const FRUSTUM_HEIGHT = 15.5;
const NODE_ENERGY = { idle: 0.5, inactive: 0.18, active: 1 } as const;

type CameraView = "isometric" | "top";

interface SceneOptions {
    reducedMotion?: boolean;
    onNodeSelect?: (node: FusionNode) => void;
    onContextLost?: () => void;
    onLabelsProject?: (positions: SceneLabelPositions) => void;
    onPacketsProject?: (positions: ScenePacketPositions) => void;
}

class FusionScene implements FusionSceneAdapter {
    private readonly scene = new Scene();
    private readonly camera = new OrthographicCamera(-10, 10, 8, -8, 0.1, 180);
    private readonly world: FusionWorld;
    private readonly controls: OrbitControls;
    private readonly raycaster = new Raycaster();
    private readonly pointer = new Vector2();
    private readonly resizeObserver: ResizeObserver | null;
    private readonly intersectionObserver: IntersectionObserver | null;
    private readonly onNodeSelect: ((node: FusionNode) => void) | undefined;
    private readonly onContextLost: (() => void) | undefined;
    private readonly onLabelsProject:
        ((positions: SceneLabelPositions) => void) | undefined;
    private readonly onPacketsProject:
        ((positions: ScenePacketPositions) => void) | undefined;
    private readonly reducedMotion: boolean;
    private readonly cameraGoal = new Vector3();
    private readonly targetGoal = new Vector3();
    private readonly nodeEnergy = Object.fromEntries(
        FUSION_NODE_IDS.map((id) => [id, NODE_ENERGY.idle]),
    ) as Record<FusionNode, number>;
    private readonly routeEnergy = Object.fromEntries(
        FUSION_ROUTE_IDS.map((id) => [id, NODE_ENERGY.idle]),
    ) as Record<FusionRouteId, number>;

    private stage: StageId = "input";
    private playing = false;
    private speed: PlaybackSpeed = 1;
    private flowTime = 0;
    private frameId: number | null = null;
    private lastFrameTime: number | null = null;
    private cameraAnimating = false;
    private cameraFocus: FusionNode | null = null;
    private cameraUserControlled = false;
    private cameraView: CameraView = "isometric";
    private followStage = true;
    private cameraZoomGoal = 1;
    private visualAnimating = false;
    private viewportAspect = 1;
    private containerVisible = true;
    private pointerDown: { x: number; y: number } | null = null;
    private contextLost = false;
    private disposed = false;

    constructor(
        private readonly container: HTMLElement,
        private readonly renderer: WebGLRenderer,
        options: SceneOptions,
    ) {
        this.reducedMotion = options.reducedMotion ?? false;
        this.onNodeSelect = options.onNodeSelect;
        this.onContextLost = options.onContextLost;
        this.onLabelsProject = options.onLabelsProject;
        this.onPacketsProject = options.onPacketsProject;
        const canvas = renderer.domElement;
        canvas.style.display = "block";
        canvas.style.width = "100%";
        canvas.style.height = "100%";
        canvas.style.cursor = "grab";
        canvas.setAttribute("role", "img");
        canvas.setAttribute(
            "aria-label",
            "Orthographic BreakFuser process model. Adjacent module buttons provide keyboard-accessible payload inspection.",
        );
        renderer.setClearColor(PALETTE.background, 1);
        renderer.outputColorSpace = SRGBColorSpace;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = PCFSoftShadowMap;
        this.scene.background = new Color(PALETTE.background);
        this.world = createFusionWorld(this.container.clientWidth);
        this.scene.add(this.world.root);
        const ambient = new HemisphereLight(0xffffff, 0xd8d2c5, 1.85);
        const key = new DirectionalLight(0xffffff, 2.4);
        key.position.set(-8, 18, 12);
        key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        key.shadow.camera.left = -18;
        key.shadow.camera.right = 18;
        key.shadow.camera.top = 14;
        key.shadow.camera.bottom = -14;
        key.shadow.bias = -0.0004;
        const fill = new DirectionalLight(0xe7eef2, 0.7);
        fill.position.set(8, 8, -10);
        this.scene.add(ambient, key, fill);

        this.controls = new OrbitControls(this.camera, canvas);
        this.controls.enableDamping = !this.reducedMotion;
        this.controls.dampingFactor = 0.08;
        this.controls.enablePan = true;
        this.controls.rotateSpeed = 0.5;
        this.controls.zoomSpeed = 0.7;
        this.controls.minZoom = 0.45;
        this.controls.maxZoom = 3;
        this.controls.minPolarAngle = 0.05;
        this.controls.maxPolarAngle = Math.PI * 0.48;
        this.container.append(canvas);
        this.intersectionObserver =
            typeof IntersectionObserver === "undefined"
                ? null
                : new IntersectionObserver(this.handleIntersection, {
                      threshold: 0,
                  });
        this.intersectionObserver?.observe(this.container);
        this.resize();
        this.resetCamera(false);
        this.updateVisuals(1, true);
        canvas.addEventListener("pointerdown", this.handlePointerDown);
        canvas.addEventListener("pointerup", this.handlePointerUp);
        canvas.addEventListener("pointermove", this.handlePointerMove);
        canvas.addEventListener("pointercancel", this.handlePointerCancel);
        canvas.addEventListener("pointerleave", this.handlePointerLeave);
        canvas.addEventListener("webglcontextlost", this.handleContextLost);
        this.controls.addEventListener("start", this.handleControlsStart);
        this.controls.addEventListener("change", this.handleControlsChange);
        document.addEventListener("visibilitychange", this.handleVisibility);
        window.addEventListener("resize", this.handleResize, { passive: true });
        this.resizeObserver =
            typeof ResizeObserver === "undefined"
                ? null
                : new ResizeObserver(this.handleResize);
        this.resizeObserver?.observe(this.container);
        this.requestRender();
    }

    setStage(stage: StageId): void {
        if (this.disposed) return;
        this.stage = stage;
        if (stage === "input") this.flowTime = 0;
        if (this.reducedMotion) this.updateVisuals(1, true);
        else this.visualAnimating = true;
        if (this.followStage) this.moveToStage(stage);
        this.requestRender();
    }

    setPlaying(playing: boolean): void {
        if (this.disposed) return;
        this.playing = playing;
        this.lastFrameTime = null;
        this.requestRender();
    }

    setSpeed(speed: PlaybackSpeed): void {
        if (!this.disposed) this.speed = speed;
    }

    focusNode(node: FusionNode): void {
        if (this.disposed) return;
        this.cameraFocus = node;
        this.cameraUserControlled = false;
        const target = this.world.nodes[node].group.getWorldPosition(
            new Vector3(),
        );
        this.targetGoal.copy(target);
        this.cameraGoal.copy(target).add(new Vector3(0, 15, 19));
        this.cameraZoomGoal = 1.65;
        this.cameraAnimating = !this.reducedMotion;
        if (this.reducedMotion) this.applyCameraGoal();
        this.requestRender();
    }

    setView(view: CameraView): void {
        if (this.disposed) return;
        this.cameraView = view;
        this.resetCamera(true);
    }

    setFollowStage(follow: boolean): void {
        if (this.disposed) return;
        this.followStage = follow;
        if (follow) this.moveToStage(this.stage);
    }

    private moveToStage(stage: StageId): void {
        this.cameraFocus = null;
        this.cameraUserControlled = false;
        const preset = getStageCameraPreset(stage, this.viewportAspect);
        this.cameraGoal.copy(preset.position);
        this.targetGoal.copy(preset.target);
        this.cameraZoomGoal = preset.zoom;
        if (this.cameraView === "top") {
            this.cameraGoal.copy(this.targetGoal).add(new Vector3(0, 42, 0));
        }
        this.cameraAnimating = !this.reducedMotion;
        if (this.reducedMotion) this.applyCameraGoal();
    }

    resetView(): void {
        this.resetCamera(true);
    }

    private resetCamera(render: boolean): void {
        if (this.disposed) return;
        this.cameraFocus = null;
        this.cameraUserControlled = false;
        const preset = getCameraPreset(this.cameraView, this.viewportAspect);
        this.cameraGoal.copy(preset.position);
        this.targetGoal.copy(preset.target);
        this.cameraZoomGoal = preset.zoom;
        this.cameraAnimating = !this.reducedMotion;
        if (this.reducedMotion) this.applyCameraGoal();
        if (render) this.requestRender();
    }

    private applyCameraGoal(): void {
        this.camera.position.copy(this.cameraGoal);
        this.camera.up.set(
            0,
            this.cameraView === "top" && this.cameraFocus === null ? 0 : 1,
            this.cameraView === "top" && this.cameraFocus === null ? -1 : 0,
        );
        this.camera.zoom = this.cameraZoomGoal;
        this.camera.updateProjectionMatrix();
        this.controls.target.copy(this.targetGoal);
        this.controls.update();
        this.cameraAnimating = false;
    }

    resize(): void {
        if (this.disposed) return;
        const bounds = this.container.getBoundingClientRect();
        const width = Math.max(
            1,
            Math.round(this.container.clientWidth || bounds.width || 1),
        );
        const height = Math.max(
            1,
            Math.round(this.container.clientHeight || bounds.height || 1),
        );
        this.viewportAspect = width / height;
        this.camera.left = (-FRUSTUM_HEIGHT * this.viewportAspect) / 2;
        this.camera.right = (FRUSTUM_HEIGHT * this.viewportAspect) / 2;
        this.camera.top = FRUSTUM_HEIGHT / 2;
        this.camera.bottom = -FRUSTUM_HEIGHT / 2;
        this.camera.updateProjectionMatrix();
        this.renderer.setPixelRatio(
            getCappedPixelRatio(window.devicePixelRatio, width),
        );
        this.renderer.setSize(width, height, false);
        if (!this.cameraUserControlled) {
            const preset = getCameraPreset(
                this.cameraView,
                this.viewportAspect,
            );
            this.cameraGoal.copy(preset.position);
            this.targetGoal.copy(preset.target);
            this.cameraZoomGoal =
                this.cameraFocus === null ? preset.zoom : 1.65;
            if (!this.cameraAnimating) this.applyCameraGoal();
        }
        this.projectLabels();
        this.requestRender();
    }

    dispose(): void {
        if (this.disposed) return;
        this.disposed = true;
        if (this.frameId !== null) cancelAnimationFrame(this.frameId);
        this.frameId = null;
        this.resizeObserver?.disconnect();
        this.intersectionObserver?.disconnect();
        window.removeEventListener("resize", this.handleResize);
        document.removeEventListener("visibilitychange", this.handleVisibility);
        this.controls.removeEventListener("start", this.handleControlsStart);
        this.controls.removeEventListener("change", this.handleControlsChange);
        this.controls.dispose();
        const canvas = this.renderer.domElement;
        canvas.removeEventListener("pointerdown", this.handlePointerDown);
        canvas.removeEventListener("pointerup", this.handlePointerUp);
        canvas.removeEventListener("pointermove", this.handlePointerMove);
        canvas.removeEventListener("pointercancel", this.handlePointerCancel);
        canvas.removeEventListener("pointerleave", this.handlePointerLeave);
        canvas.removeEventListener("webglcontextlost", this.handleContextLost);
        disposeObjectResources(this.scene);
        this.renderer.renderLists.dispose();
        this.renderer.dispose();
        if (!this.contextLost) this.renderer.forceContextLoss();
        this.scene.clear();
        canvas.remove();
    }

    private updateVisuals(delta: number, immediate = false): void {
        const stage = getStageVisualState(this.stage);
        const blend =
            immediate || this.reducedMotion ? 1 : 1 - Math.exp(-delta * 7);
        let transitioning = false;
        for (const id of FUSION_NODE_IDS) {
            const target = stage.activeNodes.includes(id)
                ? NODE_ENERGY.active
                : this.stage === "input"
                  ? NODE_ENERGY.idle
                  : NODE_ENERGY.inactive;
            transitioning ||= Math.abs(target - this.nodeEnergy[id]) > 0.001;
            const energy = immediate
                ? target
                : this.nodeEnergy[id] + (target - this.nodeEnergy[id]) * blend;
            this.nodeEnergy[id] = energy;
            const node = this.world.nodes[id];
            node.group.scale.setScalar(0.99 + energy * 0.025);
            for (const material of node.accentMaterials)
                material.opacity = 0.6 + energy * 0.4;
        }
        for (const id of FUSION_ROUTE_IDS) {
            const currentEnergy = this.routeEnergy[id] ?? NODE_ENERGY.idle;
            const target = stage.activeRoutes.includes(id)
                ? NODE_ENERGY.active
                : this.stage === "input"
                  ? 0.35
                  : 0.12;
            transitioning ||= Math.abs(target - currentEnergy) > 0.001;
            const energy = immediate
                ? target
                : currentEnergy + (target - currentEnergy) * blend;
            this.routeEnergy[id] = energy;
            const route = this.world.routes[id];
            route.lineMaterial.opacity = 0.28 + energy * 0.6;
            route.glowMaterial.opacity = 0.45 + energy * 0.35;
            route.particles.material.opacity = stage.activeRoutes.includes(id)
                ? 0.95
                : 0.08;
            route.trail.material.opacity = stage.activeRoutes.includes(id)
                ? 0.32
                : 0.015;
            updateRouteParticles(this.world, id, this.flowTime);
        }
        this.visualAnimating =
            !immediate && !this.reducedMotion && transitioning;
    }

    private projectLabels(): void {
        if (this.onLabelsProject !== undefined) {
            const positions = {} as SceneLabelPositions;
            for (const id of FUSION_NODE_IDS) {
                const point = this.world.nodes[id].group
                    .getWorldPosition(new Vector3())
                    .add(new Vector3(0, 2.5, 0));
                const projected = this.projectPoint(point);
                if (id === "request") projected.x -= 20;
                if (id === "output") projected.x += 10;
                positions[id] = projected;
            }
            this.onLabelsProject(positions);
        }
        if (this.onPacketsProject !== undefined) {
            const positions: ScenePacketPositions = {};
            const activeRoutes = getStageVisualState(this.stage).activeRoutes;
            for (const id of FUSION_ROUTE_IDS) {
                const progress =
                    this.playing && activeRoutes.includes(id)
                        ? (this.flowTime + 0.15) % 1
                        : 0.52;
                const point = this.world.routes[id].curve.getPointAt(progress);
                point.y += 0.55;
                this.world.root.localToWorld(point);
                positions[id] = this.projectPoint(point);
            }
            this.onPacketsProject(positions);
        }
    }

    private projectPoint(point: Vector3): {
        x: number;
        y: number;
        visible: boolean;
    } {
        const projected = point.project(this.camera);
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        return {
            x: (projected.x * 0.5 + 0.5) * width,
            y: (-projected.y * 0.5 + 0.5) * height,
            visible:
                projected.z > -1 &&
                projected.z < 1 &&
                projected.x > -0.94 &&
                projected.x < 0.94 &&
                projected.y > -0.9 &&
                projected.y < 0.9,
        };
    }

    private canRender(): boolean {
        return (
            !this.contextLost &&
            isSceneRenderable(document.hidden, this.containerVisible)
        );
    }

    private render(): void {
        if (!this.disposed && this.canRender()) {
            this.renderer.render(this.scene, this.camera);
            this.projectLabels();
        }
    }

    private requestRender(): void {
        if (this.disposed || !this.canRender()) return;
        if (this.reducedMotion) {
            this.render();
            return;
        }
        if (this.frameId === null)
            this.frameId = requestAnimationFrame(this.tick);
    }

    private readonly tick = (time: number): void => {
        this.frameId = null;
        if (this.disposed || !this.canRender()) return;
        const delta =
            this.lastFrameTime === null
                ? 0
                : Math.min((time - this.lastFrameTime) / 1000, 0.05);
        this.lastFrameTime = time;
        this.flowTime = getNextFlowTime(
            this.flowTime,
            delta,
            this.speed,
            this.playing,
            this.reducedMotion,
        );
        this.updateVisuals(delta);
        if (this.cameraAnimating) {
            const blend = 1 - Math.exp(-delta * 5);
            this.camera.position.lerp(this.cameraGoal, blend);
            this.controls.target.lerp(this.targetGoal, blend);
            this.camera.zoom +=
                (this.cameraZoomGoal - this.camera.zoom) * blend;
            this.camera.up.set(
                0,
                this.cameraView === "top" && this.cameraFocus === null ? 0 : 1,
                this.cameraView === "top" && this.cameraFocus === null ? -1 : 0,
            );
            this.camera.updateProjectionMatrix();
            if (
                this.camera.position.distanceToSquared(this.cameraGoal) <
                    0.0001 &&
                Math.abs(this.camera.zoom - this.cameraZoomGoal) < 0.0001
            )
                this.applyCameraGoal();
        }
        this.controls.update();
        this.render();
        if (this.playing || this.cameraAnimating || this.visualAnimating)
            this.requestRender();
    };

    private pickNode(event: PointerEvent): FusionNode | null {
        const bounds = this.renderer.domElement.getBoundingClientRect();
        if (bounds.width === 0 || bounds.height === 0) return null;
        this.pointer.set(
            ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
            -((event.clientY - bounds.top) / bounds.height) * 2 + 1,
        );
        this.raycaster.setFromCamera(this.pointer, this.camera);
        const intersections = this.raycaster.intersectObjects(
            FUSION_NODE_IDS.map((id) => this.world.nodes[id].group),
            true,
        );
        for (const intersection of intersections) {
            let object = intersection.object;
            while (object.parent !== null) {
                const node = object.userData.fusionNode as
                    FusionNode | undefined;
                if (node !== undefined && FUSION_NODE_IDS.includes(node))
                    return node;
                object = object.parent;
            }
        }
        return null;
    }

    private readonly handleContextLost = (event: Event): void => {
        event.preventDefault();
        if (this.disposed || this.contextLost) return;
        this.contextLost = true;
        if (this.frameId !== null) cancelAnimationFrame(this.frameId);
        this.frameId = null;
        this.onContextLost?.();
    };

    private readonly handlePointerDown = (event: PointerEvent): void => {
        this.pointerDown = { x: event.clientX, y: event.clientY };
        this.renderer.domElement.style.cursor = "grabbing";
    };

    private readonly handlePointerUp = (event: PointerEvent): void => {
        const start = this.pointerDown;
        this.pointerDown = null;
        this.renderer.domElement.style.cursor = "grab";
        if (
            event.button !== 0 ||
            start === null ||
            Math.hypot(event.clientX - start.x, event.clientY - start.y) > 6
        )
            return;
        const node = this.pickNode(event);
        if (node !== null) this.onNodeSelect?.(node);
    };

    private readonly handlePointerMove = (event: PointerEvent): void => {
        if (event.buttons !== 0) return;
        this.renderer.domElement.style.cursor =
            this.pickNode(event) === null ? "grab" : "pointer";
    };

    private readonly handlePointerCancel = (): void => {
        this.pointerDown = null;
        this.renderer.domElement.style.cursor = "grab";
    };

    private readonly handlePointerLeave = (): void => {
        this.pointerDown = null;
    };

    private readonly handleControlsStart = (): void => {
        this.cameraAnimating = false;
        this.cameraUserControlled = true;
    };

    private readonly handleControlsChange = (): void => {
        this.requestRender();
    };

    private readonly handleResize = (): void => {
        this.resize();
    };

    private readonly handleVisibility = (): void => {
        this.syncFrameState();
    };

    private readonly handleIntersection = (
        entries: IntersectionObserverEntry[],
    ): void => {
        const entry = entries[entries.length - 1];
        if (entry === undefined) return;
        const visible = entry.isIntersecting && entry.intersectionRatio > 0;
        if (visible !== this.containerVisible) {
            this.containerVisible = visible;
            this.syncFrameState();
        }
    };

    private syncFrameState(): void {
        this.lastFrameTime = null;
        if (!this.canRender() && this.frameId !== null) {
            cancelAnimationFrame(this.frameId);
            this.frameId = null;
        } else if (this.canRender()) this.requestRender();
    }
}

export function createFusionScene(
    container: HTMLElement,
    options: SceneOptions = {},
): FusionSceneAdapter | null {
    let renderer: WebGLRenderer | null = null;
    try {
        renderer = new WebGLRenderer({
            antialias: true,
            alpha: false,
            depth: true,
            stencil: false,
            powerPreference: "high-performance",
        });
        return new FusionScene(container, renderer, options);
    } catch {
        if (renderer !== null) {
            renderer.dispose();
            renderer.forceContextLoss();
            renderer.domElement.remove();
        }
        return null;
    }
}
