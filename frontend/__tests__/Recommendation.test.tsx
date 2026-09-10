import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Results } from "@/components/results/Results";
import { ProfileSummary } from "@/components/chat/ProfileSummary";
import type { Profile } from "@/lib/types";
import { evaluation, recommendation } from "./fixtures";

describe("Results", () => {
  it("labels a substituted figure rather than presenting it as published", async () => {
    render(<Results recommendation={recommendation()} sessionId="s" />);
    await userEvent.click(screen.getByText(/See the full calculation/));

    expect(screen.getByText(/instead of assuming it is free/)).toBeInTheDocument();
  });

  it("warns when a card's currency support could not be verified", () => {
    const unverified = evaluation();
    unverified.card.currency_support_verified = false;
    render(
      <Results
        recommendation={recommendation({ recommended_card: unverified })}
        sessionId="s"
      />,
    );
    expect(screen.getByText(/Currencies unverified/)).toBeInTheDocument();
  });

  it("flags cards that are effectively tied", () => {
    const alternative = evaluation();
    alternative.card = { ...alternative.card, id: "card-2", card_name: "Club Vistara Forex Card" };
    render(
      <Results
        recommendation={recommendation({
          alternatives: [alternative],
          comparison: [evaluation(), alternative],
          tied_with_recommended: ["card-2"],
        })}
        sessionId="s"
      />,
    );
    expect(screen.getByText(/effectively tied with the top pick/)).toBeInTheDocument();
  });

  it("says so when a provider publishes no application route", () => {
    const noRoute = evaluation({ application_url: null });
    render(
      <Results recommendation={recommendation({ recommended_card: noRoute })} sessionId="s" />,
    );
    expect(screen.getByText(/publishes no online application/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Apply at/ })).not.toBeInTheDocument();
  });

  it("records the click before opening the provider's flow", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ application_url: "https://provider.example/apply", is_affiliate: false }),
    );
    render(<Results recommendation={recommendation()} sessionId="session-123" />);

    await userEvent.click(screen.getByRole("button", { name: /Apply at/ }));

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/application-click"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(window.open).toHaveBeenCalledWith(
      "https://provider.example/apply",
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("handles having no qualifying card", () => {
    render(
      <Results
        recommendation={recommendation({ recommended_card: null, alternatives: [] })}
        sessionId="s"
      />,
    );
    expect(screen.getByText(/No card in the catalogue suits/)).toBeInTheDocument();
  });
});

describe("ProfileSummary", () => {
  const base: Profile = {
    destination_country: "United Kingdom",
    destination_currencies: ["GBP"],
    trip_duration_months: 24,
    monthly_spend: { min_amount: "1000", max_amount: "1200", currency: "GBP", confidence: "estimated" },
    atm_usage: "low",
    atm_withdrawals_per_month: null,
    expected_reload_frequency: null,
    needs_multiple_currencies: null,
    student_status: true,
    priorities: { cost: 0.4 },
    priorities_customised: false,
  };

  it("shows an uncertain spend as a range, marked as an estimate", () => {
    render(<ProfileSummary profile={base} />);
    expect(screen.getByText("GBP 1,000–1,200 (est.)")).toBeInTheDocument();
  });

  it("does not add an estimate qualifier to a figure the user stated", () => {
    render(
      <ProfileSummary
        profile={{
          ...base,
          monthly_spend: { min_amount: "1100", max_amount: "1100", currency: "GBP", confidence: "stated" },
        }}
      />,
    );
    expect(screen.getByText("GBP 1,100")).toBeInTheDocument();
  });
});
