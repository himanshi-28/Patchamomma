import { GraduationCap, Users } from "lucide-react-native";
import { StyleSheet, Text, View } from "react-native";

import { AppFrame } from "@/components/AppFrame";
import { AppHeader } from "@/components/AppHeader";
import type { Destination } from "@/features/auth/types";
import { copyByLocale } from "@/i18n/copy";
import { useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

type EmptyDestinationScreenProps = {
  destination: Exclude<Destination, "today">;
};

export function EmptyDestinationScreen({ destination }: EmptyDestinationScreenProps) {
  const { locale } = useAppState();
  const copy = copyByLocale[locale].empty[destination];
  const Icon = destination === "circle" ? Users : GraduationCap;

  return (
    <AppFrame>
      <AppHeader />
      <View style={styles.content}>
        <View style={styles.iconWrap}>
          <Icon color={tokens.color.primary} size={38} strokeWidth={1.8} />
        </View>
        <Text accessibilityRole="header" style={styles.title}>{copy.title}</Text>
        <Text style={styles.message}>{copy.message}</Text>
        <Text style={styles.note}>{copy.note}</Text>
      </View>
    </AppFrame>
  );
}

const styles = StyleSheet.create({
  content: {
    alignItems: "center",
    alignSelf: "center",
    flex: 1,
    justifyContent: "center",
    maxWidth: 480,
    padding: tokens.space.lg,
    width: "100%",
  },
  iconWrap: {
    alignItems: "center",
    backgroundColor: tokens.color.surface,
    borderRadius: tokens.radius.lg,
    height: 72,
    justifyContent: "center",
    marginBottom: tokens.space.lg,
    width: 72,
  },
  title: {
    color: tokens.color.primary,
    fontFamily: tokens.font.bold,
    fontSize: 18,
  },
  message: {
    color: tokens.color.ink,
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.title,
    lineHeight: 38,
    marginTop: tokens.space.xs,
    textAlign: "center",
  },
  note: {
    color: tokens.color.muted,
    fontFamily: tokens.font.regular,
    fontSize: tokens.type.body,
    lineHeight: 28,
    marginTop: tokens.space.sm,
    textAlign: "center",
  },
});
