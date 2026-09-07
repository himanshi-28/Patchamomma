export type Locale = "en" | "hi";

export interface LearningWish {
  hobby: string;
  experience: string;
  goal: string;
  availability: string;
  language: string;
  accessibility: string;
  format: string;
  planConsent: boolean;
  matchingConsent: boolean;
  city: string;
}

export interface TranscriptCapture {
  transcript: string;
  providerName: string;
  providerPolicy: string;
}

export interface TranscriptAdapter {
  readonly providerName: string;
  readonly providerPolicy: string;
  capture(locale: Locale): Promise<TranscriptCapture>;
}

export type TranscriptCaptureFailure =
  | "permission_denied"
  | "unsupported"
  | "no_speech"
  | "unavailable";

export class TranscriptCaptureError extends Error {
  constructor(readonly reason: TranscriptCaptureFailure) {
    super(`Speech capture failed: ${reason}`);
    this.name = "TranscriptCaptureError";
  }
}

interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  readonly [index: number]: { transcript: string };
}

interface SpeechRecognitionEventLike extends Event {
  readonly results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export interface ProfileGateway {
  save(profile: LearningWish): Promise<void>;
}

export type ProfileExtractionSource = "gemini" | "deterministic" | "deterministic_fallback";

export interface ProfileExtractionResult {
  source: ProfileExtractionSource;
  fields: LearningWish;
}

export interface ProfileExtractionGateway {
  readonly providerName: string;
  readonly providerPolicy: string;
  extract(transcript: string, locale: Locale): Promise<ProfileExtractionResult>;
}

export type ProfileSaveFailure = "maintenance" | "unauthorized" | "security" | "unavailable";

export class ProfileSaveError extends Error {
  constructor(readonly reason: ProfileSaveFailure) {
    super(`Profile save failed: ${reason}`);
    this.name = "ProfileSaveError";
  }
}

const deterministicSamples: Record<Locale, string> = {
  en: "I painted a little when I was younger. I want to restart watercolours and make a greeting card for my granddaughter. I can practise for 30 minutes, four days a week. I prefer Hindi instructions, larger text, seated alternatives, and learning at home with a small online group. I live in Pune.",
  hi: "मैंने युवावस्था में थोड़ी पेंटिंग की थी। अब मैं वॉटरकलर फिर शुरू करके अपनी नातिन के लिए शुभकामना कार्ड बनाना चाहती हूँ। मैं सप्ताह में चार दिन, 30 मिनट अभ्यास कर सकती हूँ। मुझे हिंदी में निर्देश, बड़ा टेक्स्ट, बैठकर करने के विकल्प और घर से छोटे ऑनलाइन समूह में सीखना पसंद है। मैं पुणे में रहती हूँ।",
};

export function createDeterministicTranscriptAdapter(): TranscriptAdapter {
  const providerName = "SakhiCircle deterministic local voice";
  const providerPolicy = "Local demo only. It uses a fixed synthetic transcript and receives, records, and stores no microphone audio.";

  return {
    providerName,
    providerPolicy,
    async capture(locale) {
      await Promise.resolve();
      return { transcript: deterministicSamples[locale], providerName, providerPolicy };
    },
  };
}

export function createBrowserTranscriptAdapter(speechWindow: Window = window): TranscriptAdapter {
  const providerName = "Browser speech recognition";
  const providerPolicy = "Your browser's speech service may process audio under its own terms. SakhiCircle receives only the transcript and never records or stores raw audio.";

  return {
    providerName,
    providerPolicy,
    async capture(locale) {
      const browser = speechWindow as SpeechWindow;
      const Recognition = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
      if (!Recognition) throw new TranscriptCaptureError("unsupported");

      return new Promise<TranscriptCapture>((resolve, reject) => {
        const recognition = new Recognition();
        let transcript = "";
        let settled = false;

        const fail = (reason: TranscriptCaptureFailure) => {
          if (settled) return;
          settled = true;
          reject(new TranscriptCaptureError(reason));
        };

        recognition.lang = locale === "hi" ? "hi-IN" : "en-IN";
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.onresult = (event) => {
          transcript = Array.from(event.results)
            .map((result) => result[0]?.transcript ?? "")
            .join(" ")
            .trim();
        };
        recognition.onerror = (event) => {
          if (event.error === "not-allowed" || event.error === "service-not-allowed") {
            fail("permission_denied");
            return;
          }
          fail(event.error === "no-speech" ? "no_speech" : "unavailable");
        };
        recognition.onend = () => {
          if (settled) return;
          if (!transcript) {
            fail("no_speech");
            return;
          }
          settled = true;
          resolve({ transcript, providerName, providerPolicy });
        };

        try {
          recognition.start();
        } catch {
          fail("unavailable");
        }
      });
    },
  };
}

export function createTranscriptAdapterForMode(
  mode: "deterministic" | "firebase_emulator" | "production",
): TranscriptAdapter {
  return mode === "deterministic"
    ? createDeterministicTranscriptAdapter()
    : createBrowserTranscriptAdapter();
}

export function extractLearningWish(transcript: string, locale: Locale): LearningWish {
  const normalized = transcript.toLocaleLowerCase(locale === "hi" ? "hi-IN" : "en-IN");
  const hindi = locale === "hi" || /[\u0900-\u097f]/.test(transcript);
  const watercolour = /watercolou?r|वॉटरकलर/.test(normalized);
  const painting = /\bpaint(?:ing)?\b|पेंटिंग/.test(normalized);
  const card = /greeting card|card|शुभकामना कार्ड|कार्ड/.test(normalized);
  const availabilityChoices = [
    { minutes: 15, days: 3, pattern: /(?:15|fifteen)\s*minutes?.*?(?:3|three)\s*days?|15 मिनट.*?(?:3|तीन) दिन/ },
    { minutes: 30, days: 4, pattern: /(?:30|thirty)\s*minutes?.*?(?:4|four)\s*days?|30 मिनट.*?(?:4|चार) दिन/ },
    { minutes: 45, days: 5, pattern: /(?:45|forty[- ]five)\s*minutes?.*?(?:5|five)\s*days?|45 मिनट.*?(?:5|पाँच) दिन/ },
  ];
  const hindiPlan = /hindi|हिंदी/.test(normalized);
  const largerText = /larger text|large text|बड़ा टेक्स्ट/.test(normalized);
  const seated = /seated|बैठकर/.test(normalized);
  const group = /online group|small group|ऑनलाइन समूह|छोटे ऑनलाइन समूह/.test(normalized);
  const pune = /pune|पुणे/.test(normalized);
  const restarting = /restart|younger|फिर शुरू|युवावस्था/.test(normalized);
  const genericHobby = !hindi
    ? transcript.match(/\b(?:want|would like|wish|hope) to (?:learn|begin|start|restart)\s+(.+?)(?=\s+(?:so (?:that )?i can|because|and (?:make|create|perform))\b|[.,!?]|$)/i)?.[1]?.trim()
    : "";
  const genericGoal = !hindi
    ? transcript.match(/\b(?:so (?:that )?i can|and (?:i want to )?)\s+([^.!?]+)/i)?.[1]?.trim()
    : "";
  const availabilityChoice = availabilityChoices.find(({ pattern }) => pattern.test(normalized));
  const titleCase = (value: string) => value
    ? `${value.charAt(0).toLocaleUpperCase()}${value.slice(1)}`.replace(/[\s.,!?]+$/, "")
    : "";

  return {
    hobby: watercolour
      ? (hindi ? "वॉटरकलर पेंटिंग" : "Watercolour painting")
      : painting ? (hindi ? "पेंटिंग" : "Painting") : titleCase(genericHobby ?? ""),
    experience: restarting
      ? (hindi ? "कई वर्षों बाद फिर शुरू कर रही हूँ" : "Restarting after many years")
      : "",
    goal: card ? (hindi ? "शुभकामना कार्ड बनाना" : "Paint a greeting card") : titleCase(genericGoal ?? ""),
    availability: availabilityChoice
      ? (hindi
          ? `${availabilityChoice.minutes} मिनट · सप्ताह में ${availabilityChoice.days} दिन`
          : `${availabilityChoice.minutes} minutes · ${availabilityChoice.days} days a week`)
      : "",
    language: hindiPlan ? (hindi ? "हिंदी" : "Hindi") : "",
    accessibility: largerText
      ? (hindi
          ? seated ? "बड़ा टेक्स्ट · बैठकर करने के विकल्प" : "बड़ा टेक्स्ट"
          : seated ? "Larger text · seated alternatives" : "Larger text")
      : "",
    format: group
      ? (hindi ? "घर पर · छोटा ऑनलाइन समूह" : "At home · small online group")
      : "",
    planConsent: false,
    matchingConsent: false,
    city: pune ? (hindi ? "पुणे" : "Pune") : "",
  };
}

export function createDeterministicProfileExtractionGateway(): ProfileExtractionGateway {
  return {
    providerName: "SakhiCircle private local suggestions",
    providerPolicy: "Your words stay on this device until you confirm your reviewed details.",
    async extract(transcript, locale) {
      return { source: "deterministic", fields: extractLearningWish(transcript, locale) };
    },
  };
}

interface ProfileExtractionApiGatewayOptions {
  apiBaseUrl: string;
  requestHeaders(): Promise<Record<string, string>>;
  fetcher?: typeof fetch;
}

export function createProfileExtractionApiGateway({
  apiBaseUrl,
  requestHeaders,
  fetcher = fetch,
}: ProfileExtractionApiGatewayOptions): ProfileExtractionGateway {
  return {
    providerName: "SakhiCircle AI suggestions",
    providerPolicy: "When you review, your words are processed once to suggest details and are not stored.",
    async extract(transcript, locale) {
      const response = await fetcher(`${apiBaseUrl.replace(/\/$/, "")}/api/v1/profile/extractions`, {
        method: "POST",
        headers: {
          ...(await requestHeaders()),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ transcript, locale }),
      });
      if (!response.ok) throw new Error(`Profile extraction failed with status ${response.status}.`);
      const result = await response.json() as Omit<ProfileExtractionResult, "fields"> & {
        fields: Omit<LearningWish, "planConsent" | "matchingConsent">;
      };
      return {
        ...result,
        fields: { ...result.fields, planConsent: false, matchingConsent: false },
      };
    },
  };
}

interface ProfileApiGatewayOptions {
  apiBaseUrl: string;
  requestHeaders(): Promise<Record<string, string>>;
  fetcher?: typeof fetch;
}

export function createProfileApiGateway({
  apiBaseUrl,
  requestHeaders,
  fetcher = fetch,
}: ProfileApiGatewayOptions): ProfileGateway {
  return {
    async save(profile) {
      const response = await fetcher(`${apiBaseUrl.replace(/\/$/, "")}/api/v1/profile`, {
        method: "PUT",
        headers: {
          ...(await requestHeaders()),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(profile),
      });

      if (!response.ok) {
        let code = "";
        try {
          const body = await response.json() as { detail?: { code?: string } };
          code = body.detail?.code ?? "";
        } catch {
          // A non-JSON error body is still handled by its HTTP status below.
        }
        if (code === "maintenance_mode") throw new ProfileSaveError("maintenance");
        if (response.status === 401) throw new ProfileSaveError("unauthorized");
        if (response.status === 403) throw new ProfileSaveError("security");
        throw new ProfileSaveError("unavailable");
      }
    },
  };
}
