import { fireEvent, render, screen } from "@testing-library/react-native";

import appConfig from "../../app.json";
import { AppFrame } from "@/components/AppFrame";
import { AppHeader } from "@/components/AppHeader";
import { BottomTabBar, TAB_DESTINATIONS } from "@/navigation/BottomTabBar";
import { EmptyDestinationScreen } from "@/features/destinations/EmptyDestinationScreen";
import { TodayScreen } from "@/features/today/TodayScreen";
import { AppProvider } from "@/state/AppProvider";
import { tokens } from "@/theme/tokens";

describe("native application shell", () => {
  it("is Android-only and locked to portrait", () => {
    expect(appConfig.expo.orientation).toBe("portrait");
    expect(appConfig.expo.platforms).toEqual(["android"]);
    expect(appConfig.expo.android.package).toBe("com.sakhicircle.app");
    expect("ios" in appConfig.expo).toBe(false);
  });

  it("renders exactly three safe-area-aware destinations", async () => {
    expect(TAB_DESTINATIONS).toHaveLength(3);
    await render(
      <AppProvider>
        <AppFrame>
          <BottomTabBar selected="today" onSelect={jest.fn()} />
        </AppFrame>
      </AppProvider>,
    );

    expect(screen.getByTestId("safe-area-shell")).toBeOnTheScreen();
    expect(screen.getAllByRole("tab")).toHaveLength(3);
    expect(screen.getByRole("tab", { name: "Today" })).toBeSelected();
  });

  it("supports navigation callbacks and 48dp targets", async () => {
    const onSelect = jest.fn();
    await render(
      <AppProvider>
        <BottomTabBar selected="today" onSelect={onSelect} />
      </AppProvider>,
    );

    fireEvent.press(screen.getByRole("tab", { name: "My Circle" }));
    expect(onSelect).toHaveBeenCalledWith("circle");
    expect(tokens.target.minimum).toBeGreaterThanOrEqual(48);
    expect(tokens.type.body).toBe(18);
    expect(tokens.motion.state).toBe(180);
  });

  it("preserves the approved Today content and Hindi labels", async () => {
    await render(
      <AppProvider initialLocale="hi">
        <TodayScreen />
      </AppProvider>,
    );

    expect(screen.getByRole("header", { name: "नमस्ते, मीरा" })).toBeOnTheScreen();
    expect(screen.getByText("आपकी अगली शुरुआत यहाँ से होती है")).toBeOnTheScreen();
    expect(screen.getByText("SakhiCircle कैसे काम करता है")).toBeOnTheScreen();
  });

  it("keeps the compact Hindi shell from crowding at phone width", async () => {
    await render(
      <AppProvider initialLocale="hi">
        <AppHeader />
        <TodayScreen />
      </AppProvider>,
    );

    expect(screen.getAllByText("EN")).toHaveLength(2);
    expect(screen.getByTestId("today-section-heading")).toHaveStyle({
      alignItems: "flex-start",
      flexDirection: "column",
    });
  });

  it.each([
    ["circle", "Your circle is ready when you are."],
    ["mentors", "Find guidance at your pace."],
  ] as const)("renders the %s empty state", async (destination, message) => {
    await render(
      <AppProvider>
        <EmptyDestinationScreen destination={destination} />
      </AppProvider>,
    );

    expect(screen.getByText(message)).toBeOnTheScreen();
  });
});
