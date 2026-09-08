import axe from "axe-core";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DemoActivityCenter } from "./DemoActivityCenter";

const seriousViolations = async (container: HTMLElement) => {
  const result = await axe.run(container);
  return result.violations.filter(
    (violation) => violation.impact === "critical" || violation.impact === "serious",
  );
};

describe("DemoActivityCenter", () => {
  it("offers a schedule-first browse experience with deterministic mentor classes", () => {
    render(<DemoActivityCenter locale="en" />);

    expect(screen.getByRole("heading", { name: "Find a class that fits your week" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Register as a mentor" })).toBeVisible();
    expect(screen.getByRole("group", { name: "Choose a class date" })).toBeVisible();
    expect(screen.getByLabelText("Interest")).toBeVisible();
    expect(screen.getByLabelText("Class format")).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(6);
    expect(screen.getByRole("heading", { name: "Kathak: Begin with rhythm" })).toBeVisible();
    expect(screen.getByText("Nandita Rao · Verified demo mentor")).toBeVisible();
    expect(screen.getAllByText("Synthetic demo class")).toHaveLength(6);
  });

  it("filters classes by interest and format without hiding the result count", async () => {
    const user = userEvent.setup();
    render(<DemoActivityCenter locale="en" />);

    await user.selectOptions(screen.getByLabelText("Interest"), "Painting");
    expect(screen.getByRole("status")).toHaveTextContent("1 demo class found");
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Paint your first postcard" })).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Class format"), "In person");
    expect(screen.getByRole("status")).toHaveTextContent("No demo classes match these filters");
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeVisible();
  });

  it("creates an accessible session ticket in the required detail order", async () => {
    const user = userEvent.setup();
    render(<DemoActivityCenter locale="en" />);

    await user.click(screen.getByRole("button", { name: "Book demo seat for Kathak: Begin with rhythm" }));

    const ticket = screen.getByRole("region", { name: "Your demo session ticket" });
    expect(within(ticket).getAllByRole("term").map((term) => term.textContent)).toEqual([
      "Mentor",
      "Topic",
      "Language",
      "Date",
      "Time",
      "Payment status",
      "Joining instructions",
    ]);
    expect(within(ticket).getByText("No payment taken — demo seat")).toBeVisible();
    expect(within(ticket).getByText("Nandita Rao")).toBeVisible();
    expect(screen.getByRole("button", { name: "Booked Kathak: Begin with rhythm" })).toBeDisabled();
  });

  it("accepts a deterministic mentor-interest registration without collecting payment details", async () => {
    const user = userEvent.setup();
    render(<DemoActivityCenter locale="en" />);

    await user.click(screen.getByRole("button", { name: "Register as a mentor" }));
    expect(screen.getByRole("heading", { name: "Share what you would love to teach" })).toBeVisible();
    expect(screen.getByText(/does not publish a course or collect bank details/i)).toBeVisible();

    await user.type(screen.getByLabelText("Your name"), "Leela Joshi");
    await user.type(screen.getByLabelText("What would you like to teach?"), "Everyday cooking");
    await user.selectOptions(screen.getByLabelText("Preferred teaching language"), "Hindi");
    await user.selectOptions(screen.getByLabelText("Preferred class format"), "Online");
    await user.click(screen.getByRole("button", { name: "Submit mentor interest" }));

    expect(within(screen.getByRole("region", { name: "Share what you would love to teach" })).getByRole("status")).toHaveTextContent(
      "Thank you, Leela Joshi. Your demo mentor interest for Everyday cooking is recorded for review.",
    );
  });

  it("provides reviewed Hindi labels for discovery, booking, and registration", async () => {
    const user = userEvent.setup();
    render(<DemoActivityCenter locale="hi" />);

    expect(screen.getByRole("heading", { name: "अपने सप्ताह के लिए सही क्लास खोजें" })).toBeVisible();
    expect(screen.getByRole("button", { name: "मेंटर के रूप में रजिस्टर करें" })).toBeVisible();
    expect(screen.getByLabelText("रुचि")).toBeVisible();
    expect(screen.getByLabelText("क्लास का तरीका")).toBeVisible();
    expect(screen.getAllByText("काल्पनिक डेमो क्लास")).toHaveLength(6);

    await user.click(screen.getByRole("button", { name: "कथक: लय से शुरुआत के लिए डेमो सीट बुक करें" }));
    expect(screen.getByRole("region", { name: "आपका डेमो सेशन टिकट" })).toBeVisible();
  });

  it("has no serious automated accessibility violations", async () => {
    const rendered = render(<DemoActivityCenter locale="en" />);
    expect(await seriousViolations(rendered.container)).toEqual([]);
  });
});
