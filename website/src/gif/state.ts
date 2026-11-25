import type { Scenario, StageId } from "../types";
import {
    RECORDINGS,
    recordingById,
    scenarioById,
    type RecordingCard,
    type RecordingDefinition,
    type RecordingStep,
    type RecordingView,
} from "./recordings";
import { sceneKindFor, type SceneKind } from "./scene-kinds";

const DEFAULT_RECORDING: RecordingDefinition = RECORDINGS[0]!;
if (DEFAULT_RECORDING === undefined)
    throw new Error("A recording registry is required");

export const STEP_DURATIONS = DEFAULT_RECORDING.durations;
export const TOTAL_DURATION = recordingDuration(DEFAULT_RECORDING);

export type StepCard = RecordingCard;

export interface RecordingModel extends RecordingStep {
    scenario: Scenario;
    recording: RecordingDefinition;
    step: number;
    stage: StageId;
    view: RecordingView;
    sceneKind: SceneKind;
}

export function getPentestScenario(): Scenario {
    return scenarioById("authorized-pentesting");
}

export function createRecordingModel(
    step: number,
    recording: RecordingDefinition = DEFAULT_RECORDING,
): RecordingModel {
    const normalized = Math.max(
        0,
        Math.min(recording.steps.length - 1, Math.trunc(step)),
    );
    const content = recording.steps[normalized] ?? recording.steps[0];
    if (content === undefined)
        throw new Error(`Recording ${recording.id} has no steps`);
    return {
        ...content,
        scenario: scenarioById(recording.scenarioId),
        recording,
        step: normalized,
        stage: content.stage,
        view: recording.view,
        sceneKind: sceneKindFor(recording.id),
    };
}

export function recordingDuration(recording: RecordingDefinition): number {
    return recording.durations.reduce((total, duration) => total + duration, 0);
}

export function recordingStepStart(
    recording: RecordingDefinition,
    step: number,
): number {
    let start = 0;
    for (let index = 0; index < step; index += 1)
        start += recording.durations[index] ?? 0;
    return start;
}

export function timelineAt(
    seconds: number,
    durations: readonly number[] = STEP_DURATIONS,
): { step: number; localTime: number } {
    const total = durations.reduce((sum, duration) => sum + duration, 0);
    if (total <= 0) throw new Error("A recording needs a positive duration");
    const wrapped = ((seconds % total) + total) % total;
    let start = 0;
    for (let index = 0; index < durations.length; index += 1) {
        const duration = durations[index] ?? 0;
        if (wrapped < start + duration - 1e-9) {
            const localTime = wrapped - start;
            return {
                step: index,
                localTime: Math.abs(localTime) < 1e-9 ? 0 : localTime,
            };
        }
        start += duration;
    }
    return { step: durations.length - 1, localTime: durations.at(-1) ?? 0 };
}

export { RECORDINGS, recordingById };
