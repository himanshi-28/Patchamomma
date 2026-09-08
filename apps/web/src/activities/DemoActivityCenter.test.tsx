import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DemoActivityCenter } from "./DemoActivityCenter";

describe("DemoActivityCenter", () => {
  it("shows six clearly synthetic activities with practical booking details", () => {
    render(<DemoActivityCenter locale="en" />);

    expect(screen.getByRole("heading", { name: "Activities near you" })).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(6);
    expect(screen.getByRole("heading", { name: "Kathak: Begin with rhythm" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Paint your first postcard" })).toBeVisible();
    expect(screen.getByText("Nandita Rao · Demo mentor")).toBeVisible();
    expect(screen.getByText("Sat, 12 Sep · 10:30 AM")).toBeVisible();
    expect(screen.getByText("Indiranagar, Bengaluru")).toBeVisible();
    expect(screen.getByText("₹450")).toBeVisible();
    expect(screen.getAllByText("Synthetic demo listing")).toHaveLength(6);
  });

  it("turns a join action into an accessible demo booking confirmation", async () => {
    const user = userEvent.setup();
    render(<DemoActivityCenter locale="en" />);

    await user.click(screen.getByRole("button", { name: "Join Kathak: Begin with rhythm" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "Demo booking saved for Kathak: Begin with rhythm with Nandita Rao",
    );
    expect(screen.getByRole("button", { name: "Joined Kathak: Begin with rhythm" })).toBeDisabled();
  });

  it("keeps earlier demo bookings joined when another activity is booked", async () => {
    const user = userEvent.setup();
    render(<DemoActivityCenter locale="en" />);

    await user.click(screen.getByRole("button", { name: "Join Kathak: Begin with rhythm" }));
    await user.click(screen.getByRole("button", { name: "Join Paint your first postcard" }));

    expect(screen.getByRole("button", { name: "Joined Kathak: Begin with rhythm" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Joined Paint your first postcard" })).toBeDisabled();
  });

  it("provides reviewed Hindi labels for the activity centre", () => {
    render(<DemoActivityCenter locale="hi" />);

    expect(screen.getByRole("heading", { name: "आपके पास की गतिविधियाँ" })).toBeVisible();
    expect(screen.getAllByRole("button", { name: /^जुड़ें / })).toHaveLength(6);
    expect(screen.getAllByText("काल्पनिक डेमो सूची")).toHaveLength(6);
  });
});
