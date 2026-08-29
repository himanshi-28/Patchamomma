import type { PropsWithChildren } from "react";
import { StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { tokens } from "@/theme/tokens";

export function AppFrame({ children }: PropsWithChildren) {
  return (
    <SafeAreaView edges={["top"]} style={styles.frame} testID="safe-area-shell">
      {children}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  frame: {
    backgroundColor: tokens.color.canvas,
    flex: 1,
  },
});
