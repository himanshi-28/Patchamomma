import {
  NotoSansDevanagari_400Regular,
} from "@expo-google-fonts/noto-sans-devanagari/400Regular";
import {
  NotoSansDevanagari_500Medium,
} from "@expo-google-fonts/noto-sans-devanagari/500Medium";
import {
  NotoSansDevanagari_700Bold,
} from "@expo-google-fonts/noto-sans-devanagari/700Bold";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useReducedMotion } from "@/accessibility/useReducedMotion";
import { AppProvider } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

export default function RootLayout() {
  const reducedMotion = useReducedMotion();
  const [fontsLoaded, fontError] = useFonts({
    NotoSansDevanagari_400Regular,
    NotoSansDevanagari_500Medium,
    NotoSansDevanagari_700Bold,
  });

  if (!fontsLoaded && !fontError) return null;

  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            animation: reducedMotion ? "none" : "fade",
            animationDuration: reducedMotion ? 0 : tokens.motion.state,
            headerShown: false,
          }}
        >
          <Stack.Screen name="(auth)" />
          <Stack.Screen name="(tabs)" />
        </Stack>
      </AppProvider>
    </SafeAreaProvider>
  );
}
