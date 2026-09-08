export type RecommendationType = "partner" | "mentor";
export type MatchFactor =
  | "hobbyGoalFit"
  | "schedule"
  | "language"
  | "skillLevel"
  | "pace"
  | "format"
  | "price";

export interface LocalizedText {
  en: string;
  hi: string;
}

export interface FactorBreakdown {
  factor: MatchFactor;
  points: number;
  maxPoints: number;
}

export interface MatchReason extends FactorBreakdown {
  reasonCode: string;
  text: LocalizedText;
}

export interface RecommendationResult {
  candidateId: string;
  candidateType: RecommendationType;
  displayName: string;
  synthetic: true;
  score: number;
  scoreOutOf: 100;
  hobby: LocalizedText;
  reasons: [MatchReason, MatchReason, MatchReason];
  factorBreakdown: FactorBreakdown[];
}

export interface DemoProfile {
  candidateId: string;
  displayName: string;
  synthetic: true;
  hobby: LocalizedText;
}

export interface RecommendationResponse {
  contractVersion: "matching-v1.0.0";
  recommendationType: RecommendationType;
  source: "deterministic_synthetic";
  synthetic: true;
  status: "matched" | "no_matches";
  scoreThreshold: 65;
  resultLimit: 3;
  results: RecommendationResult[];
  demoProfiles: DemoProfile[];
  emptyReason?: "no_eligible_candidate" | "hobby_not_in_catalog";
}

export interface RecommendationGateway {
  find(type: RecommendationType): Promise<RecommendationResponse>;
}

interface RecommendationApiGatewayOptions {
  apiBaseUrl: string;
  requestHeaders(): Promise<Record<string, string>>;
  fetcher?: typeof fetch;
}

export function createRecommendationApiGateway({
  apiBaseUrl,
  requestHeaders,
  fetcher = fetch,
}: RecommendationApiGatewayOptions): RecommendationGateway {
  const api = apiBaseUrl.replace(/\/$/, "");
  return {
    async find(type) {
      const response = await fetcher(
        `${api}/api/v1/recommendations?type=${encodeURIComponent(type)}`,
        { method: "GET", headers: await requestHeaders() },
      );
      if (!response.ok) {
        throw new Error(`Recommendation request failed with status ${response.status}.`);
      }
      return response.json() as Promise<RecommendationResponse>;
    },
  };
}
