import { Mail } from "lucide-react-native";
import { useEffect, useMemo, useState } from "react";
import {
  Keyboard,
  KeyboardAvoidingView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";

import { AppButton } from "@/components/AppButton";
import { AppFrame } from "@/components/AppFrame";
import { Brand } from "@/components/Brand";
import { LanguageButton } from "@/components/LanguageButton";
import { SakhiGuide } from "@/components/SakhiGuide";
import { copyByLocale } from "@/i18n/copy";
import { useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

type SignInScreenProps = {
  onSignedIn?: () => void;
};

type PendingAction = "email" | "google" | "demo" | null;

export function SignInScreen({ onSignedIn }: SignInScreenProps) {
  const { authGateway, demoMode, locale, setSession } = useAppState();
  const copy = copyByLocale[locale];
  const { fontScale, height } = useWindowDimensions();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction>(null);
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  const largeText = fontScale >= tokens.a11y.largeTextScale;
  const compact = keyboardOpen || height < 700 || largeText;

  useEffect(() => {
    const show = Keyboard.addListener("keyboardDidShow", () => setKeyboardOpen(true));
    const hide = Keyboard.addListener("keyboardDidHide", () => setKeyboardOpen(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  const validEmail = useMemo(() => /^\S+@\S+\.\S+$/.test(email.trim()), [email]);

  async function sendEmailLink() {
    setMessage(null);
    if (!validEmail) {
      setMessage(copy.invalidEmail);
      return;
    }
    setPending("email");
    try {
      await authGateway.sendEmailLink(email.trim());
    } catch {
      setMessage(copy.emailSetup);
    } finally {
      setPending(null);
    }
  }

  async function signInWithGoogle() {
    setMessage(null);
    setPending("google");
    try {
      const nextSession = await authGateway.signInWithGoogle();
      setSession(nextSession);
      onSignedIn?.();
    } catch {
      setMessage(copy.googleSetup);
    } finally {
      setPending(null);
    }
  }

  async function continueAsMeera() {
    if (!demoMode) return;
    setMessage(null);
    setPending("demo");
    try {
      const nextSession = await authGateway.createDemoSession();
      setSession(nextSession);
      onSignedIn?.();
    } catch {
      setMessage(locale === "en" ? "The local demo could not start." : "स्थानीय डेमो शुरू नहीं हो सका।");
    } finally {
      setPending(null);
    }
  }

  return (
    <AppFrame>
      <KeyboardAvoidingView
        behavior="height"
        style={styles.keyboardView}
      >
        <View style={styles.header}>
          <Brand compact />
          <LanguageButton compact={largeText} />
        </View>

        <View style={[styles.content, compact && styles.contentCompact]}>
          <View style={styles.welcomeBlock}>
            <Text
              accessibilityRole="header"
              maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
              style={[styles.title, compact && styles.titleCompact]}
            >
              {copy.welcome}
            </Text>
            {!compact && (
              <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.subtitle}>
                {copy.welcomeNote}
              </Text>
            )}
          </View>

          <SakhiGuide compact={compact} />

          <View style={styles.form}>
            <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.label}>
              {copy.emailLabel}
            </Text>
            <View style={styles.field}>
              <Mail color={tokens.color.muted} size={22} strokeWidth={2} />
              <TextInput
                accessibilityLabel={copy.emailLabel}
                autoCapitalize="none"
                autoComplete="email"
                autoCorrect={false}
                inputMode="email"
                keyboardType="email-address"
                maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
                onChangeText={setEmail}
                onSubmitEditing={sendEmailLink}
                placeholder={copy.emailPlaceholder}
                placeholderTextColor={tokens.color.muted}
                returnKeyType="send"
                style={styles.input}
                value={email}
              />
            </View>
            {message && (
              <Text
                accessibilityLiveRegion="polite"
                maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
                style={styles.message}
              >
                {message}
              </Text>
            )}
            <AppButton
              busy={pending === "email"}
              disabled={pending !== null && pending !== "email"}
              label={copy.emailAction}
              onPress={sendEmailLink}
              testID="email-sign-in"
            />
          </View>

          {!keyboardOpen && (
            <>
              {!largeText && (
                <View style={styles.divider}>
                  <View style={styles.rule} />
                  <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.or}>
                    {copy.or}
                  </Text>
                  <View style={styles.rule} />
                </View>
              )}

              <AppButton
                busy={pending === "google"}
                disabled={pending !== null && pending !== "google"}
                icon={<Text style={styles.googleMark}>G</Text>}
                label={copy.googleAction}
                onPress={signInWithGoogle}
                variant="outline"
              />

              {demoMode && (
                <View style={[styles.demo, largeText && styles.demoLargeText]}>
                  {!largeText && (
                    <View style={styles.demoCopy}>
                      <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.demoTitle}>
                        {copy.demoLabel}
                      </Text>
                      {!compact && (
                        <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.demoNote}>
                          {copy.demoNote}
                        </Text>
                      )}
                    </View>
                  )}
                  <AppButton
                    busy={pending === "demo"}
                    disabled={pending !== null && pending !== "demo"}
                    label={copy.demoAction}
                    onPress={continueAsMeera}
                    style={largeText ? styles.demoButtonLargeText : styles.demoButton}
                  />
                </View>
              )}
            </>
          )}
        </View>
      </KeyboardAvoidingView>
    </AppFrame>
  );
}

const styles = StyleSheet.create({
  keyboardView: {
    flex: 1,
  },
  header: {
    alignItems: "center",
    borderBottomColor: tokens.color.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 60,
    paddingHorizontal: tokens.space.md,
  },
  content: {
    alignSelf: "center",
    flex: 1,
    gap: tokens.space.sm,
    justifyContent: "center",
    maxWidth: 480,
    paddingHorizontal: tokens.space.md,
    paddingVertical: tokens.space.sm,
    width: "100%",
  },
  contentCompact: {
    gap: tokens.space.xs,
    justifyContent: "flex-start",
    paddingTop: tokens.space.sm,
  },
  welcomeBlock: {
    gap: tokens.space.xxs,
  },
  title: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.title,
    lineHeight: 38,
  },
  titleCompact: {
    fontSize: 24,
    lineHeight: 32,
  },
  subtitle: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: 16,
    lineHeight: 23,
  },
  form: {
    gap: tokens.space.xs,
  },
  label: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: 16,
  },
  field: {
    alignItems: "center",
    backgroundColor: tokens.color.canvas,
    borderColor: tokens.color.border,
    borderRadius: tokens.radius.sm,
    borderWidth: 2,
    flexDirection: "row",
    minHeight: tokens.target.primary,
    paddingHorizontal: tokens.space.sm,
  },
  input: {
    color: tokens.color.ink,
    flex: 1,
    fontFamily: tokens.font.regular,
    fontSize: tokens.type.body,
    minHeight: tokens.target.minimum,
    paddingHorizontal: tokens.space.sm,
    paddingVertical: 0,
  },
  message: {
    color: tokens.color.error,
    fontFamily: tokens.font.medium,
    fontSize: 15,
    lineHeight: 20,
  },
  divider: {
    alignItems: "center",
    flexDirection: "row",
    gap: tokens.space.sm,
    minHeight: 24,
  },
  rule: {
    backgroundColor: tokens.color.border,
    flex: 1,
    height: 1,
  },
  or: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: 15,
  },
  googleMark: {
    color: "#1A73E8",
    fontFamily: tokens.font.bold,
    fontSize: 20,
  },
  demo: {
    alignItems: "center",
    backgroundColor: tokens.color.surface,
    borderRadius: tokens.radius.md,
    flexDirection: "row",
    gap: tokens.space.sm,
    padding: tokens.space.xs,
    paddingLeft: tokens.space.sm,
  },
  demoCopy: {
    flex: 1,
  },
  demoTitle: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: 15,
  },
  demoNote: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: 13,
    lineHeight: 17,
  },
  demoButton: {
    minHeight: tokens.target.minimum,
    paddingHorizontal: tokens.space.sm,
  },
  demoButtonLargeText: {
    width: "100%",
  },
  demoLargeText: {
    backgroundColor: tokens.color.canvas,
    padding: 0,
  },
});
