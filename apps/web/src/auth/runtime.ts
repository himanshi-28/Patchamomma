export type AdapterMode = "deterministic" | "firebase_emulator" | "production";

export interface AuthSession {
  uid: string;
  displayName: string;
  synthetic: boolean;
}

export interface AuthGateway {
  observeSession(
    listener: (session: AuthSession | null) => void,
    onError?: (error: Error) => void,
  ): () => void;
  sendEmailLink(email: string): Promise<void>;
  signInWithGoogle(): Promise<void>;
  signInDemo(): Promise<void>;
  signOut(): Promise<void>;
  getIdToken(): Promise<string>;
  getAppCheckToken(): Promise<string | null>;
}

export interface AuthRuntimeEnvironment {
  VITE_ADAPTER_MODE?: AdapterMode;
  VITE_DEMO_MODE?: string;
  VITE_FIREBASE_API_KEY?: string;
  VITE_FIREBASE_AUTH_DOMAIN?: string;
  VITE_FIREBASE_PROJECT_ID?: string;
  VITE_FIREBASE_APP_ID?: string;
  VITE_FIREBASE_APP_CHECK_SITE_KEY?: string;
}

export interface AuthRuntimeConfig {
  adapterMode: AdapterMode;
  demoMode: boolean;
  firebase: {
    apiKey?: string;
    authDomain?: string;
    projectId?: string;
    appId?: string;
    appCheckSiteKey?: string;
  };
}

const PRODUCTION_ENVIRONMENT_FIELDS = [
  "VITE_FIREBASE_API_KEY",
  "VITE_FIREBASE_AUTH_DOMAIN",
  "VITE_FIREBASE_PROJECT_ID",
  "VITE_FIREBASE_APP_ID",
  "VITE_FIREBASE_APP_CHECK_SITE_KEY",
] as const;

export const SESSION_STORAGE_KEYS = [
  "sakhicircle-email-for-sign-in",
  "sakhicircle-onboarding-draft",
  "sakhicircle-user-query-state",
  "sakhicircle-confirmed-journey-cache",
] as const;

export class SessionCleanupError extends Error {
  constructor() {
    super("Signed out, but local user data cleanup did not finish.");
    this.name = "SessionCleanupError";
  }
}

export function resolveAuthRuntimeConfig(
  environment: AuthRuntimeEnvironment,
): AuthRuntimeConfig {
  const adapterMode = environment.VITE_ADAPTER_MODE ?? "deterministic";
  const demoMode = environment.VITE_DEMO_MODE === "true";

  if (adapterMode === "production" && demoMode) {
    throw new Error("Demo mode cannot be enabled in production.");
  }

  if (adapterMode === "production") {
    const missing = PRODUCTION_ENVIRONMENT_FIELDS.filter((field) => !environment[field]);
    if (missing.length > 0) {
      throw new Error(`Firebase production configuration is missing: ${missing.join(", ")}`);
    }
  }

  return {
    adapterMode,
    demoMode,
    firebase: {
      apiKey: environment.VITE_FIREBASE_API_KEY,
      authDomain: environment.VITE_FIREBASE_AUTH_DOMAIN,
      projectId: environment.VITE_FIREBASE_PROJECT_ID,
      appId: environment.VITE_FIREBASE_APP_ID,
      appCheckSiteKey: environment.VITE_FIREBASE_APP_CHECK_SITE_KEY,
    },
  };
}

export function clearUserSessionState(): void {
  let cleanupFailed = false;
  for (const key of SESSION_STORAGE_KEYS) {
    for (const storage of [window.localStorage, window.sessionStorage]) {
      try {
        storage.removeItem(key);
      } catch {
        cleanupFailed = true;
      }
    }
  }
  if (cleanupFailed) throw new SessionCleanupError();
}

export function createDeterministicAuthGateway({ demoMode }: { demoMode: boolean }): AuthGateway {
  let currentSession: AuthSession | null = null;
  const listeners = new Set<(session: AuthSession | null) => void>();
  const notify = () => listeners.forEach((listener) => listener(currentSession));
  const unavailable = () => Promise.reject(new Error("Firebase sign-in is not configured."));

  return {
    observeSession(listener) {
      listeners.add(listener);
      listener(currentSession);
      return () => listeners.delete(listener);
    },
    sendEmailLink: unavailable,
    signInWithGoogle: unavailable,
    async signInDemo() {
      if (!demoMode) throw new Error("Demo access is disabled.");
      currentSession = {
        uid: "demo-meera",
        displayName: "Meera Sharma",
        synthetic: true,
      };
      notify();
    },
    async signOut() {
      currentSession = null;
      try {
        clearUserSessionState();
      } finally {
        notify();
      }
    },
    async getIdToken() {
      if (!currentSession || !demoMode) throw new Error("Authentication required.");
      return "demo-learner-token";
    },
    async getAppCheckToken() {
      return null;
    },
  };
}

export function createUnavailableAuthGateway(configurationError: Error): AuthGateway {
  const unavailable = () => Promise.reject(configurationError);
  return {
    observeSession(listener, onError) {
      listener(null);
      onError?.(configurationError);
      return () => undefined;
    },
    sendEmailLink: unavailable,
    signInWithGoogle: unavailable,
    signInDemo: unavailable,
    signOut: unavailable,
    getIdToken: unavailable,
    getAppCheckToken: unavailable,
  };
}

export async function protectedRequestHeaders(
  tokenSource: Pick<AuthGateway, "getIdToken" | "getAppCheckToken">,
  adapterMode: AdapterMode,
): Promise<Record<string, string>> {
  const idToken = await tokenSource.getIdToken();
  const headers: Record<string, string> = { Authorization: `Bearer ${idToken}` };

  if (adapterMode === "production") {
    const appCheckToken = await tokenSource.getAppCheckToken();
    if (!appCheckToken) {
      throw new Error("Firebase App Check is not configured for this production request.");
    }
    headers["X-Firebase-AppCheck"] = appCheckToken;
  }

  return headers;
}
