import { Redirect, Tabs } from "expo-router";

import type { Destination } from "@/features/auth/types";
import { BottomTabBar } from "@/navigation/BottomTabBar";
import { useAppState } from "@/state/AppProvider";

export default function TabsLayout() {
  const { session } = useAppState();

  if (!session) return <Redirect href="/(auth)" />;

  return (
    <Tabs
      backBehavior="history"
      screenOptions={{ headerShown: false }}
      tabBar={({ navigation, state }) => (
        <BottomTabBar
          onSelect={(destination) => navigation.navigate(destination)}
          selected={state.routes[state.index].name as Destination}
        />
      )}
    >
      <Tabs.Screen name="today" />
      <Tabs.Screen name="circle" />
      <Tabs.Screen name="mentors" />
    </Tabs>
  );
}
