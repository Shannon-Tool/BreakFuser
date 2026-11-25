import { Vector3 } from "three";
import type { StageId } from "../types";

export function isSceneRenderable(
    documentHidden: boolean,
    containerVisible: boolean,
): boolean {
    return !documentHidden && containerVisible;
}

export function getViewportFit(aspect: number): number {
    if (!Number.isFinite(aspect) || aspect <= 0) {
        return 1;
    }
    return aspect >= 16 / 9 ? 1 : Math.max(1, 1.9 / aspect);
}

export function getCameraPreset(
    view: "isometric" | "top",
    aspect: number,
): { position: Vector3; target: Vector3; zoom: number } {
    const fit = getViewportFit(aspect);
    if (view === "top") {
        return {
            position: new Vector3(0, 42, 0),
            target: new Vector3(0, 0, 0),
            zoom: 1 / fit,
        };
    }
    return {
        position: new Vector3(0, 26, 34),
        target: new Vector3(0, 0, 0),
        zoom: 1 / fit,
    };
}

export function getStageCameraPreset(
    stage: StageId,
    aspect: number,
): { position: Vector3; target: Vector3; zoom: number } {
    if (stage === "input") return getCameraPreset("isometric", aspect);
    const settings = {
        smart_model: { x: -4.6, zoom: 1.04 },
        recovery: { x: -5.3, zoom: 1.32 },
        fusion: { x: 1.2, zoom: 1.12 },
        verified: { x: 7.7, zoom: 1.2 },
    } as const;
    const setting = settings[stage];
    const target = new Vector3(setting.x, 0, 0);
    return {
        position: target.clone().add(new Vector3(0, 26, 34)),
        target,
        zoom: setting.zoom / getViewportFit(aspect),
    };
}

export function refitOrbitPosition(
    position: Vector3,
    target: Vector3,
    previousAspect: number,
    nextAspect: number,
): Vector3 {
    const scale = getViewportFit(nextAspect) / getViewportFit(previousAspect);
    return position.clone().sub(target).multiplyScalar(scale).add(target);
}
