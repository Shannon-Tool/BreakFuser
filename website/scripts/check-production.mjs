#!/usr/bin/env node

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [sourceLicense, distributedLicense, indexHtml] = await Promise.all([
    readFile(new URL("../node_modules/three/LICENSE", import.meta.url), "utf8"),
    readFile(new URL("../dist/THREE-LICENSE.txt", import.meta.url), "utf8"),
    readFile(new URL("../dist/index.html", import.meta.url), "utf8"),
]);

assert.equal(
    distributedLicense,
    sourceLicense,
    "dist/THREE-LICENSE.txt must exactly match three/LICENSE",
);

const configuredBase = process.env.VITE_BASE_PATH ?? "/BreakFuser/";
const expectedBase = configuredBase.endsWith("/")
    ? configuredBase
    : `${configuredBase}/`;
for (const match of indexHtml.matchAll(/(?:src|href)="([^"]+)"/g)) {
    const url = match[1];
    if (url?.startsWith("/")) {
        assert.ok(
            url.startsWith(expectedBase),
            `Production asset ${url} must use the configured base ${expectedBase}`,
        );
    }
}

console.log(
    `Production artifact includes the exact Three.js MIT license and ${expectedBase} asset paths.`,
);
