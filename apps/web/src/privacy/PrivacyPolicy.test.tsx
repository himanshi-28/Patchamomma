import axe from "axe-core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { PrivacyPolicy } from "./PrivacyPolicy";

describe("SakhiCircle privacy policy", () => {
  it("clearly explains YouTube discovery, retention, deletion, and third-party terms", async () => {
    const user = userEvent.setup();
    const rendered = render(<PrivacyPolicy />);

    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeVisible();
    expect(screen.getByText(/topic, learning level, and preferred plan language/)).toBeVisible();
    expect(screen.getByText(/do not send your transcript, name, email address, city, accessibility choices/)).toBeVisible();
    expect(screen.getByText(/no longer than 29 days/)).toBeVisible();
    expect(screen.getByText(/Remove video guide/)).toBeVisible();
    expect(screen.getByRole("link", { name: "YouTube Terms of Service" })).toHaveAttribute(
      "href",
      "https://www.youtube.com/t/terms",
    );
    expect(screen.getByRole("link", { name: "Google Privacy Policy" })).toHaveAttribute(
      "href",
      "https://policies.google.com/privacy",
    );
    expect((await axe.run(rendered.container)).violations.filter(
      (violation) => ["critical", "serious"].includes(violation.impact ?? ""),
    )).toEqual([]);

    await user.click(screen.getByRole("button", { name: "हिंदी में देखें" }));
    expect(screen.getByRole("heading", { name: "गोपनीयता नीति" })).toBeVisible();
    expect(screen.getByText(/29 दिनों से अधिक/)).toBeVisible();
    expect(screen.getByRole("link", { name: "SakhiCircle होम पर वापस जाएँ" })).toBeVisible();
  });
});
