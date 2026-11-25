import {
    Color,
    CubicBezierCurve3,
    CylinderGeometry,
    DirectionalLight,
    FogExp2,
    GridHelper,
    Group,
    HemisphereLight,
    Mesh,
    MeshBasicMaterial,
    MeshStandardMaterial,
    PerspectiveCamera,
    Points,
    PointsMaterial,
    BufferGeometry,
    Float32BufferAttribute,
    Scene,
    SphereGeometry,
    SRGBColorSpace,
    TorusGeometry,
    TubeGeometry,
    Vector2,
    Vector3,
    WebGLRenderer,
} from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

import { disposeObjectResources } from "../scene/geometry";
import type { RecordingModel } from "./state";
import {
    buildSpecializedScene,
    type SceneLinkSpec,
    type SceneNodeSpec,
    type SceneTone,
} from "./scene-kinds";

export interface UniqueLabelProjection {
    id: string;
    title: string;
    detail: string;
    tone: SceneTone;
    active: boolean;
    x: number;
    y: number;
    visible: boolean;
}

const COLORS: Record<SceneTone, number> = {
    cyan: 0x7dd3fc,
    green: 0x86efac,
    violet: 0xc4b5fd,
    amber: 0xfdba74,
    muted: 0x385064,
    blue: 0x60a5fa,
};

interface BuiltNode {
    spec: SceneNodeSpec;
    group: Group;
    materials: MeshStandardMaterial[];
}

interface BuiltLink {
    spec: SceneLinkSpec;
    curve: CubicBezierCurve3;
    material: MeshBasicMaterial;
    point: Points;
}

export class UniqueGifScene {
    private readonly scene = new Scene();
    private readonly camera = new PerspectiveCamera(36, 1.6, 0.1, 180);
    private readonly renderer: WebGLRenderer;
    private readonly composer: EffectComposer;
    private readonly content = new Group();
    private nodes: BuiltNode[] = [];
    private links: BuiltLink[] = [];
    private key = "";
    private visible = false;

    constructor(
        private readonly container: HTMLElement,
        private readonly onProject: (labels: UniqueLabelProjection[]) => void,
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
        this.scene.add(this.content);
        const grid = new GridHelper(90, 90, 0x173f52, 0x122e40);
        grid.position.y = -0.5;
        const gridMaterials = Array.isArray(grid.material)
            ? grid.material
            : [grid.material];
        for (const material of gridMaterials) {
            material.transparent = true;
            material.opacity = 0.36;
            material.depthWrite = false;
        }
        this.scene.add(grid);
        const ambient = new HemisphereLight(0xbfeaff, 0x07111b, 1.35);
        const key = new DirectionalLight(0xe5f6ff, 2.2);
        key.position.set(-8, 18, 12);
        key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        key.shadow.camera.left = -22;
        key.shadow.camera.right = 22;
        key.shadow.camera.top = 18;
        key.shadow.camera.bottom = -18;
        const rim = new DirectionalLight(0x86efac, 0.65);
        rim.position.set(8, 8, -12);
        this.scene.add(ambient, key, rim);
        this.composer = new EffectComposer(this.renderer);
        this.composer.addPass(new RenderPass(this.scene, this.camera));
        this.composer.addPass(
            new UnrealBloomPass(new Vector2(1200, 750), 0.58, 0.55, 0.74),
        );
        this.composer.addPass(new OutputPass());
        container.append(this.renderer.domElement);
        this.setVisible(false);
        this.resize();
    }

    setVisible(visible: boolean): void {
        this.visible = visible;
        this.renderer.domElement.style.display = visible ? "block" : "none";
    }

    setModel(model: RecordingModel): void {
        const key = `${model.recording.id}:${model.step}`;
        if (key === this.key) return;
        this.key = key;
        const definition = buildSpecializedScene(
            model.sceneKind,
            model.step,
            model.scenario,
        );
        disposeObjectResources(this.content);
        this.content.clear();
        this.nodes = [];
        this.links = [];
        for (const spec of definition.nodes) this.addNode(spec);
        for (const spec of definition.links) this.addLink(spec);
        this.camera.position.set(...definition.camera);
        this.camera.lookAt(...definition.target);
    }

    private material(spec: SceneNodeSpec): MeshStandardMaterial {
        const color = COLORS[spec.tone];
        return new MeshStandardMaterial({
            color: spec.tone === "muted" ? 0x162a38 : color,
            emissive: color,
            emissiveIntensity: spec.active ? 0.42 : 0.025,
            roughness: 0.48,
            metalness: 0.16,
            transparent:
                spec.opacity !== undefined ||
                spec.kind === "wall" ||
                spec.kind === "panel",
            opacity:
                spec.opacity ??
                (spec.kind === "wall"
                    ? 0.35
                    : spec.kind === "panel"
                      ? 0.78
                      : 1),
        });
    }

