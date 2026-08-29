import { Sparkles } from "lucide-react-native";
import { StyleSheet, Text, View } from "react-native";

import { tokens } from "@/theme/tokens";

type BrandProps = {
  compact?: boolean;
  inverse?: boolean;
};

export function Brand({ compact = false, inverse = false }: BrandProps) {
  const foreground = inverse ? tokens.color.white : tokens.color.ink;
  const markBackground = inverse ? tokens.color.white : tokens.color.primary;
  const markForeground = inverse ? tokens.color.primary : tokens.color.white;

  return (
    <View accessibilityLabel="SakhiCircle" style={styles.brand}>
      <View
        style={[
          styles.mark,
          compact && styles.markCompact,
          { backgroundColor: markBackground },
        ]}
      >
        <Sparkles color={markForeground} size={compact ? 20 : 24} strokeWidth={2.2} />
      </View>
      <Text
        maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
        numberOfLines={1}
        style={[styles.wordmark, compact && styles.wordmarkCompact, { color: foreground }]}
      >
        SakhiCircle
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  brand: {
    alignItems: "center",
    flexDirection: "row",
    gap: tokens.space.sm,
  },
  mark: {
    alignItems: "center",
    borderRadius: 22,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  markCompact: {
    borderRadius: 19,
    height: 38,
    width: 38,
  },
  wordmark: {
    fontFamily: tokens.font.bold,
    fontSize: 21,
  },
  wordmarkCompact: {
    fontSize: 19,
  },
});
