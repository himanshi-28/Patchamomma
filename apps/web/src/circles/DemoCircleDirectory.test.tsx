import axe from "axe-core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DemoCircleDirectory } from "./DemoCircleDirectory";

describe("DemoCircleDirectory", () => {
  it("shows six purposeful, synthetic activity circles with useful details", () => {
    render(<DemoCircleDirectory locale="en" />);

    expect(screen.getByRole("heading", { level: 1, name: "Find a circle to begin with" })).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(6);
    for (const activity of ["Driving", "Painting", "Dancing", "Walking", "Sewing", "Cooking"]) {
      expect(screen.getByRole("heading", { name: new RegExp(activity, "i") })).toBeVisible();
    }
    expect(screen.getAllByText("Synthetic demo circle")).toHaveLength(6);
    expect(screen.getAllByText("Hindi & English")).toHaveLength(2);
    expect(screen.queryByText(/followers|likes|popular/i)).not.toBeInTheDocument();
  });

  it("gives accessible, persistent feedback after joining more than one circle", async () => {
    const user = userEvent.setup();
    render(<DemoCircleDirectory locale="en" />);

    await user.click(screen.getByRole("button", { name: "Join Confident Driving Circle" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "You joined Confident Driving Circle. Your first meetup is Saturday at 8:00 AM.",
    );
    expect(screen.getByRole("button", { name: "Joined Confident Driving Circle" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Join Everyday Painting Circle" }));
    expect(screen.getByRole("button", { name: "Joined Confident Driving Circle" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Joined Everyday Painting Circle" })).toBeDisabled();
  });

  it("provides complete Hindi labels and joined-state feedback", async () => {
    const user = userEvent.setup();
    render(<DemoCircleDirectory locale="hi" />);

    expect(screen.getByRole("heading", { level: 1, name: "शुरुआत के लिए अपना सर्कल चुनें" })).toBeVisible();
    expect(screen.getAllByText("काल्पनिक डेमो सर्कल")).toHaveLength(6);
    expect(screen.getAllByRole("button", { name: /^जुड़ें / })).toHaveLength(6);

    await user.click(screen.getByRole("button", { name: "जुड़ें आत्मविश्वास से ड्राइविंग सर्कल" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "आप आत्मविश्वास से ड्राइविंग सर्कल से जुड़ गई हैं। आपकी पहली बैठक शनिवार सुबह 8:00 बजे है।",
    );
  });

  it("has no serious or critical accessibility violations", async () => {
    const rendered = render(<DemoCircleDirectory locale="en" />);
    const result = await axe.run(rendered.container);
    const seriousViolations = result.violations.filter(
      (violation) => violation.impact === "critical" || violation.impact === "serious",
    );

    expect(seriousViolations).toEqual([]);
  });
});
