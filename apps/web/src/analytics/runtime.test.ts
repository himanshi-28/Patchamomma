import { describe, expect, it, vi } from "vitest";
import {
  createAnalyticsAwareFetcher,
  createAnalyticsReceiptGateway,
  readAnalyticsReceipt,
} from "./runtime";


describe("SC-710 analytics receipt transport", () => {
  it("reads only the server-issued receipt pair from a successful business response", () => {
    const response = new Response(JSON.stringify({ status: "saved" }), {
      status: 200,
      headers: {
        "X-Sakhi-Analytics-Event-Id": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
        "X-Sakhi-Analytics-Receipt": "v1.opaque.signed",
        "X-Trace-Id": "must-not-enter-analytics",
      },
    });

    expect(readAnalyticsReceipt(response)).toEqual({
      eventId: "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
      actionReceipt: "v1.opaque.signed",
    });
  });

  it("returns no receipt unless both server-owned headers are present", () => {
    expect(readAnalyticsReceipt(new Response(null, {
      headers: { "X-Sakhi-Analytics-Receipt": "v1.opaque.signed" },
    }))).toBeUndefined();
    expect(readAnalyticsReceipt(new Response(null, {
      headers: { "X-Sakhi-Analytics-Event-Id": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1" },
    }))).toBeUndefined();
  });

  it("can resume only one opaque server-issued receipt without event properties", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      schemaVersion: "analytics-v1.0.0",
      eventId: "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
      status: "queued",
      duplicate: false,
    }), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    }));
    const gateway = createAnalyticsReceiptGateway({
      apiBaseUrl: "http://localhost:8080/",
      requestHeaders: async () => ({ Authorization: "Bearer synthetic" }),
      fetcher,
    });

    await gateway.resume({
      eventId: "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
      actionReceipt: "v1.opaque.signed",
    });

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8080/api/v1/analytics/events",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer synthetic",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          schemaVersion: "analytics-v1.0.0",
          eventId: "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
          actionReceipt: "v1.opaque.signed",
        }),
      },
    );
    const body = JSON.parse(String(fetcher.mock.calls[0][1]?.body));
    expect(Object.keys(body).sort()).toEqual([
      "actionReceipt",
      "eventId",
      "schemaVersion",
    ]);
    expect(body).not.toHaveProperty("eventName");
    expect(body).not.toHaveProperty("outcome");
    expect(body).not.toHaveProperty("properties");
  });

  it("observes successful product responses and never turns retry failure into product failure", async () => {
    const productResponse = new Response(JSON.stringify({ status: "saved" }), {
      status: 200,
      headers: {
        "X-Sakhi-Analytics-Event-Id": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
        "X-Sakhi-Analytics-Receipt": "v1.opaque.signed",
      },
    });
    const fetcher = vi.fn().mockResolvedValue(productResponse);
    const resume = vi.fn().mockRejectedValue(new Error("queue temporarily unavailable"));
    const analyticsAwareFetch = createAnalyticsAwareFetcher({ fetcher, resume });

    await expect(analyticsAwareFetch("http://localhost:8080/api/v1/profile", {
      method: "PUT",
    })).resolves.toBe(productResponse);
    await vi.waitFor(() => expect(resume).toHaveBeenCalledWith({
      eventId: "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
      actionReceipt: "v1.opaque.signed",
    }));
  });

  it("does not emit or resume analytics for a failed product operation", async () => {
    const resume = vi.fn();
    const analyticsAwareFetch = createAnalyticsAwareFetcher({
      fetcher: vi.fn().mockResolvedValue(new Response(null, { status: 422 })),
      resume,
    });

    await analyticsAwareFetch("http://localhost:8080/api/v1/profile", { method: "PUT" });

    expect(resume).not.toHaveBeenCalled();
  });
});
