import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { run } from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { OnboardingFlow } from "./OnboardingFlow";
import {
  createDeterministicTranscriptAdapter,
  ProfileSaveError,
  TranscriptCaptureError,
} from "./runtime";

const completeTranscript = "I want to restart watercolours and paint a greeting card. I can practise for 30 minutes, four days a week. I prefer Hindi, larger text, seated alternatives, and a small online group in Pune.";

describe("SC-310 onboarding flow", () => {
  it("has no serious accessibility violations in capture or review", async () => {
    const user = userEvent.setup();
    const rendered = render(<OnboardingFlow locale="en" transcriptAdapter={createDeterministicTranscriptAdapter()} profileGateway={{ save: vi.fn() }} />);
    const serious = async () => (await run(rendered.container)).violations
      .filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""));

    expect(await serious()).toEqual([]);
    await user.type(screen.getByLabelText("Your learning wish"), completeTranscript);
    await user.click(screen.getByRole("button", { name: "Review my details" }));
    expect(await serious()).toEqual([]);
  });

  it("keeps text in memory and writes nothing before explicit confirmation", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    render(<OnboardingFlow locale="en" transcriptAdapter={createDeterministicTranscriptAdapter()} profileGateway={{ save }} />);

    await user.type(screen.getByLabelText("Your learning wish"), completeTranscript);
    expect(save).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Review my details" }));
    expect(screen.getByText("Nothing has been saved")).toBeVisible();
    expect(screen.getByLabelText("Editable transcript")).toHaveValue(completeTranscript);
    expect(save).not.toHaveBeenCalled();
  });

  it("uses the deterministic voice adapter and keeps the transcript editable", async () => {
    const user = userEvent.setup();
    render(<OnboardingFlow locale="en" transcriptAdapter={createDeterministicTranscriptAdapter()} profileGateway={{ save: vi.fn() }} />);

    await user.click(screen.getByRole("button", { name: "Start speaking" }));

    expect((await screen.findByLabelText("Your learning wish") as HTMLTextAreaElement).value).toContain("restart watercolours");
    expect(screen.getByText(/SakhiCircle deterministic local voice/)).toBeVisible();
  });

  it("keeps typing available and focuses recovery when browser speech is unsupported", async () => {
    const user = userEvent.setup();
    render(
      <OnboardingFlow
        locale="en"
        transcriptAdapter={{
          providerName: "Browser speech recognition",
          providerPolicy: "The browser may process audio under its own terms.",
          capture: vi.fn().mockRejectedValue(new TranscriptCaptureError("unsupported")),
        }}
        profileGateway={{ save: vi.fn() }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Start speaking" }));

    const recovery = await screen.findByRole("alert");
    expect(recovery).toHaveTextContent("Voice input is not supported in this browser");
    expect(recovery).toHaveFocus();
    expect(screen.getByLabelText("Your learning wish")).toBeEnabled();
  });

  it("requires transcript review and plan consent, then discards the transcript after save", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    render(<OnboardingFlow locale="en" transcriptAdapter={createDeterministicTranscriptAdapter()} profileGateway={{ save }} />);

    await user.type(screen.getByLabelText("Your learning wish"), completeTranscript);
    await user.click(screen.getByRole("button", { name: "Review my details" }));
    const confirm = screen.getByRole("button", { name: "Confirm and create my 4-week plan" });
    expect(confirm).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "My words look right" }));
    await user.click(screen.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }));
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    expect(save).toHaveBeenCalledTimes(1);
    expect(save.mock.calls[0][0]).not.toHaveProperty("transcript");
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Your plan is ready to build" }));
    expect(screen.queryByDisplayValue(completeTranscript)).not.toBeInTheDocument();
  });

  it("preserves the reviewed draft and offers retry when saving fails", async () => {
    const user = userEvent.setup();
    const save = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(undefined);
    render(<OnboardingFlow locale="en" transcriptAdapter={createDeterministicTranscriptAdapter()} profileGateway={{ save }} />);

    await user.type(screen.getByLabelText("Your learning wish"), completeTranscript);
    await user.click(screen.getByRole("button", { name: "Review my details" }));
    await user.click(screen.getByRole("button", { name: "My words look right" }));
    await user.click(screen.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }));
    await user.click(screen.getByRole("button", { name: "Confirm and create my 4-week plan" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your details were not saved");
    expect(screen.getByLabelText("Editable transcript")).toHaveValue(completeTranscript);
    await user.click(screen.getByRole("button", { name: "Retry saving" }));
    expect(save).toHaveBeenCalledTimes(2);
  });

  it("allows experience and first goal to remain optional", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockResolvedValue(undefined);
    render(<OnboardingFlow locale="en" transcriptAdapter={createDeterministicTranscriptAdapter()} profileGateway={{ save }} />);

    await user.type(
      screen.getByLabelText("Your learning wish"),
      "I want to learn paint. I can practise for 30 minutes, four days a week. I prefer Hindi, larger text, and a small online group in Pune.",
    );
    await user.click(screen.getByRole("button", { name: "Review my details" }));

    expect(screen.getByText("Your experience (optional)")).toBeVisible();
    expect(screen.getByText("Your first goal (optional)")).toBeVisible();
    expect(screen.getAllByText("Not provided (optional)")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "My words look right" }));
    await user.click(screen.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }));
    await user.click(screen.getByRole("button", { name: "Confirm and create my 4-week plan" }));

    expect(save).toHaveBeenCalledWith(expect.objectContaining({
      hobby: "Painting",
      experience: "",
      goal: "",
    }));
  });

  it("explains when saving is paused for maintenance and keeps the draft", async () => {
    const user = userEvent.setup();
    const save = vi.fn().mockRejectedValue(new ProfileSaveError("maintenance"));
    render(<OnboardingFlow locale="en" transcriptAdapter={createDeterministicTranscriptAdapter()} profileGateway={{ save }} />);

    await user.type(screen.getByLabelText("Your learning wish"), completeTranscript);
    await user.click(screen.getByRole("button", { name: "Review my details" }));
    await user.click(screen.getByRole("button", { name: "My words look right" }));
    await user.click(screen.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }));
    await user.click(screen.getByRole("button", { name: "Confirm and create my 4-week plan" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("temporarily paused for maintenance");
    expect(screen.getByLabelText("Editable transcript")).toHaveValue(completeTranscript);
  });
});
