import { describe, expect, it, vi } from "vitest";
import { createFirebaseAuthGateway, signInWithPopupOrRedirect } from "./firebase";

const firebaseMocks = vi.hoisted(() => ({
  getApps: vi.fn(() => []),
  initializeApp: vi.fn(() => ({ name: "sakhicircle" })),
  getAuth: vi.fn(() => ({ currentUser: null })),
  getRedirectResult: vi.fn(),
  isSignInWithEmailLink: vi.fn(() => false),
  onAuthStateChanged: vi.fn(),
  signInWithEmailLink: vi.fn(),
}));

vi.mock("firebase/app", () => ({
  getApps: firebaseMocks.getApps,
  initializeApp: firebaseMocks.initializeApp,
}));

vi.mock("firebase/auth", () => ({
  getAuth: firebaseMocks.getAuth,
  getRedirectResult: firebaseMocks.getRedirectResult,
  isSignInWithEmailLink: firebaseMocks.isSignInWithEmailLink,
  onAuthStateChanged: firebaseMocks.onAuthStateChanged,
  signInWithEmailLink: firebaseMocks.signInWithEmailLink,
}));

describe("Firebase Google sign-in compatibility", () => {
  it("observes the restored session before redirect processing finishes", async () => {
    firebaseMocks.getRedirectResult.mockImplementation(() => new Promise(() => undefined));
    firebaseMocks.onAuthStateChanged.mockReturnValue(() => undefined);
    const gateway = createFirebaseAuthGateway({
      adapterMode: "firebase_emulator",
      demoMode: false,
      firebase: {
        apiKey: "test-api-key",
        authDomain: "test.firebaseapp.com",
        projectId: "test-project",
        appId: "test-app-id",
      },
    });

    const onError = vi.fn();
    gateway.observeSession(vi.fn(), onError);

    await vi.waitFor(() => {
      expect(
        firebaseMocks.onAuthStateChanged.mock.calls.length + onError.mock.calls.length,
      ).toBeGreaterThan(0);
    });
    expect(onError).not.toHaveBeenCalled();
    expect(firebaseMocks.onAuthStateChanged).toHaveBeenCalledOnce();
  });

  it("starts with a full-page redirect on privacy-focused browsers", async () => {
    const popup = vi.fn();
    const redirect = vi.fn().mockResolvedValue(undefined);

    await signInWithPopupOrRedirect({
      popup,
      redirect,
      preferRedirect: true,
    });

    expect(redirect).toHaveBeenCalledTimes(1);
    expect(popup).not.toHaveBeenCalled();
  });

  it("falls back to a full-page redirect when a browser leaves the popup pending", async () => {
    const redirect = vi.fn().mockResolvedValue(undefined);

    await signInWithPopupOrRedirect({
      popup: () => new Promise(() => undefined),
      redirect,
      popupTimeoutMs: 0,
    });

    expect(redirect).toHaveBeenCalledTimes(1);
  });

  it("falls back immediately when the browser blocks the popup", async () => {
    const redirect = vi.fn().mockResolvedValue(undefined);

    await signInWithPopupOrRedirect({
      popup: vi.fn().mockRejectedValue({ code: "auth/popup-blocked" }),
      redirect,
    });

    expect(redirect).toHaveBeenCalledTimes(1);
  });

  it("does not redirect after the person deliberately closes the popup", async () => {
    const redirect = vi.fn();
    const cancelled = { code: "auth/popup-closed-by-user" };

    await expect(signInWithPopupOrRedirect({
      popup: vi.fn().mockRejectedValue(cancelled),
      redirect,
    })).rejects.toBe(cancelled);
    expect(redirect).not.toHaveBeenCalled();
  });
});
