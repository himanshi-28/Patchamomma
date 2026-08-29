import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Text } from "react-native";

import { SignInScreen } from "@/features/auth/SignInScreen";
import type { AuthGateway } from "@/features/auth/types";
import { AppProvider, useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

const unconfiguredGateway: AuthGateway = {
  sendEmailLink: jest.fn().mockRejectedValue(new Error("Email sign-in is not configured yet.")),
  signInWithGoogle: jest.fn().mockRejectedValue(new Error("Google sign-in is not configured yet.")),
  createDemoSession: jest.fn().mockResolvedValue({
    uid: "demo-meera",
    displayName: "Meera",
    roles: ["learner"],
    synthetic: true,
  }),
};

async function renderSignIn(demoMode = false) {
  function SessionProbe() {
    const { session } = useAppState();
    return <Text testID="signed-in-session">{session?.displayName}</Text>;
  }

  return await render(
    <AppProvider authGateway={unconfiguredGateway} demoMode={demoMode}>
      <SignInScreen />
      <SessionProbe />
    </AppProvider>,
  );
}

describe("native sign-in", () => {
  beforeEach(() => jest.clearAllMocks());

  it("keeps every sign-in action in one non-scrolling portrait screen", async () => {
    await renderSignIn();
    const source = readFileSync(join(__dirname, "../features/auth/SignInScreen.tsx"), "utf8");

    expect(source).not.toMatch(/\bScrollView\b/);
    expect(screen.getByRole("header", { name: "Welcome to SakhiCircle" })).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Send sign-in link" })).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeOnTheScreen();
    expect(screen.queryByRole("button", { name: "Continue as Meera" })).toBeNull();
  });

  it("uses a bounded large-text layout so 200% system text cannot push out sign-in actions", () => {
    const signInSource = readFileSync(join(__dirname, "../features/auth/SignInScreen.tsx"), "utf8");
    const buttonSource = readFileSync(join(__dirname, "../components/AppButton.tsx"), "utf8");

    expect(tokens.a11y.largeTextScale).toBeLessThanOrEqual(2);
    expect(tokens.a11y.maxFontMultiplier).toBeGreaterThanOrEqual(1.2);
    expect(signInSource).toContain("fontScale >= tokens.a11y.largeTextScale");
    expect(buttonSource).toContain("maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}");
  });

  it("switches the complete sign-in experience to Hindi", async () => {
    await renderSignIn();

    await fireEvent.press(screen.getByRole("button", { name: "हिंदी में देखें" }));

    expect(screen.getByRole("header", { name: "SakhiCircle में आपका स्वागत है" })).toBeOnTheScreen();
    expect(screen.getByLabelText("ईमेल पता")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "साइन-इन लिंक भेजें" })).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Google से जारी रखें" })).toBeOnTheScreen();
  });

  it("opens guided Sakhi help with three deterministic topics", async () => {
    await renderSignIn();

    await fireEvent.press(screen.getByRole("button", { name: "Hi, let me help you" }));

    const dialog = screen.getByLabelText("Sakhi help");
    expect(dialog.props.role).toBe("dialog");
    expect(dialog).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Signing in" })).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Finding a hobby" })).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Using voice" })).toBeOnTheScreen();

    await fireEvent.press(screen.getByRole("button", { name: "Signing in" }));
    expect(screen.getByText("Choose email, Google, or the local demo. You will never be asked for a password here.")).toBeOnTheScreen();
  });

  it("reports unconfigured authentication without pretending it succeeded", async () => {
    await renderSignIn();

    await fireEvent.press(screen.getByRole("button", { name: "Continue with Google" }));

    await waitFor(() => {
      expect(screen.getByText("Google sign-in is not configured yet.")).toBeOnTheScreen();
    });
  });

  it("only exposes the synthetic Meera session when demo mode is enabled", async () => {
    await renderSignIn(true);

    await fireEvent.press(screen.getByRole("button", { name: "Continue as Meera" }));

    await waitFor(() => {
      expect(screen.getByTestId("signed-in-session")).toHaveTextContent("Meera");
    });
  });
});
