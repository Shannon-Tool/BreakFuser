import { SCENARIOS } from "../src/scenarios";
import { LINEAR_STAGES } from "../src/types";
import { expect, test } from "./fixtures";

const general = SCENARIOS[0];
const medical = SCENARIOS[1];
if (general === undefined || medical === undefined) {
    throw new Error("Curated traces are required for live-data browser tests");
}

test("request JSON, ordered events, blackboard evidence, and verified metadata stay synchronized", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page.locator(".request-json")).toHaveText(
        JSON.stringify(general.request, null, 2),
    );
    await expect(page.locator(".process-event")).toHaveCount(2);
    await expect(page.locator(".evidence-record")).toHaveCount(0);
    await expect(page.locator(".response-metadata")).toContainText("pending");

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(
        page.locator(".process-event[data-phase='acquisition']"),
    ).toHaveCount(6);
    for (const branch of ["document", "smart", "local"]) {
        await expect(
            page.locator(
                `.process-event[data-phase='acquisition'][data-branch='${branch}']`,
            ),
        ).toHaveCount(2);
    }
    await expect(page.locator("[data-figure='acquisition']")).toHaveAttribute(
        "data-state",
        "complete",
    );
    await expect(page.locator(".evidence-record")).toHaveCount(0);

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator(".process-events")).toContainText(
        "RefusalClass=partial_refusal",
    );
    await expect(page.locator(".process-events")).toContainText(
        "strategy=refusal_repair",
    );
    await expect(page.locator(".evidence-record")).toHaveCount(0);

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator(".process-events")).toContainText(
        `EvidenceBlackboard · spans=${general.evidence.length}`,
    );
    await expect(page.locator(".evidence-record")).toHaveCount(
        general.evidence.length,
    );
    await expect(
        page.locator(".evidence-record[data-origin='local']"),
    ).toContainText(general.localDraft);
    await expect(
        page.locator(
            ".evidence-record[data-origin='remote'][data-reveal-stage='recovery']",
        ),
    ).toHaveCount(general.recoveredFacts.length);
    await expect(page.locator(".output-panel")).toHaveAttribute(
        "data-state",
        "pending",
    );

    await page.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(page.locator(".output-text")).toHaveText(
        general.finalResponse,
    );
    await expect(page.locator(".response-metadata")).toHaveText(
        JSON.stringify(general.responsePanelMetadata, null, 2),
    );
    expect(general.responsePanelMetadata.pipeline_stages).toEqual(
        LINEAR_STAGES,
    );
    await expect(page.locator(".process-events")).toContainText(
        general.traceId,
    );
});

test("scenario selection replaces request, recovery, evidence, and final response data", async ({
    page,
}) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await page
        .getByRole("button", { name: "Select Medical information scenario" })
        .click();
    await expect(page.locator(".request-json")).toHaveText(
        JSON.stringify(medical.request, null, 2),
    );
    for (let step = 0; step < 4; step += 1) {
        await page
            .getByRole("button", { name: "Next step", exact: true })
            .click();
    }
    await expect(page.locator(".process-events")).toContainText(
        "RefusalClass=hedge_heavy",
    );
    await expect(page.locator(".process-events")).toContainText(
        "strategy=crescendo",
    );
    await expect(page.locator(".output-text")).toHaveText(
        medical.finalResponse,
    );
    await expect(page.locator(".response-metadata")).toContainText(
        medical.traceId,
    );
});
