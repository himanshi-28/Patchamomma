import { Redirect } from "expo-router";

import { SignInScreen } from "@/features/auth/SignInScreen";
import { useAppState } from "@/state/AppProvider";

export default function SignInRoute() {
  const { session } = useAppState();

  if (session) return <Redirect href="/(tabs)/today" />;
  return <SignInScreen />;
}
