const { test, expect } = require("@playwright/test");

test.use({
  viewport: { width: 430, height: 900 },
  launchOptions: {
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
  }
});

test("profile screen shows trader identity, rules, preferences, and security actions", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("http://127.0.0.1:8097?riskwise_preview=1");
  await page.getByText("Profile", { exact: true }).last().click();

  await expect(page.getByText("Overview")).toBeVisible();
  await expect(page.getByText("Trader DNA")).toBeVisible();
  await expect(page.getByText("What RiskWise Has Learned")).toBeVisible();
  await expect(page.getByText("Decision Quality Breakdown")).toBeVisible();

  await page.getByText("Rules & AI").click();
  await expect(page.getByText("Max risk per trade")).toBeVisible();
  await expect(page.getByText("These rules are used in every analysis")).toBeVisible();

  await page.getByText("Explanation Style").click();
  await expect(page.getByText("Preferred explanations")).toBeVisible();
  await page.getByText("Quant-heavy").click();
  await page.getByText("Save", { exact: true }).click();
  await expect(page.getByText("Profile saved.")).toBeVisible();
  await page.getByText("OK").click();
  await expect(page.getByText("Quant-heavy").first()).toBeVisible();

  await expect(page.getByText("Use compact report cards")).toBeVisible();
  await page.getByText("Use compact report cards").click();
  await expect(page.getByText("Profile saved.")).toBeVisible();
  await page.getByText("OK").click();

  await page.getByText("Account", { exact: true }).click();
  await expect(page.getByText("Account & Security")).toBeVisible();
  await page.getByText("Display Name").click();
  await page.locator("input").last().fill("Aarav Settings Test");
  await page.getByText("Save", { exact: true }).click();
  await expect(page.getByText("Profile saved.")).toBeVisible();
  await page.getByText("OK").click();
  await expect(page.getByText("Aarav Settings Test")).toBeVisible();

  await expect(page.getByText("Clear all context")).toBeVisible();
  await page.getByText("Clear all context").click();
  await expect(page.getByText("Clear all context?")).toBeVisible();
  await page.getByText("Cancel").click();

  await expect(page.getByText("Send Password Reset Email")).toBeVisible();
  await page.getByText("Delete Account Data").click();
  await expect(page.getByText("Delete account data?")).toBeVisible();
  await page.getByText("Cancel").click();

  expect(
    errors
      .filter((message) => !message.includes("favicon"))
      .filter((message) => !message.includes("File not found"))
      .join("\n")
  ).toBe("");
});
