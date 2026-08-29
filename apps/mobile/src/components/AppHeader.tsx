import { StyleSheet, Text, View } from "react-native";

import { Brand } from "@/components/Brand";
import { LanguageButton } from "@/components/LanguageButton";
import { useAppState } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

export function AppHeader() {
  const { session } = useAppState();
  const initial = session?.displayName.slice(0, 1).toUpperCase() ?? "M";

  return (
    <View style={styles.header}>
      <Brand compact />
      <View style={styles.actions}>
        <LanguageButton compact />
        <View accessibilityLabel={session?.displayName ?? "Meera"} style={styles.avatar}>
          <Text style={styles.initial}>{initial}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    alignItems: "center",
    borderBottomColor: tokens.color.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 60,
    paddingHorizontal: tokens.space.md,
  },
  actions: {
    alignItems: "center",
    flexDirection: "row",
    gap: tokens.space.xxs,
  },
  avatar: {
    alignItems: "center",
    backgroundColor: tokens.color.primary,
    borderRadius: 20,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  initial: {
    color: tokens.color.white,
    fontFamily: tokens.font.bold,
    fontSize: tokens.type.body,
  },
});