    private addNode(spec: SceneNodeSpec): void {
        const group = new Group();
        group.position.set(...spec.position);
        const materials: MeshStandardMaterial[] = [];
        const addMesh = (
            geometry: RoundedBoxGeometry | CylinderGeometry | SphereGeometry,
            position?: Vector3,
        ) => {
            const material = this.material(spec);
            materials.push(material);
            const mesh = new Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            if (position) mesh.position.copy(position);
            group.add(mesh);
        };
        if (spec.kind === "cylinder") {
            addMesh(
                new CylinderGeometry(
                    spec.size[0] / 2,
                    spec.size[0] / 2,
                    spec.size[1],
                    32,
                ),
            );
        } else if (spec.kind === "orb") {
            addMesh(new SphereGeometry(spec.size[0] / 2, 28, 20));
        } else if (spec.kind === "ring") {
            const material = new MeshBasicMaterial({
                color: COLORS[spec.tone],
                transparent: true,
                opacity: spec.active ? 0.72 : 0.1,
            });
            const ring = new Mesh(
                new TorusGeometry(spec.size[0] / 2, 0.075, 8, 80),
                material,
            );
            ring.rotation.x = Math.PI / 2;
            group.add(ring);
        } else if (spec.kind === "arch") {
            const width = spec.size[0];
            const height = spec.size[1];
            const depth = spec.size[2];
            addMesh(
                new RoundedBoxGeometry(0.28, height, depth, 2, 0.05),
                new Vector3(-width / 2, height / 2, 0),
            );
            addMesh(
                new RoundedBoxGeometry(0.28, height, depth, 2, 0.05),
                new Vector3(width / 2, height / 2, 0),
            );
            addMesh(
                new RoundedBoxGeometry(width + 0.28, 0.3, depth, 2, 0.05),
                new Vector3(0, height, 0),
            );
        } else {
            addMesh(
                new RoundedBoxGeometry(
                    spec.size[0],
                    spec.size[1],
                    spec.size[2],
                    3,
                    Math.min(0.12, spec.size[1] / 5),
                ),
            );
        }
        this.content.add(group);
        this.nodes.push({ spec, group, materials });
    }

    private addLink(spec: SceneLinkSpec): void {
        const start = new Vector3(...spec.from);
        const end = new Vector3(...spec.to);
        const first = start.clone().lerp(end, 0.33);
        const second = start.clone().lerp(end, 0.66);
        first.y += spec.arc ?? 0.6;
        second.y += spec.arc ?? 0.6;
        const curve = new CubicBezierCurve3(start, first, second, end);
        const material = new MeshBasicMaterial({
            color: COLORS[spec.tone],
            transparent: true,
            opacity: spec.active ? 0.85 : 0.06,
            depthWrite: false,
        });
        const tube = new Mesh(
            new TubeGeometry(curve, 40, spec.active ? 0.035 : 0.018, 5, false),
            material,
        );
        const geometry = new BufferGeometry();
        geometry.setAttribute(
            "position",
            new Float32BufferAttribute(new Float32Array(3), 3),
        );
        const point = new Points(
            geometry,
            new PointsMaterial({
                color: COLORS[spec.tone],
                size: 0.34,
                transparent: true,
                opacity: spec.active ? 1 : 0,
                depthWrite: false,
            }),
        );
        point.frustumCulled = false;
        this.content.add(tube, point);
        this.links.push({ spec, curve, material, point });
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
        if (!this.visible) return;
        this.content.updateMatrixWorld(true);
        this.camera.updateMatrixWorld();
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        const labels: UniqueLabelProjection[] = [];
        for (const [index, built] of this.nodes.entries()) {
            const { spec, group, materials } = built;
            if (spec.active)
                group.scale.setScalar(1 + Math.sin(time * 2.8 + index) * 0.025);
            else group.scale.setScalar(1);
            for (const material of materials)
                material.emissiveIntensity = spec.active
                    ? 0.42 + Math.sin(time * 3 + index) * 0.08
                    : 0.025;
            if (spec.label !== undefined && spec.active) {
                const point = group.position.clone();
                point.y += Math.max(0.8, spec.size[1] / 2 + 0.65);
                const projected = point.project(this.camera);
                labels.push({
                    id: spec.id,
                    title: spec.label,
                    detail: spec.detail ?? "",
                    tone: spec.tone,
                    active: spec.active ?? false,
                    x: (projected.x * 0.5 + 0.5) * width,
                    y: (-projected.y * 0.5 + 0.5) * height,
                    visible: projected.z > -1 && projected.z < 1,
                });
            }
        }
        for (const [index, built] of this.links.entries()) {
            const position = built.curve.getPointAt(
                (time * 0.22 + index * 0.13) % 1,
            );
            const attribute = built.point.geometry.getAttribute("position");
            attribute.setXYZ(0, position.x, position.y + 0.12, position.z);
            attribute.needsUpdate = true;
            built.material.opacity = built.spec.active
                ? 0.72 + Math.sin(time * 2.5 + index) * 0.15
                : 0.05;
        }
        this.onProject(labels);
        this.composer.render();
    }

    dispose(): void {
        disposeObjectResources(this.scene);
        this.composer.dispose();
        this.renderer.dispose();
        this.renderer.domElement.remove();
    }
}
