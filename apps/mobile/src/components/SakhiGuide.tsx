import { CircleHelp, X } from "lucide-react-native";
import { useState } from "react";
import {
  Image,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useReducedMotion } from "@/accessibility/useReducedMotion";
import { copyByLocale } from "@/i18n/copy";
import { useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

type SakhiGuideProps = {
  compact?: boolean;
};

export function SakhiGuide({ compact = false }: SakhiGuideProps) {
  const reducedMotion = useReducedMotion();
  const { locale } = useAppState();
  const copy = copyByLocale[locale];
  const [open, setOpen] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);

  function closeGuide() {
    setOpen(false);
    setAnswer(null);
  }

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={copy.helpTrigger}
        onPress={() => setOpen(true)}
        style={({ pressed }) => [
          styles.trigger,
          compact && styles.triggerCompact,
          pressed && styles.triggerPressed,
        ]}
      >
        <View style={[styles.avatar, compact && styles.avatarCompact]}>
          <Image
            accessibilityIgnoresInvertColors
            resizeMode="contain"
            source={require("../../assets/images/sakhi-guide.png")}
            style={[styles.image, compact && styles.imageCompact]}
          />
        </View>
        <View style={styles.triggerCopy}>
          <Text
            maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
            numberOfLines={1}
            style={styles.triggerTitle}
          >
            {copy.helpTrigger}
          </Text>
          {!compact && (
            <Text
              maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
              numberOfLines={2}
              style={styles.triggerNote}
            >
              {locale === "en" ? "Ask about signing in, hobbies, or voice." : "साइन इन, शौक या आवाज़ के बारे में पूछें।"}
            </Text>
          )}
        </View>
        <CircleHelp color={tokens.color.primary} size={22} strokeWidth={2} />
      </Pressable>

      <Modal
        animationType={reducedMotion ? "none" : "fade"}
        onRequestClose={closeGuide}
        transparent
        visible={open}
      >
        <View style={styles.scrim}>
          <View
            accessibilityLabel={copy.helpTitle}
            accessibilityViewIsModal
            role="dialog"
            style={styles.dialog}
          >
            <View style={styles.dialogHeader}>
              <View style={styles.dialogTitleRow}>
                <View style={styles.dialogAvatar}>
                  <Image
                    accessibilityIgnoresInvertColors
                    resizeMode="contain"
                    source={require("../../assets/images/sakhi-guide.png")}
                    style={styles.dialogImage}
                  />
                </View>
                <View style={styles.dialogTitleCopy}>
                  <Text accessibilityRole="header" maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.dialogTitle}>{copy.helpTitle}</Text>
                  <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.dialogSubtitle}>{copy.helpTrigger}</Text>
                </View>
              </View>
              <Pressable
                accessibilityLabel={copy.close}
                accessibilityRole="button"
                hitSlop={8}
                onPress={closeGuide}
                style={({ pressed }) => [styles.close, pressed && styles.triggerPressed]}
              >
                <X color={tokens.color.ink} size={24} />
              </Pressable>
            </View>

            <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.prompt}>
              {locale === "en" ? "What would you like help with?" : "आप किस बारे में मदद चाहती हैं?"}
            </Text>

            <View style={styles.topics}>
              {copy.helpTopics.map((topic, index) => (
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={topic}
                  key={topic}
                  onPress={() => setAnswer(copy.helpReplies[index])}
                  style={({ pressed }) => [styles.topic, pressed && styles.topicPressed]}
                >
                  <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.topicText}>{topic}</Text>
                </Pressable>
              ))}
            </View>

            {answer && (
              <View accessibilityLiveRegion="polite" style={styles.answer}>
                <Text maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier} style={styles.answerText}>{answer}</Text>
              </View>
            )}
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  trigger: {
    alignItems: "center",
    backgroundColor: tokens.color.surface,
    borderRadius: tokens.radius.lg,
    flexDirection: "row",
    gap: tokens.space.sm,
    minHeight: 76,
    overflow: "hidden",
    paddingHorizontal: tokens.space.sm,
  },
  triggerCompact: {
    minHeight: tokens.target.minimum,
  },
  triggerPressed: {
    backgroundColor: tokens.color.surfaceStrong,
  },
  avatar: {
    alignSelf: "stretch",
    overflow: "hidden",
    width: 56,
  },
  avatarCompact: {
    width: 38,
  },
  image: {
    bottom: -34,
    height: 112,
    left: -7,
    position: "absolute",
    width: 70,
  },
  imageCompact: {
    bottom: -22,
    height: 76,
    left: -5,
    width: 48,
  },
  triggerCopy: {
    flex: 1,
  },
  triggerTitle: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: 17,
  },
  triggerNote: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: 14,
    lineHeight: 19,
    marginTop: 2,
  },
  scrim: {
    alignItems: "center",
    backgroundColor: tokens.color.scrim,
    flex: 1,
    justifyContent: "center",
    padding: tokens.space.md,
  },
  dialog: {
    backgroundColor: tokens.color.canvas,
    borderRadius: tokens.radius.lg,
    maxWidth: 460,
    padding: tokens.space.lg,
    width: "100%",
  },
  dialogHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  dialogTitleRow: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: tokens.space.sm,
  },
  dialogAvatar: {
    backgroundColor: tokens.color.surface,
    borderRadius: 28,
    height: 56,
    overflow: "hidden",
    width: 56,
  },
  dialogImage: {
    height: 90,
    left: 1,
    position: "absolute",
    top: 2,
    width: 54,
  },
  dialogTitleCopy: {
    flex: 1,
  },
  dialogTitle: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: 22,
  },
  dialogSubtitle: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: 15,
  },
  close: {
    alignItems: "center",
    borderRadius: tokens.radius.sm,
    height: tokens.target.minimum,
    justifyContent: "center",
    width: tokens.target.minimum,
  },
  prompt: {
    color: tokens.color.ink,
    fontFamily: tokens.font.regular,
    fontSize: tokens.type.body,
    marginTop: tokens.space.lg,
  },
  topics: {
    gap: tokens.space.xs,
    marginTop: tokens.space.sm,
  },
  topic: {
    borderColor: tokens.color.border,
    borderRadius: tokens.radius.sm,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: tokens.target.minimum,
    paddingHorizontal: tokens.space.md,
  },
  topicPressed: {
    backgroundColor: tokens.color.surface,
  },
  topicText: {
    color: tokens.color.primary,
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.body,
  },
  answer: {
    backgroundColor: tokens.color.surface,
    borderRadius: tokens.radius.md,
    marginTop: tokens.space.md,
    padding: tokens.space.md,
  },
  answerText: {
    color: tokens.color.ink,
    fontFamily: tokens.font.regular,
    fontSize: 17,
    lineHeight: 25,
  },
});
