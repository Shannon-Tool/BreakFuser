#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const website = path.join(root, "website");
const requireWebsite = createRequire(path.join(website, "package.json"));
const { chromium } = requireWebsite("@playwright/test");
const { PNG } = requireWebsite("pngjs");
const gifenc = requireWebsite("gifenc");
const gifApi = "quantize" in gifenc ? gifenc : gifenc.default;
const { GIFEncoder, applyPalette, quantize } = gifApi;

const args = process.argv.slice(2);
const option = (name, fallback) => {
    const index = args.indexOf(`--${name}`);
    return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};
const fps = Number(option("fps", "10"));
const fuzz = Number(option("fuzz", "3"));
const outputDirectory = path.resolve(
    option("out", path.join(root, "assets/animations")),
);
const only = new Set(option("only", "").split(",").filter(Boolean));
const keyframes = option("keyframes", "");
const inspection = option("inspect", "");
const stillOnly = args.includes("--still");
if (!Number.isFinite(fps) || fps < 5 || fps > 12)
    throw new Error("fps must be between 5 and 12");
if (!Number.isFinite(fuzz) || fuzz < 0 || fuzz > 20)
    throw new Error("fuzz must be between 0 and 20");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let server = null;
let browser = null;

async function startRenderer() {
    const supplied = option("base", process.env.BREAKFUSER_GIF_URL ?? "");
    if (supplied) return supplied;
    const port = Number(option("port", "4175"));
    const base = `http://127.0.0.1:${port}/gif.html?manual`;
    server = spawn(
        process.execPath,
        [
            path.join(website, "node_modules/vite/bin/vite.js"),
            "--host",
            "127.0.0.1",
            "--port",
            String(port),
            "--strictPort",
        ],
        { cwd: website, stdio: "ignore" },
    );
    for (let attempt = 0; attempt < 100; attempt += 1) {
        try {
            const response = await fetch(base);
            if (response.ok) return base;
        } catch {}
        await sleep(100);
    }
    throw new Error("The local GIF renderer did not start");
}

function paletteFrom(samples) {
    const pixels = samples.reduce((sum, sample) => sum + sample.length / 4, 0);
    const stride = Math.max(1, Math.ceil(pixels / 2_000_000));
    const length =
        samples.reduce(
            (sum, sample) => sum + Math.ceil(sample.length / 4 / stride),
            0,
        ) * 4;
    const picked = new Uint8Array(length);
    let offset = 0;
    for (const sample of samples) {
        for (let pixel = 0; pixel < sample.length / 4; pixel += stride) {
            picked[offset] = sample[pixel * 4];
            picked[offset + 1] = sample[pixel * 4 + 1];
            picked[offset + 2] = sample[pixel * 4 + 2];
            picked[offset + 3] = 255;
            offset += 4;
        }
    }
    return quantize(picked.subarray(0, offset), 255, { format: "rgb565" });
}

function createWriter(width, height, palette) {
    const count = width * height;
    const transparentIndex = palette.length;
    const table = [...palette.map((colour) => colour.slice(0, 3)), [0, 0, 0]];
    const gif = GIFEncoder();
    const shown = new Uint8Array(count);
    let pending = null;
    let written = 0;
    let added = 0;
    const flush = () => {
        if (!pending) return;
        gif.writeFrame(pending.index, width, height, {
            palette: written === 0 ? table : undefined,
            delay: pending.delay,
            transparent: written > 0,
            transparentIndex,
            dispose: 1,
            repeat: 0,
        });
        written += 1;
        pending = null;
    };
    return {
        add(rgba, delay) {
            if (rgba.length !== count * 4)
                throw new Error("Captured frame has the wrong dimensions");
            const index = applyPalette(rgba, palette, "rgb565");
            if (written === 0 && !pending) {
                shown.set(index);
                pending = { index, delay };
                return;
            }
            added += 1;
            const tolerance = added % 12 === 0 ? Math.floor(fuzz / 4) : fuzz;
            let changed = 0;
            for (let pixel = 0; pixel < count; pixel += 1) {
                const before = shown[pixel];
                if (index[pixel] === before) {
                    index[pixel] = transparentIndex;
                    continue;
                }
                if (tolerance > 0) {
                    const colour = palette[before];
                    const at = pixel * 4;
                    if (
                        Math.abs(rgba[at] - colour[0]) <= tolerance &&
                        Math.abs(rgba[at + 1] - colour[1]) <= tolerance &&
                        Math.abs(rgba[at + 2] - colour[2]) <= tolerance
                    ) {
                        index[pixel] = transparentIndex;
                        continue;
                    }
                }
                shown[pixel] = index[pixel];
                changed += 1;
            }
            if (changed === 0) {
                pending.delay += delay;
                return;
            }
            flush();
            pending = { index, delay };
        },
        finish() {
            flush();
            gif.finish();
            return { bytes: gif.bytes(), frames: written };
        },
    };
}

