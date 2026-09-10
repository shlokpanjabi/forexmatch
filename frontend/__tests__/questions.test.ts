import { describe, expect, it } from "vitest";

import { DESTINATIONS, spendBandsFor, toProfile } from "@/components/pick/questions";

const uk = DESTINATIONS.find((d) => d.id === "uk")!;
const uae = DESTINATIONS.find((d) => d.id === "ae")!;

describe("spend bands", () => {
  it("scales to the destination rather than asking one global question", () => {
    // £600 and AED 600 are not the same question.
    const ukBands = spendBandsFor(uk);
    const uaeBands = spendBandsFor(uae);

    expect(uaeBands[2].min).toBeGreaterThan(ukBands[2].min * 3);
    expect(ukBands[0].label).toContain("£");
    expect(uaeBands[0].label).toContain("AED");
  });

  it("differentiates cities within the same currency", () => {
    const germany = spendBandsFor(DESTINATIONS.find((d) => d.id === "de")!);
    const ireland = spendBandsFor(DESTINATIONS.find((d) => d.id === "ie")!);

    expect(ireland[0].min).toBeGreaterThan(germany[0].min);
  });

  it("always offers an explicit 'not sure', spanning the middle", () => {
    const bands = spendBandsFor(uk);
    const unsure = bands.at(-1)!;

    expect(unsure.value).toBe("unsure");
    expect(unsure.max - unsure.min).toBeGreaterThan(bands[2].max - bands[2].min);
  });

  it("still works before a destination has been chosen", () => {
    expect(spendBandsFor(undefined).length).toBeGreaterThan(1);
  });

  it("labels the first and last bands as open-ended", () => {
    const bands = spendBandsFor(uk);
    expect(bands[0].label).toMatch(/^Under/);
    expect(bands[4].label).toMatch(/^Over/);
  });
});

describe("profile mapping", () => {
  it("records an uncertain answer with lower confidence than a chosen band", () => {
    const bands = spendBandsFor(uk);
    const chosen = toProfile({ destination: uk, spend: bands[2] });
    const unsure = toProfile({ destination: uk, spend: bands.at(-1)! });

    expect(chosen.monthly_spend.confidence).toBe("estimated");
    expect(unsure.monthly_spend.confidence).toBe("assumed");
  });

  it("carries the destination currency through to the profile", () => {
    const profile = toProfile({ destination: uk, spend: spendBandsFor(uk)[1] });
    expect(profile.destination_currencies).toEqual(["GBP"]);
    expect(profile.monthly_spend.currency).toBe("GBP");
    expect(profile.monthly_spend.min_amount).toBe("600");
  });
});
