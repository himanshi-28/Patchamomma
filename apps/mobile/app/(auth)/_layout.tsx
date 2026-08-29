import { Stack } from "expo-router";

import { useReducedMotion } from "@/accessibility/useReducedMotion";
import { tokens } from "@/theme/tokens";

export default function AuthLayout() {
  const reducedMotion = useReducedMotion();

  return (
    <Stack
      screenOptions={{
        animation: reducedMotion ? "none" : "fade",
        animationDuration: reducedMotion ? 0 : tokens.motion.state,
        headerShown: false,
      }}
    />
  );
}
