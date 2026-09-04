import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("web release build contract", () => {
  it("uses the approved TypeScript Vite config without stale generated overrides", () => {
    const webRoot = resolve(process.cwd());
    const packageJson = JSON.parse(
      readFileSync(resolve(webRoot, "package.json"), "utf8"),
    ) as { scripts: Record<string, string> };

    expect(packageJson.scripts.build).toContain("vite build --config vite.config.ts");
    expect(existsSync(resolve(webRoot, "vite.config.js"))).toBe(false);
    expect(existsSync(resolve(webRoot, "vite.config.d.ts"))).toBe(false);
  });

  it("ships installable standard and maskable PWA icons", () => {
    const webRoot = resolve(process.cwd());
    const viteConfig = readFileSync(resolve(webRoot, "vite.config.ts"), "utf8");

    expect(viteConfig).toContain('src: "/pwa-192.png"');
    expect(viteConfig).toContain('src: "/pwa-512.png"');
    expect(viteConfig).toContain('src: "/pwa-maskable-512.png"');
    expect(existsSync(resolve(webRoot, "public/pwa-192.png"))).toBe(true);
    expect(existsSync(resolve(webRoot, "public/pwa-512.png"))).toBe(true);
    expect(existsSync(resolve(webRoot, "public/pwa-maskable-512.png"))).toBe(true);
  });

  it("keeps Firebase authentication helpers outside the PWA navigation fallback", () => {
    const webRoot = resolve(process.cwd());
    const viteConfig = readFileSync(resolve(webRoot, "vite.config.ts"), "utf8");

    expect(viteConfig).toContain("navigateFallbackDenylist");
    expect(viteConfig).toContain("/^\\/__\\/auth\\//");
    expect(viteConfig).toContain("/^\\/__\\/firebase\\//");
  });
});
