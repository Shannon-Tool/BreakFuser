import { defineConfig } from "vitest/config";

export default defineConfig(({ command }) => ({
    base:
        process.env.VITE_BASE_PATH ??
        (command === "build" ? "/BreakFuser/" : "/"),
    server: {
        allowedHosts:
            process.env.VITE_ALLOWED_HOSTS?.split(",")
                .map((host) => host.trim())
                .filter((host) => host.length > 0) ?? [],
    },
    test: {
        include: ["tests/**/*.test.ts"],
    },
}));
