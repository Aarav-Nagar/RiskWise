const { test, expect } = require("@playwright/test");

test.use({
  viewport: { width: 430, height: 900 },
  launchOptions: {
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
  }
});

test("check flow supports niche ticker search and investigation screens", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("http://127.0.0.1:8097?riskwise_preview=1");
  await expect(page.getByText("Stock lookup")).toBeVisible();

  await page.getByText("Check", { exact: true }).last().click();
  await expect(page.getByText("How would you like to check a trade?")).toBeVisible();

  await page.getByText("Option Contract").click();
  await expect(page.getByText("Build Your Trade")).toBeVisible();

  const tickerInput = page.getByPlaceholder("Search ticker or company");
  await tickerInput.fill("achr");
  await expect(page.getByText("Archer Aviation Inc.").first()).toBeVisible({ timeout: 10000 });
  await page.getByText("Archer Aviation Inc.").first().click();
  await expect(page.getByText("ACHR", { exact: true }).first()).toBeVisible();

  await page.getByText("Review Trade").click();
  await expect(page.getByText("Trade Investigation")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Why RiskWise is hesitating")).toBeVisible();

  await page.getByText("Open Committee Debate").click();
  await expect(page.getByText("Committee Debate")).toBeVisible();
  await expect(page.getByText("Bull Analyst")).toBeVisible();

  expect(
    errors
      .filter((message) => !message.includes("favicon"))
      .filter((message) => !message.includes("File not found"))
      .join("\n")
  ).toBe("");
});
