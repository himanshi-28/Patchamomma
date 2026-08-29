import { BookOpen, GraduationCap, Users } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { Destination } from "@/features/auth/types";
import { copyByLocale } from "@/i18n/copy";
import { useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

export const TAB_DESTINATIONS: Destination[] = ["today", "circle", "mentors"];

type BottomTabBarProps = {
  selected: Destination;
  onSelect(destination: Destination): void;
};

const icons = {
  today: BookOpen,
  circle: Users,
  mentors: GraduationCap,
};

export function BottomTabBar({ selected, onSelect }: BottomTabBarProps) {
  const { locale } = useAppState();
  const copy = copyByLocale[locale];
  const labels: Record<Destination, string> = {
    today: copy.today,
    circle: copy.circle,
    mentors: copy.mentors,
  };

  return (
    <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
      <View accessibilityRole="tablist" style={styles.bar}>
        {TAB_DESTINATIONS.map((destination) => {
          const active = selected === destination;
          const Icon = icons[destination];
          return (
            <Pressable
              accessibilityLabel={labels[destination]}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              key={destination}
              onPress={() => onSelect(destination)}
              style={({ pressed }) => [
                styles.tab,
                active && styles.tabActive,
                pressed && styles.tabPressed,
              ]}
            >
              <Icon
                color={active ? tokens.color.primary : tokens.color.muted}
                size={23}
                strokeWidth={active ? 2.4 : 1.9}
              />
              <Text
                maxFontSizeMultiplier={tokens.a11y.maxFontMultiplier}
                numberOfLines={1}
                style={[styles.label, active && styles.labelActive]}
              >
                {labels[destination]}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: tokens.color.canvas,
    borderTopColor: tokens.color.border,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  bar: {
    flexDirection: "row",
    gap: tokens.space.xs,
    minHeight: 64,
    paddingHorizontal: tokens.space.sm,
    paddingTop: tokens.space.xs,
  },
  tab: {
    alignItems: "center",
    borderRadius: tokens.radius.md,
    flex: 1,
    justifyContent: "center",
    minHeight: tokens.target.minimum,
    paddingHorizontal: tokens.space.xxs,
  },
  tabActive: {
    backgroundColor: tokens.color.surface,
  },
  tabPressed: {
    backgroundColor: tokens.color.surfaceStrong,
  },
  label: {
    color: tokens.color.muted,
    fontFamily: tokens.font.medium,
    fontSize: 13,
    marginTop: 2,
  },
  labelActive: {
    color: tokens.color.primary,
    fontFamily: tokens.font.bold,
  },
});
