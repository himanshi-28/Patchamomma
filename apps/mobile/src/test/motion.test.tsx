import { act, render, screen, waitFor } from "@testing-library/react-native";
import { AccessibilityInfo, Text } from "react-native";

import { useReducedMotion } from "@/accessibility/useReducedMotion";

describe("reduced motion", () => {
  afterEach(() => jest.restoreAllMocks());

  it("follows the native accessibility preference and later preference changes", async () => {
    let onChange: ((enabled: boolean) => void) | undefined;
    jest.spyOn(AccessibilityInfo, "isReduceMotionEnabled").mockResolvedValue(true);
    jest.spyOn(AccessibilityInfo, "addEventListener").mockImplementation(((_eventName: string, listener: unknown) => {
      onChange = listener as (enabled: boolean) => void;
      return { remove: jest.fn() };
    }) as never);

    function PreferenceProbe() {
      const reducedMotion = useReducedMotion();
      return <Text testID="reduced-motion">{String(reducedMotion)}</Text>;
    }

    await render(<PreferenceProbe />);
    await waitFor(() => expect(screen.getByTestId("reduced-motion")).toHaveTextContent("true"));

    await act(async () => onChange?.(false));
    expect(screen.getByTestId("reduced-motion")).toHaveTextContent("false");
  });
});
