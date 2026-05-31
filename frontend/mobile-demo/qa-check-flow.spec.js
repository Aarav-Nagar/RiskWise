const { test, expect } = require("@playwright/test");

test.use({
  viewport: { width: 430, height: 900 },
  launchOptions: {
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
  }
});

async function openCheck(page) {
  await page.goto("http://127.0.0.1:8097?riskwise_preview=1");
  await page.getByText("Check", { exact: true }).last().click();
  await expect(page.getByText("How would you like to check a trade?")).toBeVisible();
}

test("option contract flow supports niche ticker search and reaches investigation", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await openCheck(page);
  await page.getByText("Option Contract", { exact: true }).click();
  await expect(page.getByText("Select Ticker")).toBeVisible();

  await page.getByPlaceholder("Search ticker, e.g. AAPL").fill("achr");
  await expect(page.getByText("Archer Aviation Inc.").first()).toBeVisible({ timeout: 10000 });
  await page.getByText("Archer Aviation Inc.").first().click();
  await expect(page.getByText("ACHR", { exact: true }).first()).toBeVisible();

  await page.getByText("Continue").click();
  await expect(page.getByText("Choose Direction")).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("Select Option Type")).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("Expiration", { exact: true })).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("Contract Details")).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("Size & Guardrails")).toBeVisible();
  await page.getByText("Review Trade Check").click();

  await expect(page.getByText("Trade Investigation")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Why RiskWise is hesitating")).toBeVisible();
  await page.getByText("Open Committee Debate").click();
  await expect(page.getByText("Committee Debate")).toBeVisible();
  await expect(page.getByText("Bull Analyst")).toBeVisible();

  expect(filteredErrors(errors)).toBe("");
});

test("stock idea flow suggests strategies before contract details", async ({ page }) => {
  await openCheck(page);
  await page.getByText("Stock Idea", { exact: true }).click();
  await expect(page.getByText("What's the stock?")).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("What's your outlook?")).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("Time Horizon")).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("Risk Tolerance")).toBeVisible();
  await page.getByText("Continue").click();
  await expect(page.getByText("Suggested Strategies")).toBeVisible();
  await expect(page.getByText("Explore Strategy").first()).toBeVisible();
});

test("screenshot flow mocks extraction and confirmation", async ({ page }) => {
  await openCheck(page);
  await page.getByText("Screenshot", { exact: true }).click();
  await expect(page.getByText("Upload Screenshot")).toBeVisible();
  await page.getByText("Tap to upload").click();
  await expect(page.getByText("Extracting Details...")).toBeVisible();
  await page.getByText("Review Extracted Details").click();
  await expect(page.getByText("Review Extracted Details")).toBeVisible();
  await page.getByText("Confirm & Continue").click();
  await expect(page.getByText("Confirm Contract")).toBeVisible();
  await page.getByText("Continue to Analysis").click();
  await expect(page.getByText("Running Risk Check")).toBeVisible();
});

function collectBrowserErrors(page) {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

function filteredErrors(errors) {
  return errors
    .filter((message) => !message.includes("favicon"))
    .filter((message) => !message.includes("File not found"))
    .join("\n");
}
