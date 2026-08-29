import { createContext, type PropsWithChildren, useContext, useMemo, useState } from "react";

import { unconfiguredAuthGateway } from "@/features/auth/authGateway";
import type { AuthGateway, Locale, Session } from "@/features/auth/types";

type AppState = {
  locale: Locale;
  session: Session | null;
  authGateway: AuthGateway;
  demoMode: boolean;
  setLocale(locale: Locale): void;
  toggleLocale(): void;
  setSession(session: Session | null): void;
};

type AppProviderProps = PropsWithChildren<{
  authGateway?: AuthGateway;
  demoMode?: boolean;
  initialLocale?: Locale;
  initialSession?: Session | null;
}>;

const AppStateContext = createContext<AppState | null>(null);

function developmentDemoMode() {
  return __DEV__ && process.env.EXPO_PUBLIC_DEMO_MODE !== "false";
}

export function AppProvider({
  children,
  authGateway = unconfiguredAuthGateway,
  demoMode = developmentDemoMode(),
  initialLocale = "en",
  initialSession = null,
}: AppProviderProps) {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [session, setSession] = useState<Session | null>(initialSession);

  const value = useMemo<AppState>(
    () => ({
      locale,
      session,
      authGateway,
      demoMode,
      setLocale,
      toggleLocale: () => setLocale((current) => (current === "en" ? "hi" : "en")),
      setSession,
    }),
    [authGateway, demoMode, locale, session],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error("useAppState must be used inside AppProvider");
  }
  return context;
}
