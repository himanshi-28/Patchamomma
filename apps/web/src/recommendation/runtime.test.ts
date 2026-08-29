import { describe, expect, it, vi } from "vitest";
import { createRecommendationApiGateway } from "./runtime";


describe("SC-510 recommendation gateway", () => {
  it("sends one authenticated read-only request with only the approved type query", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "no_matches", results: [] }),
    });
    const gateway = createRecommendationApiGateway({
      apiBaseUrl: "http://localhost:8080/",
      requestHeaders: async () => ({ Authorization: "Bearer synthetic" }),
      fetcher,
    });

    await gateway.find("partner");

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8080/api/v1/recommendations?type=partner",
      { method: "GET", headers: { Authorization: "Bearer synthetic" } },
    );
  });
});

