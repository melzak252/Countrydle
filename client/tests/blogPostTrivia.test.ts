import { describe, it, expect } from "bun:test";
import { getFalseDistractor } from "../src/lib/blogTrivia";

describe("getFalseDistractor", () => {
  it("generates a guaranteed-false statement for African countries (like Tunisia)", () => {
    const distractorEn = getFalseDistractor("Tunisia", "Africa", { continent: "Africa" }, false);
    expect(distractorEn).toContain("South America");
    expect(distractorEn).not.toContain("Mediterranean");

    const distractorPl = getFalseDistractor("Tunisia", "Africa", { continent: "Africa" }, true);
    expect(distractorPl).toContain("Ameryce Południowej");
  });

  it("generates mutually exclusive false distractors for all other continents", () => {
    // Europe
    const europeDist = getFalseDistractor("Poland", "Europe");
    expect(europeDist).toContain("Southern Hemisphere");

    // Asia
    const asiaDist = getFalseDistractor("Vietnam", "Asia");
    expect(asiaDist).toContain("Central America");

    // South America
    const saDist = getFalseDistractor("Brazil", "South America");
    expect(saDist).toContain("European Union");

    // North America
    const naDist = getFalseDistractor("United States", "North America");
    expect(naDist).toContain("African continent");

    // Oceania
    const oceaniaDist = getFalseDistractor("Palau", "Oceania");
    expect(oceaniaDist).toContain("Central Europe");
  });

  it("never suggests Mediterranean Sea coastline for any country", () => {
    const continents = ["Africa", "Europe", "Asia", "South America", "North America", "Oceania", "Unknown"];
    for (const cont of continents) {
      const dist = getFalseDistractor("TestCountry", cont);
      expect(dist.toLowerCase()).not.toContain("mediterranean");
    }
  });
});
