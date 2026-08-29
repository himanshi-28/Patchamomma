import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type ViewStyle,
} from "react-native";

import { tokens } from "@/theme/tokens";

type AppButtonProps = {
  label: string;
  onPress(): void;
  variant?: "primary" | "outline" | "quiet";
  disabled?: boolean;
  busy?: boolean;
  icon?: ReactNode;
  testID?: string;
  style?: ViewStyle;
};

export function AppButton({
  label,
  onPress,
  variant = "primary",
  disabled = false,
  busy = false,
  icon,
  testID,
  style,
}: AppButtonProps) {
  const isDisabled = disabled || busy;
  const foreground = variant === "primary" ? tokens.color.white : tokens.color.ink;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: isDisabled, busy }}
      disabled={isDisabled}
      onPress={onPress}
      testID={testID}
      style={({ pressed }) => [
        styles.base,
        variant === "primary" && styles.primary,
        variant === "outline" && styles.outline,
        variant === "quiet" && styles.quiet,
        pressed && variant === "primary" && styles.primaryPressed,
        pressed && variant !== "primary" && styles.secondaryPressed,
        isDisabled && styles.disabled,
        style,
      ]}
    >
      {busy ? <ActivityIndicator color={foreground} /> : icon}
      <Text
        maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
        numberOfLines={1}
        style={[styles.label, { color: foreground }]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: "center",
    borderRadius: tokens.radius.sm,
    flexDirection: "row",
    gap: tokens.space.sm,
    justifyContent: "center",
    minHeight: tokens.target.primary,
    paddingHorizontal: tokens.space.md,
  },
  primary: {
    backgroundColor: tokens.color.primary,
  },
  primaryPressed: {
    backgroundColor: tokens.color.primaryPressed,
  },
  outline: {
    backgroundColor: tokens.color.canvas,
    borderColor: tokens.color.ink,
    borderWidth: 2,
  },
  quiet: {
    backgroundColor: tokens.color.surface,
  },
  secondaryPressed: {
    backgroundColor: tokens.color.surfaceStrong,
  },
  disabled: {
    opacity: 0.55,
  },
  label: {
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.body,
    lineHeight: 25,
    textAlign: "center",
  },
});
