import { afterEach, describe, expect, it, vi } from "vitest";
import { createJourneyApiGateway } from "./runtime";

describe("journey API boundary", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("stops a stalled plan request and preserves a retryable failure", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      })
    ));
    const gateway = createJourneyApiGateway({
      apiBaseUrl: "https://api.example.test",
      requestHeaders: async () => ({ Authorization: "Bearer test" }),
      fetcher: fetcher as typeof fetch,
    });

    const result = expect(gateway.create("2026-09-10")).rejects.toThrow(
      "Plan request timed out after 75 seconds.",
    );
    await vi.advanceTimersByTimeAsync(75_000);

    await result;
    expect(fetcher.mock.calls[0]?.[1]?.signal).toBeInstanceOf(AbortSignal);
    expect(fetcher.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });
});
