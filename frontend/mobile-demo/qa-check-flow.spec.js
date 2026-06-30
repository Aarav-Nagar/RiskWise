const { test, expect } = require("@playwright/test");
const { collectBrowserErrors, filteredErrors, installBackendMocks } = require("./qa-helpers");

test.use({
  viewport: { width: 430, height: 900 }
});

const PREVIEW_PATH = "/?riskwise_preview=1";

async function openCheck(page) {
  await installBackendMocks(page);
  await page.goto(PREVIEW_PATH, { waitUntil: "domcontentloaded" });
  await page.getByText("Check", { exact: true }).last().click();
  await expect(page.getByText("How would you like to check a trade?")).toBeVisible();
}

async function reachContractDetails(page) {
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
}

async function reachFinalReview(page) {
  await reachContractDetails(page);
  await page.getByText("Continue").click();
  await expect(page.getByText("Size & Guardrails")).toBeVisible();
  await page.getByText("Review Final Details").click();
  await expect(page.getByText("Final Review")).toBeVisible();
}

test("option contract flow supports niche ticker search and reaches investigation", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await reachFinalReview(page);
  await expect(page.getByText("Missing data RiskWise will not invent")).toBeVisible();
  await page.getByText("Run Risk Check").click();

  await expect(page.getByText("Trade Investigation")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Why RiskWise is hesitating")).toBeVisible();
  await page.getByText("Open Committee Debate").click();
  await expect(page.getByText("Committee Debate")).toBeVisible();
  await expect(page.getByText("Bull Analyst")).toBeVisible();

  expect(filteredErrors(errors)).toBe("");
});

test("option contract validation blocks impossible bid ask before review", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await reachContractDetails(page);
  const inputs = page.locator("input");
  await inputs.nth(2).fill("1.50");
  await inputs.nth(3).fill("1.00");
  await expect(page.getByText("Bid cannot be greater than ask.")).toBeVisible();
  await page.getByText("Continue").click({ force: true });
  await expect(page.getByText("Contract Details")).toBeVisible();
  await expect(page.getByText("Final Review")).toHaveCount(0);

  expect(filteredErrors(errors)).toBe("");
});

test("completed check becomes selected Coach context", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await reachFinalReview(page);
  await page.getByText("Run Risk Check").click();
  await expect(page.getByText("Trade Investigation")).toBeVisible({ timeout: 15000 });

  await page.getByText("Coach", { exact: true }).last().click();
  await expect(page.getByText(/ACHR/i).first()).toBeVisible();
  await page.getByPlaceholder("Ask RiskWiseAI").fill("What trade did I do?");
  await page.getByLabel("Send message").click();
  await expect(page.getByText(/ACHR Call Option/i)).toBeVisible({ timeout: 10000 });

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
  await expect(page.getByText("Long Call")).toBeVisible();
  await expect(page.getByText("Bull Call Spread")).toHaveCount(0);
  await expect(page.getByText("Cash Secured Put")).toHaveCount(0);
  await expect(page.getByText("Covered Call")).toHaveCount(0);
  await expect(page.getByText("Explore Strategy").first()).toBeVisible();
});

test("screenshot flow shows real upload guidance and honest checklist", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await openCheck(page);
  await page.getByText("Screenshot", { exact: true }).click();
  await expect(page.getByText("Upload Screenshot")).toBeVisible();
  await expect(page.getByText("No guessing")).toBeVisible();
  await expect(page.getByText("Upload contract screenshot")).toBeVisible();
  await expect(page.getByText("Take Photo")).toBeVisible();
  await expect(page.getByText("Photo Library")).toBeVisible();
  await expect(page.getByText("Files")).toBeVisible();
  await expect(page.getByText("Image, TXT, or CSV")).toBeVisible();
  await expect(page.getByText("Clean screenshot checklist")).toBeVisible();
  await expect(page.getByText("RiskWise only uses fields it can actually see.")).toBeVisible();

  expect(filteredErrors(errors)).toBe("");
});

test("screenshot extraction confirms partial data before analysis", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await openCheck(page);
  await page.getByText("Screenshot", { exact: true }).click();
  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByText("Files").click();
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: "contract.png",
    mimeType: "image/png",
    buffer: Buffer.from("riskwise qa screenshot")
  });

  await expect(page.getByText("Review Extracted Details")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Can continue with partial data")).toBeVisible();
  await page.getByText("Confirm & Continue").click();
  await expect(page.getByText("Confirm Contract")).toBeVisible();
  await expect(page.getByText("Missing data RiskWise will not invent")).toBeVisible();
  await page.getByText("Continue to Analysis").click();
  await expect(page.getByText("Running Risk Check")).toBeVisible();
  await page.getByText("View Investigation Results").click();
  await expect(page.getByText("Trade Investigation")).toBeVisible({ timeout: 15000 });

  expect(filteredErrors(errors)).toBe("");
});