function inspectGif(bytes) {
    const signature = String.fromCharCode(...bytes.subarray(0, 6));
    if (signature !== "GIF89a" && signature !== "GIF87a")
        throw new Error("Not a GIF");
    const u16 = (at) => bytes[at] | (bytes[at + 1] << 8);
    let at = 13 + (bytes[10] & 0x80 ? 3 * (1 << ((bytes[10] & 7) + 1)) : 0);
    let frames = 0;
    let durationMs = 0;
    let loops = null;
    let ended = false;
    const skipBlocks = () => {
        while (at < bytes.length && bytes[at] !== 0) at += 1 + bytes[at];
        if (at >= bytes.length) throw new Error("The GIF is truncated");
        at += 1;
    };
    while (at < bytes.length && !ended) {
        const block = bytes[at];
        at += 1;
        if (block === 0x3b) {
            ended = true;
            break;
        }
        if (block === 0x21) {
            const label = bytes[at];
            at += 1;
            if (label === 0xf9) {
                durationMs += u16(at + 2) * 10;
                at += 6;
                continue;
            }
            if (
                label === 0xff &&
                String.fromCharCode(...bytes.subarray(at + 1, at + 12)) ===
                    "NETSCAPE2.0"
            )
                loops = u16(at + 14);
            skipBlocks();
            continue;
        }
        if (block !== 0x2c) throw new Error(`Unexpected GIF block ${block}`);
        const flags = bytes[at + 8];
        at += 9 + (flags & 0x80 ? 3 * (1 << ((flags & 7) + 1)) : 0) + 1;
        skipBlocks();
        frames += 1;
    }
    if (!ended) throw new Error("The GIF has no trailer");
    return { width: u16(6), height: u16(8), frames, durationMs, loops };
}

async function validateStage(page, step, recording) {
    const state = await page.evaluate(() => ({
        recording: document.querySelector("#stage")?.dataset.recording,
        stage: document.querySelector("#stage")?.dataset.stage,
        step: Number(document.querySelector("#stage")?.dataset.step),
        output: document.querySelector(".output-text")?.textContent ?? "",
        outputTitle:
            document.querySelector(".stage-panel.output .stage-label")
                ?.textContent ?? "",
        cards: [...document.querySelectorAll(".track-card")].map(
            (card) => card.dataset.state,
        ),
    }));
    if (state.recording !== recording.id)
        throw new Error(`Wrong recording loaded: ${state.recording}`);
    if (state.step !== step)
        throw new Error(`Stage ${step} did not update in ${recording.id}`);
    const expected = Array.from({ length: state.cards.length }, (_, index) =>
        index < step ? "done" : index === step ? "now" : "todo",
    );
    if (JSON.stringify(state.cards) !== JSON.stringify(expected))
        throw new Error(
            `Process cards are wrong at ${recording.id} step ${step}`,
        );
    if (!state.output.trim())
        throw new Error(
            `Output panel is empty at ${recording.id} step ${step}`,
        );
    if (
        state.stage !== "verified" &&
        state.outputTitle.includes("VERIFIED CHATCOMPLETION")
    )
        throw new Error(
            `Verified output leaked before verification in ${recording.id}`,
        );
}

async function capture(page) {
    const buffer = await page
        .locator("#stage")
        .screenshot({ type: "png", timeout: 120_000 });
    const png = PNG.sync.read(buffer);
    if (png.width !== 1200 || png.height !== 750)
        throw new Error(`Unexpected capture ${png.width}×${png.height}`);
    return png;
}

async function inspectInBrowser(gifBytes, directory, sampleTimes) {
    await mkdir(directory, { recursive: true });
    const page = await browser.newPage({
        viewport: { width: 1200, height: 750 },
    });
    const source = `data:image/gif;base64,${Buffer.from(gifBytes).toString("base64")}`;
    await page.setContent(
        `<style>body{margin:0;background:#070b11}img{display:block;width:1200px;height:750px}</style><img src="${source}">`,
    );
    await page.locator("img").evaluate((image) => image.decode());
    const targets = sampleTimes.map((seconds) => Math.round(seconds * 1000));
    let previous = 0;
    for (const [index, target] of targets.entries()) {
        await sleep(index === 0 ? 120 : target - previous);
        previous = target;
        await page.locator("img").screenshot({
            path: path.join(
                directory,
                ["input.png", "process.png", "output.png"][index],
            ),
        });
    }
    await page.close();
}

