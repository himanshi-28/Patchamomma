import { describe, expect, it, vi } from "vitest";
import { signInWithPopupOrRedirect } from "./firebase";

describe("Firebase Google sign-in compatibility", () => {
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
