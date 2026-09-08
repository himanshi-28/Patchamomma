import type { FirebaseApp } from "firebase/app";
import type { AppCheck } from "firebase/app-check";
import type { Auth } from "firebase/auth";
import {
  clearUserSessionState,
  type AuthGateway,
  type AuthRuntimeConfig,
} from "./runtime";

interface FirebaseResources {
  app: FirebaseApp;
  auth: Auth;
  appCheck: AppCheck | null;
}

interface GoogleSignInStrategy {
  popup(): Promise<unknown>;
  redirect(): Promise<unknown>;
  popupTimeoutMs?: number;
  preferRedirect?: boolean;
}

const REDIRECTABLE_POPUP_ERRORS = new Set([
  "auth/popup-blocked",
  "auth/operation-not-supported-in-this-environment",
  "auth/web-storage-unsupported",
]);

export async function signInWithPopupOrRedirect({
  popup,
  redirect,
  popupTimeoutMs = 12_000,
  preferRedirect = false,
}: GoogleSignInStrategy): Promise<void> {
  if (preferRedirect) {
    await redirect();
    return;
  }

  let timeout: ReturnType<typeof setTimeout> | undefined;
  const stalled = new Promise<"stalled">((resolve) => {
    timeout = setTimeout(() => resolve("stalled"), popupTimeoutMs);
  });

  try {
    const result = await Promise.race([
      popup().then(() => "complete" as const),
      stalled,
    ]);
    if (result === "stalled") await redirect();
  } catch (error) {
    const code = typeof error === "object" && error !== null && "code" in error
      ? String(error.code)
      : "";
    if (!REDIRECTABLE_POPUP_ERRORS.has(code)) throw error;
    await redirect();
  } finally {
    if (timeout !== undefined) clearTimeout(timeout);
  }
}

export function createFirebaseAuthGateway(config: AuthRuntimeConfig): AuthGateway {
  let resourcesPromise: Promise<FirebaseResources> | null = null;

  const configuredResources = (): Promise<FirebaseResources> => {
    if (resourcesPromise) return resourcesPromise;

    resourcesPromise = (async () => {
      const missing = Object.entries({
        apiKey: config.firebase.apiKey,
        authDomain: config.firebase.authDomain,
        projectId: config.firebase.projectId,
        appId: config.firebase.appId,
      })
        .filter(([, value]) => !value)
        .map(([key]) => key);

      if (missing.length > 0) {
        throw new Error(`Firebase sign-in is not configured: ${missing.join(", ")}`);
      }

      const [{ getApps, initializeApp }, { getAuth }] = await Promise.all([
        import("firebase/app"),
        import("firebase/auth"),
      ]);
      const app = getApps()[0] ?? initializeApp({
        apiKey: config.firebase.apiKey,
        authDomain: config.firebase.authDomain,
        projectId: config.firebase.projectId,
        appId: config.firebase.appId,
      });
      const auth = getAuth(app);
      let appCheck: AppCheck | null = null;

      if (config.adapterMode === "production") {
        if (!config.firebase.appCheckSiteKey) {
          throw new Error("Firebase App Check is not configured: appCheckSiteKey");
        }
        const { initializeAppCheck, ReCaptchaEnterpriseProvider } = await import("firebase/app-check");
        appCheck = initializeAppCheck(app, {
          provider: new ReCaptchaEnterpriseProvider(config.firebase.appCheckSiteKey),
          isTokenAutoRefreshEnabled: true,
        });
      }

      return { app, auth, appCheck };
    })();

    return resourcesPromise;
  };

  return {
    observeSession(listener, onError) {
      let active = true;
      let unsubscribe: () => void = () => undefined;

      void configuredResources()
        .then(async ({ auth }) => {
          const { getRedirectResult, isSignInWithEmailLink, onAuthStateChanged, signInWithEmailLink } = await import("firebase/auth");
          if (!active) return;
          unsubscribe = onAuthStateChanged(
            auth,
            (user) => listener(user ? {
              uid: user.uid,
              displayName: user.displayName || "SakhiCircle member",
              synthetic: false,
            } : null),
            (error) => onError?.(error),
          );
          if (isSignInWithEmailLink(auth, window.location.href)) {
            const pendingEmail = window.localStorage.getItem("sakhicircle-email-for-sign-in");
            if (!pendingEmail) {
              throw new Error("Enter the same email address to finish sign-in.");
            }
            try {
              await signInWithEmailLink(auth, pendingEmail, window.location.href);
            } finally {
              window.localStorage.removeItem("sakhicircle-email-for-sign-in");
            }
          }
          await getRedirectResult(auth);
        })
        .catch((error: unknown) => onError?.(
          error instanceof Error ? error : new Error("Firebase sign-in failed."),
        ));

      return () => {
        active = false;
        unsubscribe();
      };
    },
    async sendEmailLink(email) {
      const { auth } = await configuredResources();
      const { sendSignInLinkToEmail } = await import("firebase/auth");
      await sendSignInLinkToEmail(auth, email, {
        url: window.location.origin,
        handleCodeInApp: true,
      });
      window.localStorage.setItem("sakhicircle-email-for-sign-in", email);
    },
    async signInWithGoogle() {
      const { auth } = await configuredResources();
      const { GoogleAuthProvider, signInWithPopup, signInWithRedirect } = await import("firebase/auth");
      const provider = new GoogleAuthProvider();
      await signInWithPopupOrRedirect({
        popup: () => signInWithPopup(auth, provider),
        redirect: () => signInWithRedirect(auth, provider),
        preferRedirect: config.adapterMode === "production",
      });
    },
    async signInDemo() {
      throw new Error("Demo access is unavailable with Firebase authentication.");
    },
    async signOut() {
      const { auth } = await configuredResources();
      const { signOut } = await import("firebase/auth");
      await signOut(auth);
      clearUserSessionState();
    },
    async getIdToken() {
      const { auth } = await configuredResources();
      if (!auth.currentUser) throw new Error("Authentication required.");
      return auth.currentUser.getIdToken();
    },
    async getAppCheckToken() {
      const { appCheck } = await configuredResources();
      if (!appCheck) return null;
      const { getToken } = await import("firebase/app-check");
      return (await getToken(appCheck)).token;
    },
  };
}
