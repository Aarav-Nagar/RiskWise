const { test, expect } = require("@playwright/test");
const { installBackendMocks } = require("./qa-helpers");

const PREVIEW_PATH = "/?riskwise_preview=1";

test.describe("Coach redesign", () => {
  for (const viewport of [
    { width: 390, height: 844, name: "reference mobile" },
    { width: 360, height: 760, name: "smaller mobile" },
    { width: 430, height: 900, name: "larger mobile" }
  ]) {
    test(`renders restored Coach modes at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installBackendMocks(page);
      await page.goto(PREVIEW_PATH, { waitUntil: "domcontentloaded" });

      await page.getByText("Coach", { exact: true }).last().click();

      await page.getByText("Challenge", { exact: true }).click();
      await expect(page.getByText("Challenge Your Trade")).toBeVisible();
      await expect(page.getByLabel("Start Challenge")).toBeVisible();

      await page.getByText("How this works", { exact: true }).click();
      await expect(page.getByText("We ask questions")).toBeVisible();
      await page.getByLabel("Got it").click();

      await page.getByText("Alternatives", { exact: true }).click();
      await expect(page.getByText("Better-fitting alternatives")).toBeVisible();
      // Alternatives are backend-priced now (no hardcoded demo cards): pick a
      // trade so the mocked /alternatives endpoint returns real candidates.
      await page.getByText("Change trade", { exact: true }).click();
      await page.getByText("AAPL 7D Call @ $200", { exact: true }).click();
      await expect(page.getByLabel("Open Same contract, later expiration alternative")).toBeVisible();
    });
  }
});
