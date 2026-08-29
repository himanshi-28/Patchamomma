import { Languages } from "lucide-react-native";
import { Pressable, StyleSheet, Text } from "react-native";

import { copyByLocale } from "@/i18n/copy";
import { useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

type LanguageButtonProps = {
  compact?: boolean;
};

export function LanguageButton({ compact = false }: LanguageButtonProps) {
  const { locale, toggleLocale } = useAppState();
  const label = copyByLocale[locale].languageAction;
  const visibleLabel = compact ? (locale === "en" ? "हिंदी" : "EN") : label;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      onPress={toggleLocale}
      style={({ pressed }) => [styles.button, pressed && styles.pressed]}
    >
      <Languages color={tokens.color.primary} size={21} strokeWidth={2} />
      <Text
        maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
        numberOfLines={1}
        style={styles.label}
      >
        {visibleLabel}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    borderRadius: tokens.radius.sm,
    flexDirection: "row",
    gap: tokens.space.xs,
    minHeight: tokens.target.minimum,
    paddingHorizontal: tokens.space.xs,
  },
  pressed: {
    backgroundColor: tokens.color.surface,
  },
  label: {
    color: tokens.color.primary,
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.small,
  },
});