try {
    const base = await startRenderer();
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
        viewport: { width: 1200, height: 750 },
        deviceScaleFactor: 1,
    });
    await page.goto(base, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => Boolean(window.breakfuserGif));
    const available = await page.evaluate(() => window.breakfuserGif.list());
    if (available.length !== 10)
        throw new Error(`Expected ten recordings, found ${available.length}`);
    const recordings = available.filter(
        (recording) => only.size === 0 || only.has(recording.id),
    );
    if (only.size > 0 && recordings.length !== only.size)
        throw new Error("An --only recording ID is unknown");
    const results = [];
    let totalBytes = 0;
    for (const recording of recordings) {
        await page.evaluate(
            (id) => window.breakfuserGif.load(id),
            recording.id,
        );
        const samples = [];
        const indices = [
            0,
            Math.floor((recording.steps - 1) / 2),
            recording.steps - 1,
        ];
        for (const [position, step] of indices.entries()) {
            await page.evaluate(
                (value) => window.breakfuserGif.setStep(value),
                step,
            );
            await validateStage(page, step, recording);
            const frame = await capture(page);
            samples.push(frame.data);
            if (keyframes) {
                const directory = path.join(keyframes, recording.id);
                await mkdir(directory, { recursive: true });
                const label = ["input", "process", "output"][position];
                await writeFile(
                    path.join(directory, `${label}.png`),
                    PNG.sync.write(frame),
                );
            }
        }
        console.error(`${recording.id}: three keyframes passed`);
        if (stillOnly) {
            results.push({
                id: recording.id,
                duration: recording.duration,
                keyframes: true,
            });
            continue;
        }
        const writer = createWriter(1200, 750, paletteFrom(samples));
        const frameCount = Math.round(recording.duration * fps);
        const delay = 1000 / fps;
        for (let frame = 0; frame < frameCount; frame += 1) {
            await page.evaluate(
                (value) => window.breakfuserGif.renderAt(value),
                frame / fps,
            );
            const png = await capture(page);
            writer.add(png.data, delay);
            if ((frame + 1) % 40 === 0)
                console.error(
                    `${recording.id}: ${frame + 1}/${frameCount} frames`,
                );
        }
        const encoded = writer.finish();
        const output = path.join(outputDirectory, recording.file);
        await mkdir(path.dirname(output), { recursive: true });
        await writeFile(output, encoded.bytes);
        const metadata = inspectGif(encoded.bytes);
        const expectedDuration = frameCount * delay;
        if (metadata.width !== 1200 || metadata.height !== 750)
            throw new Error(`${recording.id}: wrong dimensions`);
        if (metadata.frames < frameCount * 0.6)
            throw new Error(`${recording.id}: too many static frames`);
        if (Math.abs(metadata.durationMs - expectedDuration) > 500)
            throw new Error(`${recording.id}: wrong duration`);
        if (metadata.loops !== 0)
            throw new Error(`${recording.id}: does not loop forever`);
        if (encoded.bytes.length > 2_500_000)
            throw new Error(`${recording.id}: file exceeds 2.5 MB`);
        totalBytes += encoded.bytes.length;
        results.push({
            id: recording.id,
            ...metadata,
            bytes: encoded.bytes.length,
            output,
        });
        console.error(
            `${recording.id}: ${encoded.bytes.length} bytes, ${metadata.frames} frames`,
        );
        if (inspection)
            await inspectInBrowser(
                encoded.bytes,
                path.join(inspection, recording.id),
                indices.map((step, position) =>
                    position === 0
                        ? 0
                        : (recording.keyframeTimes[step] ?? 0) + 0.25,
                ),
            );
    }
    if (!stillOnly && only.size === 0 && totalBytes > 10_000_000)
        throw new Error(`Ten-GIF set exceeds 10 MB: ${totalBytes} bytes`);
    console.log(
        JSON.stringify(
            {
                stillOnly,
                count: results.length,
                totalBytes,
                recordings: results,
            },
            null,
            2,
        ),
    );
    await page.close();
} finally {
    if (browser) await browser.close();
    if (server) server.kill("SIGTERM");
}
