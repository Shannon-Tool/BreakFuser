import "./styles.css";

import type { FusionNode, StageId } from "../types";
import {
    FUSION_NODE_IDS,
    FUSION_ROUTE_IDS,
    getStageVisualState,
    PACKET_LABELS,
    type FusionRouteId,
} from "../scene/geometry";
import { NODE_CONTENT } from "../scene/content";
import { FusionGifScene, type SceneProjection } from "./scene";
import { UniqueGifScene, type UniqueLabelProjection } from "./UniqueGifScene";
import {
    createRecordingModel,
    RECORDINGS,
    recordingById,
    recordingDuration,
    recordingStepStart,
    timelineAt,
    type RecordingModel,
} from "./state";
import type { RecordingDefinition } from "./recordings";

function node<K extends keyof HTMLElementTagNameMap>(
    tag: K,
    className?: string,
    text?: string,
): HTMLElementTagNameMap[K] {
    const element = document.createElement(tag);
    if (className !== undefined) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

const root = document.querySelector<HTMLElement>("#stage");
if (root === null) throw new Error("Recording stage is missing");
const stageRoot = root;

const sceneHost = node("div");
sceneHost.id = "scene";
const labelsHost = node("div");
labelsHost.id = "node-labels";
const packetsHost = node("div");
packetsHost.id = "packet-labels";
const uniqueLabelsHost = node("div");
uniqueLabelsHost.id = "unique-labels";
const specialOverlay = node("section", "special-overlay");
specialOverlay.hidden = true;
stageRoot.append(
    sceneHost,
    labelsHost,
    packetsHost,
    uniqueLabelsHost,
    specialOverlay,
);

const top = node("header", "stage-top");
const brand = node("div", "brand");
const brandDetail = node("span");
brand.append(
    node("span", "brand-mark", "BF"),
    node("strong", undefined, "BREAKFUSER"),
    brandDetail,
);
const phase = node("span", "phase-pill");
top.append(brand, phase);
stageRoot.append(top);
const processBadge = node("div", "process-badge");
stageRoot.append(processBadge);

const left = node("aside", "stage-side");
const inputPanel = node("section", "stage-panel input");
inputPanel.append(
    node("p", "stage-label", "INPUT · YOUR REQUEST"),
    node("p", "request-text"),
);
const contextPanel = node("section", "stage-panel context");
const contextTitle = node("p", "stage-label");
const contextValue = node("p", "context-value");
contextPanel.append(contextTitle, contextValue);
left.append(inputPanel, contextPanel);
stageRoot.append(left);

const right = node("aside", "stage-side right");
const outputPanel = node("section", "stage-panel output");
const outputTitle = node("p", "stage-label");
const outputText = node("p", "output-text");
const outputMeta = node("div", "output-meta");
outputPanel.append(outputTitle, outputText, outputMeta);
right.append(outputPanel);
stageRoot.append(right);

const nodeLabels = new Map<FusionNode, HTMLElement>();
for (const id of FUSION_NODE_IDS) {
    const content = NODE_CONTENT[id];
    const label = node("div", "node-label");
    label.dataset.node = id;
    label.append(
        node("strong", undefined, content.shortTitle),
        node("span", undefined, content.label),
    );
    labelsHost.append(label);
    nodeLabels.set(id, label);
}
const packetLabels = new Map<FusionRouteId, HTMLElement>();
for (const id of FUSION_ROUTE_IDS) {
    const label = node(
        "div",
        `packet-label${id === "smart_recovery_loop" ? " recovery" : ""}`,
        PACKET_LABELS[id],
    );
    label.hidden = true;
    packetsHost.append(label);
    packetLabels.set(id, label);
}

const bottom = node("section", "stage-bottom");
const track = node("div", "track");
let cardElements: { item: HTMLElement; values: HTMLElement }[] = [];
const caption = node("div", "stage-caption");
const captionNow = node("p", "caption-now");
const stepCount = node("strong");
const captionText = node("span");
captionNow.append(stepCount, captionText);
const captionWhy = node("p", "caption-why");
captionWhy.append(node("strong", undefined, "WHY IT MATTERS"), node("span"));
caption.append(
    captionNow,
    captionWhy,
    node(
        "p",
        "disclosure",
        "CURATED TRACE · NO PROVIDER CALL · TIMINGS ARE NOT MEASUREMENTS",
    ),
);
bottom.append(track, caption);
stageRoot.append(bottom);

function buildCards(model: RecordingModel): void {
    track.replaceChildren();
    cardElements = model.cards.map((card, index) => {
        const item = node("article", "track-card");
        item.dataset.card = card.id;
        const heading = node("div", "track-head");
        heading.append(
            node("span", "track-number", String(index + 1).padStart(2, "0")),
            node("span", undefined, card.title),
        );
        const values = node("div", "track-values");
        item.append(heading, values);
        track.append(item);
        return { item, values };
    });
}

function project(projection: SceneProjection): void {
    for (const [id, label] of nodeLabels) {
        const position = projection.nodes[id];
        label.style.left = `${position.x}px`;
        label.style.top = `${position.y}px`;
        label.hidden = !position.visible;
    }
    for (const [id, label] of packetLabels) {
        const position = projection.routes[id];
        label.hidden = position === undefined || !position.visible;
        if (position !== undefined) {
            label.style.left = `${position.x}px`;
            label.style.top = `${position.y}px`;
        }
    }
}

const pipelineScene = new FusionGifScene(sceneHost, project);
const uniqueLabelElements = new Map<string, HTMLElement>();
function projectUnique(labels: UniqueLabelProjection[]): void {
    const seen = new Set<string>();
    for (const label of labels) {
        if (
            stageRoot.dataset.sceneKind === "evidence_table" &&
            label.id.startsWith("row-")
        )
            continue;
        seen.add(label.id);
        let element = uniqueLabelElements.get(label.id);
        if (element === undefined) {
            element = node("div", "unique-node-label");
            element.append(node("strong"), node("span"));
            uniqueLabelsHost.append(element);
            uniqueLabelElements.set(label.id, element);
        }
        element.className = `unique-node-label tone-${label.tone}${label.active ? " active" : ""}`;
        element.querySelector("strong")!.textContent = label.title;
        element.querySelector("span")!.textContent = label.detail;
        element.style.left = `${label.x}px`;
        element.style.top = `${label.y}px`;
        element.hidden = !label.visible;
    }
    for (const [id, element] of uniqueLabelElements) {
        if (!seen.has(id)) {
            element.remove();
            uniqueLabelElements.delete(id);
        }
    }
}
const uniqueScene = new UniqueGifScene(sceneHost, projectUnique);
let activeStage: StageId = "input";

function updateSpecialOverlay(model: RecordingModel): void {
    specialOverlay.replaceChildren();
    specialOverlay.hidden = true;
    if (model.sceneKind === "continuation_editor") {
        specialOverlay.hidden = false;
        specialOverlay.className = "special-overlay editor-overlay";
        specialOverlay.append(
            node("header", undefined, `continuation.ts · ${model.phase}`),
        );
        const content =
            model.step === 0
                ? `${model.scenario.initialResponse}\n\n… truncated · continuation anchor required`
                : model.step === 1
                  ? model.scenario.recoveredFacts
                        .map((fact, index) => `// fact ${index + 1}\n${fact}`)
                        .join("\n\n")
                  : model.scenario.finalResponse;
        specialOverlay.append(node("pre", undefined, content));
    } else if (model.sceneKind === "evidence_table") {
        specialOverlay.hidden = false;
        specialOverlay.className = "special-overlay evidence-overlay";
        specialOverlay.append(
            node(
                "header",
                undefined,
                `EVIDENCE BLACKBOARD · ${model.scenario.evidence.length} ROWS`,
            ),
        );
        const table = node("div", "evidence-html-table");
        const header = node("div", "evidence-html-row heading");
        for (const label of [
            "evidence_id",
            "origin",
            "turn_id",
            "complete",
            "salvaged",
        ])
            header.append(node("span", undefined, label));
        table.append(header);
        if (model.step > 0) {
            for (const record of model.scenario.evidence) {
                const row = node(
                    "div",
                    `evidence-html-row origin-${record.origin}`,
                );
                for (const value of [
                    record.id,
                    record.origin,
                    record.turn_id ?? "null",
                    String(record.complete),
                    String(record.salvaged),
                ])
                    row.append(node("span", undefined, value));
                table.append(row);
            }
        }
        specialOverlay.append(table);
    }
}

function update(model: RecordingModel): void {
    stageRoot.dataset.step = String(model.step);
    stageRoot.dataset.stage = model.stage;
    stageRoot.dataset.recording = model.recording.id;
    brandDetail.textContent = model.recording.title.toUpperCase();
    processBadge.textContent = model.recording.processLabel;
    phase.textContent = model.phase;
    inputPanel.querySelector(".request-text")!.textContent =
        model.scenario.input;
    contextTitle.textContent = model.contextTitle;
    contextValue.textContent = model.contextValue;
    outputTitle.textContent = `OUTPUT · ${model.outputTitle}`;
    outputText.textContent = model.outputText;
    outputPanel.classList.toggle("ready", model.outputReady);
    outputPanel.classList.toggle("long", model.outputText.length > 450);
    outputMeta.replaceChildren();
    if (model.outputReady && model.stage === "verified") {
        outputMeta.append(
            node(
                "span",
                undefined,
                `verification_status=${model.scenario.verification.status}`,
            ),
            node("span", undefined, `trace_id=${model.scenario.traceId}`),
            node(
                "span",
                undefined,
                "finish_reason=stop · model=uncensored-model",
            ),
        );
    } else if (model.outputReady) {
        outputMeta.append(
            node(
                "span",
                undefined,
                `step=${model.step + 1}/${model.recording.steps.length} · process output complete`,
            ),
            node(
                "span",
                undefined,
                "evidence output is not a final ChatCompletion",
            ),
        );
    } else {
        outputMeta.append(
            node(
                "span",
                undefined,
                `step=${model.step + 1}/${model.recording.steps.length} · release gate closed`,
            ),
            node(
                "span",
                undefined,
                "final output requires composition + verify_after",
            ),
        );
    }
    for (const [index, card] of model.cards.entries()) {
        const elements = cardElements[index];
        if (elements === undefined) continue;
        const state =
            index < model.step ? "done" : index === model.step ? "now" : "todo";
        elements.item.className = `track-card ${state}`;
        elements.item.dataset.state = state;
        elements.values.replaceChildren();
        if (state === "todo") {
            elements.values.append(node("span", "track-empty", "—"));
            continue;
        }
        for (const [name, value] of card.values) {
            const row = node("div", "track-row");
            row.append(
                node("span", undefined, name),
                node("span", undefined, value),
            );
            elements.values.append(row);
        }
    }
    stepCount.textContent = `STEP ${model.step + 1} OF ${model.recording.steps.length}`;
    captionText.textContent = model.caption;
    captionWhy.querySelector("span")!.textContent = model.why;
    const activeNodes =
        model.activeNodes ?? getStageVisualState(model.stage).activeNodes;
    for (const [id, label] of nodeLabels)
        label.classList.toggle("active", activeNodes.includes(id));
    stageRoot.dataset.sceneKind = model.sceneKind;
    updateSpecialOverlay(model);
    const overview = model.sceneKind === "pipeline_graph";
    labelsHost.hidden = !overview;
    packetsHost.hidden = !overview;
    uniqueLabelsHost.hidden = overview;
    pipelineScene.setVisible(overview);
    uniqueScene.setVisible(!overview);
    if (overview) {
        activeStage = model.stage;
        stageRoot.dataset.stage = activeStage;
        pipelineScene.setVisual(
            activeStage,
            model.view,
            model.activeNodes,
            model.activeRoutes,
        );
    } else {
        uniqueScene.setModel(model);
    }
}

let currentRecording: RecordingDefinition = RECORDINGS[0]!;
function renderAt(seconds: number): void {
    const frame = timelineAt(seconds, currentRecording.durations);
    const model = createRecordingModel(frame.step, currentRecording);
    update(model);
    if (model.sceneKind === "pipeline_graph") pipelineScene.draw(seconds);
    else uniqueScene.draw(seconds);
}

function loadRecording(id: string): void {
    currentRecording = recordingById(id);
    buildCards(createRecordingModel(0, currentRecording));
    renderAt(0);
}

declare global {
    interface Window {
        breakfuserGif: {
            renderAt: (seconds: number) => void;
            setStep: (step: number) => void;
            load: (id: string) => void;
            list: () => {
                id: string;
                file: string;
                duration: number;
                steps: number;
                keyframeTimes: number[];
            }[];
            duration: number;
            recording: string;
        };
    }
}

window.breakfuserGif = {
    renderAt,
    load: loadRecording,
    list: () =>
        RECORDINGS.map((recording) => ({
            id: recording.id,
            file: recording.file,
            duration: recordingDuration(recording),
            steps: recording.steps.length,
            keyframeTimes: recording.steps.map((_, step) =>
                recordingStepStart(recording, step),
            ),
        })),
    get duration() {
        return recordingDuration(currentRecording);
    },
    get recording() {
        return currentRecording.id;
    },
    setStep(step) {
        renderAt(recordingStepStart(currentRecording, step) + 0.6);
    },
};

const parameters = new URLSearchParams(window.location.search);
loadRecording(parameters.get("recording") ?? currentRecording.id);
const manual = parameters.has("manual") || parameters.has("still");
const stillStep = Number(parameters.get("step") ?? "0");
if (manual) {
    window.breakfuserGif.setStep(Number.isFinite(stillStep) ? stillStep : 0);
} else {
    const started = performance.now();
    const animate = (now: number) => {
        renderAt((now - started) / 1000);
        requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
}
