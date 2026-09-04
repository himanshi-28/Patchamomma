export interface AnalyticsReceipt {
  eventId: string;
  actionReceipt: string;
}

export interface AnalyticsStatus {
  schemaVersion: "analytics-v1.0.0";
  eventId: string;
  status: "queued" | "written" | "failed" | "discarded";
  duplicate: boolean;
}

export interface AnalyticsReceiptGateway {
  resume(receipt: AnalyticsReceipt): Promise<AnalyticsStatus>;
}

interface AnalyticsReceiptGatewayOptions {
  apiBaseUrl: string;
  requestHeaders(): Promise<Record<string, string>>;
  fetcher?: typeof fetch;
}

interface AnalyticsAwareFetcherOptions {
  fetcher?: typeof fetch;
  resume(receipt: AnalyticsReceipt): Promise<unknown>;
}

export function readAnalyticsReceipt(response: Response): AnalyticsReceipt | undefined {
  const eventId = response.headers.get("X-Sakhi-Analytics-Event-Id");
  const actionReceipt = response.headers.get("X-Sakhi-Analytics-Receipt");
  if (!eventId || !actionReceipt) return undefined;
  return { eventId, actionReceipt };
}

export function createAnalyticsReceiptGateway({
  apiBaseUrl,
  requestHeaders,
  fetcher = fetch,
}: AnalyticsReceiptGatewayOptions): AnalyticsReceiptGateway {
  const api = apiBaseUrl.replace(/\/$/, "");
  return {
    async resume(receipt) {
      const response = await fetcher(`${api}/api/v1/analytics/events`, {
        method: "POST",
        headers: {
          ...(await requestHeaders()),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          schemaVersion: "analytics-v1.0.0",
          eventId: receipt.eventId,
          actionReceipt: receipt.actionReceipt,
        }),
      });
      if (!response.ok) {
        throw new Error(`Analytics receipt retry failed with status ${response.status}.`);
      }
      return response.json() as Promise<AnalyticsStatus>;
    },
  };
}

export function createAnalyticsAwareFetcher({
  fetcher = fetch,
  resume,
}: AnalyticsAwareFetcherOptions): typeof fetch {
  return async (input, init) => {
    const response = await fetcher(input, init);
    if (response.ok) {
      const receipt = readAnalyticsReceipt(response);
      if (receipt) void resume(receipt).catch(() => undefined);
    }
    return response;
  };
}
