const { test, expect } = require("@playwright/test");
const { collectBrowserErrors, filteredErrors, installBackendMocks } = require("./qa-helpers");

test.use({
  viewport: { width: 430, height: 900 }
});

const PREVIEW_PATH = "/?riskwise_preview=1";

test("active app surfaces render without blank states or generic error cards", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await installBackendMocks(page);
  await page.goto(PREVIEW_PATH, { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/Good morning/)).toBeVisible();
  await expect(page.getByText("Market snapshot")).toBeVisible();
  await expect(page.getByText("Options readiness")).toBeVisible();
  await expect(page.getByText(/needs option-chain proof|options context attached/)).toBeVisible();
  await expect(page.getByText("Data transparency")).toBeVisible();
  await expect(page.getByText(/source ready|sources ready|Backend status pending/)).toBeVisible();
  await expect(page.getByText(/Full|Quote/).first()).toBeVisible();
  await expect(page.getByText(/Manual|Manual upload/).first()).toBeVisible();
  await expect(page.getByText("Something went wrong")).toHaveCount(0);

  await page.getByText("Coach", { exact: true }).last().click();
  await expect(page.getByText(/Hi,/)).toBeVisible();
  await expect(page.getByPlaceholder("Ask RiskWiseAI")).toBeVisible();
  await page.getByLabel("Add context").click();
  await expect(page.getByText("Add context")).toBeVisible();
  await expect(page.getByText("Deep Analysis")).toBeVisible();
  await page.getByLabel("Close sheet").click();

  await page.getByText("Check", { exact: true }).last().click();
  await expect(page.getByText("How would you like to check a trade?")).toBeVisible();
  await expect(page.getByText("Option Contract")).toBeVisible();
  await expect(page.getByText("Stock Idea")).toBeVisible();
  await expect(page.getByText("Screenshot", { exact: true })).toBeVisible();

  await page.getByText("Profile", { exact: true }).last().click();
  await expect(page.getByText("Overview")).toBeVisible();
  await expect(page.getByText("Trader DNA")).toBeVisible();
  await expect(page.getByText("What RiskWise Has Learned")).toBeVisible();
  await expect(page.getByText("Something went wrong")).toHaveCount(0);

  const bodyText = await page.locator("body").innerText();
  expect(bodyText.length).toBeGreaterThan(500);
  expect(filteredErrors(errors)).toBe("");
});

test("home market snapshot stacks cleanly on very small phones", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 });
  const errors = collectBrowserErrors(page);

  await installBackendMocks(page);
  await page.goto(PREVIEW_PATH, { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/Good morning/)).toBeVisible();
  await expect(page.getByText("Market snapshot")).toBeVisible();

  const dayRangeBox = await page.getByText("Day range", { exact: true }).boundingBox();
  const volumeBox = await page.getByText("Volume", { exact: true }).first().boundingBox();
  expect(dayRangeBox).toBeTruthy();
  expect(volumeBox).toBeTruthy();
  expect(volumeBox.x).toBeLessThanOrEqual(dayRangeBox.x + 8);
  expect(volumeBox.y).toBeGreaterThan(dayRangeBox.y);

  expect(filteredErrors(errors)).toBe("");
});
