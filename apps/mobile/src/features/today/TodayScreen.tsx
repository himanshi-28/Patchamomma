import { Sparkles } from "lucide-react-native";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { AppButton } from "@/components/AppButton";
import { AppFrame } from "@/components/AppFrame";
import { AppHeader } from "@/components/AppHeader";
import { SakhiGuide } from "@/components/SakhiGuide";
import { copyByLocale } from "@/i18n/copy";
import { useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

export function TodayScreen() {
  const { locale } = useAppState();
  const copy = copyByLocale[locale];

  return (
    <AppFrame>
      <AppHeader />
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.greetingRow}>
          <Text accessibilityRole="header" style={styles.greeting}>{copy.greeting}</Text>
        </View>

        <View style={styles.hero}>
          <Text style={styles.eyebrow}>{copy.nextStep}</Text>
          <Text style={styles.heroTitle}>{copy.nextChapter}</Text>
          <Text style={styles.heroDescription}>{copy.nextDescription}</Text>
          <AppButton
            icon={<Sparkles color={tokens.color.white} size={22} strokeWidth={2.2} />}
            label={copy.chooseHobby}
            onPress={() => undefined}
            style={styles.heroButton}
          />
        </View>

        <SakhiGuide />

        <View style={styles.sectionHeading} testID="today-section-heading">
          <Text style={styles.sectionTitle}>{copy.howItWorks}</Text>
          <Text style={styles.sectionLink}>{copy.howLink}</Text>
        </View>

        <View style={styles.steps}>
          {copy.steps.map((step, index) => (
            <View key={step.title} style={[styles.step, index > 0 && styles.stepBorder]}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>{index + 1}</Text>
              </View>
              <View style={styles.stepCopy}>
                <Text style={styles.stepTitle}>{step.title}</Text>
                <Text style={styles.stepDescription}>{step.description}</Text>
              </View>
            </View>
          ))}
        </View>
      </ScrollView>
    </AppFrame>
  );
}

const styles = StyleSheet.create({
  content: {
    alignSelf: "center",
    gap: tokens.space.md,
    maxWidth: 720,
    padding: tokens.space.md,
    paddingBottom: tokens.space.xl,
    width: "100%",
  },
  greetingRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  greeting: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: 24,
    lineHeight: 33,
  },
  hero: {
    backgroundColor: tokens.color.surface,
    borderRadius: tokens.radius.lg,
    gap: tokens.space.sm,
    padding: tokens.space.lg,
  },
  eyebrow: {
    color: tokens.color.primary,
    fontFamily: tokens.font.bold,
    fontSize: 16,
  },
  heroTitle: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.display,
    letterSpacing: -0.8,
    lineHeight: 44,
  },
  heroDescription: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: tokens.type.body,
    lineHeight: 28,
  },
  heroButton: {
    alignSelf: "stretch",
    marginTop: tokens.space.xxs,
  },
  sectionHeading: {
    alignItems: "flex-start",
    flexDirection: "column",
    gap: tokens.space.xxs,
  },
  sectionTitle: {
    color: tokens.color.ink,
    flex: 1,
    fontFamily: tokens.font.bold,
    fontSize: 22,
  },
  sectionLink: {
    color: tokens.color.primary,
    fontFamily: tokens.font.bold,
    fontSize: 15,
    textDecorationLine: "underline",
  },
  steps: {
    borderBottomColor: tokens.color.border,
    borderBottomWidth: 1,
    borderTopColor: tokens.color.border,
    borderTopWidth: 1,
  },
  step: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: tokens.space.sm,
    paddingVertical: tokens.space.md,
  },
  stepBorder: {
    borderTopColor: tokens.color.border,
    borderTopWidth: 1,
  },
  stepNumber: {
    alignItems: "center",
    backgroundColor: tokens.color.primary,
    borderRadius: 18,
    height: 36,
    justifyContent: "center",
    width: 36,
  },
  stepNumberText: {
    color: tokens.color.white,
    fontFamily: tokens.font.bold,
    fontSize: 17,
  },
  stepCopy: {
    flex: 1,
  },
  stepTitle: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.body,
  },
  stepDescription: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: 16,
    lineHeight: 23,
    marginTop: tokens.space.xxs,
  },
});
