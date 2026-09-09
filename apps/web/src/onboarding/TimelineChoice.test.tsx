import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { OnboardingFlow } from "./OnboardingFlow";
import { createDeterministicTranscriptAdapter } from "./runtime";

const transcript = "I want to restart watercolours and paint a greeting card. I can practise for 30 minutes, four days a week. I prefer Hindi, larger text, seated alternatives, and a small online group in Pune.";

describe("learning timeline choice", () => {
  it("asks for a timeline, defaults to four weeks, and saves a reviewed six-week choice", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    render(
      <OnboardingFlow
        locale="en"
        transcriptAdapter={createDeterministicTranscriptAdapter()}
        profileGateway={{ save }}
      />,
    );

    const timeline = screen.getByRole("combobox", { name: "How many weeks can you give to learning?" });
    expect(timeline).toHaveValue("4");
    await user.selectOptions(timeline, "6");
    await user.type(screen.getByLabelText("Your learning wish"), transcript);
    await user.click(screen.getByRole("button", { name: "Review my details" }));

    expect(screen.getByRole("combobox", { name: "Learning timeline" })).toHaveValue("6");
    expect(screen.getByText("I agree SakhiCircle may use these reviewed details to create my private 6-week plan.")).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: /create my private 6-week plan/ }));
    await user.click(screen.getByRole("button", { name: "Confirm and create my 6-week plan" }));

    expect(save).toHaveBeenCalledWith(expect.objectContaining({ planWeeks: 6 }));
  });
});
