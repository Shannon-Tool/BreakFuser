import { defineConfig } from "@playwright/test";

export default defineConfig({
    testDir: "./e2e",
    fullyParallel: true,
    projects: [
        {
            name: "desktop",
            use: { viewport: { width: 1440, height: 1000 } },
        },
        {
            name: "mobile",
            use: {
                viewport: { width: 390, height: 844 },
                isMobile: true,
                hasTouch: true,
            },
        },
    ],
    forbidOnly: Boolean(process.env.CI),
    retries: process.env.CI ? 2 : 0,
    use: {
        baseURL: "http://127.0.0.1:4173",
        browserName: "chromium",
        headless: true,
    },
    webServer: {
        command:
            "VITE_BASE_PATH=/ npm run build && npm run preview -- --host 127.0.0.1 --port 4173",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
    },
});
