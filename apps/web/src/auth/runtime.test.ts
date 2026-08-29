import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createDeterministicAuthGateway,
  protectedRequestHeaders,
  resolveAuthRuntimeConfig,
  SESSION_STORAGE_KEYS,
} from "./runtime";

describe("authentication runtime boundary", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("allows zero-credential deterministic demo but fails closed for production", () => {
    expect(
      resolveAuthRuntimeConfig({
        VITE_ADAPTER_MODE: "deterministic",
        VITE_DEMO_MODE: "true",
      }),
    ).toMatchObject({ adapterMode: "deterministic", demoMode: true });

    expect(() =>
      resolveAuthRuntimeConfig({
        VITE_ADAPTER_MODE: "production",
        VITE_DEMO_MODE: "true",
      }),
    ).toThrow(/Demo mode cannot be enabled in production/);

    expect(() =>
      resolveAuthRuntimeConfig({
        VITE_ADAPTER_MODE: "production",
        VITE_DEMO_MODE: "false",
      }),
    ).toThrow(/VITE_FIREBASE_API_KEY.*VITE_FIREBASE_APP_CHECK_SITE_KEY/);
  });

  it("creates an explicit synthetic session and clears user state on sign-out", async () => {
    const gateway = createDeterministicAuthGateway({ demoMode: true });
    const listener = vi.fn();
    const stop = gateway.observeSession(listener);

    for (const key of SESSION_STORAGE_KEYS) {
      window.localStorage.setItem(key, "private user state");
      window.sessionStorage.setItem(key, "private user state");
    }

    await gateway.signInDemo();
    expect(listener).toHaveBeenLastCalledWith({
      uid: "demo-meera",
      displayName: "Meera Sharma",
      synthetic: true,
    });

    expect(await gateway.getIdToken()).toBe("demo-learner-token");
    await gateway.signOut();
    expect(listener).toHaveBeenLastCalledWith(null);
    for (const key of SESSION_STORAGE_KEYS) {
      expect(window.localStorage.getItem(key)).toBeNull();
      expect(window.sessionStorage.getItem(key)).toBeNull();
    }
    stop();
  });

  it("sends both Firebase tokens in production and never substitutes a demo token", async () => {
    const headers = await protectedRequestHeaders(
      {
        getIdToken: vi.fn().mockResolvedValue("firebase-id-token"),
        getAppCheckToken: vi.fn().mockResolvedValue("firebase-app-check-token"),
      },
      "production",
    );

    expect(headers).toEqual({
      Authorization: "Bearer firebase-id-token",
      "X-Firebase-AppCheck": "firebase-app-check-token",
    });

    await expect(
      protectedRequestHeaders(
        {
          getIdToken: vi.fn().mockResolvedValue("firebase-id-token"),
          getAppCheckToken: vi.fn().mockResolvedValue(null),
        },
        "production",
      ),
    ).rejects.toThrow("Firebase App Check is not configured");
  });

  it("stays signed out and reports a retryable error when local cleanup fails", async () => {
    const gateway = createDeterministicAuthGateway({ demoMode: true });
    const listener = vi.fn();
    gateway.observeSession(listener);
    await gateway.signInDemo();
    const removeItem = vi
      .spyOn(Storage.prototype, "removeItem")
      .mockImplementationOnce(() => { throw new Error("storage unavailable"); });

    await expect(gateway.signOut()).rejects.toThrow("local user data cleanup");
    expect(listener).toHaveBeenLastCalledWith(null);
    removeItem.mockRestore();
  });
});
