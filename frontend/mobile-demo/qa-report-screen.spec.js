const { test, expect } = require("@playwright/test");
const { collectBrowserErrors, filteredErrors, installBackendMocks, PREVIEW_PATH } = require("./qa-helpers");

test.use({
  viewport: { width: 430, height: 900 }
});

// ReportScreen is only reachable by opening a saved check from Home, so the
// saved-checks list has to answer with one. The shared mocks return [].
function savedCheck(report) {
  return [
    {
      id: "saved-qa-report",
      userId: "preview-user",
      tradeCheckId: "qa-report-check",
      report,
      note: "",
      createdAt: new Date().toISOString()
    }
  ];
}

// Saved reports are stored already-normalised, so the top level is camelCase.
// normalizeSavedReport only back-fills the nested snake_case objects.
const FULL_REPORT = {
  id: "qa-report-check",
  ticker: "ACHR",
  tradeType: "Call Option (Long)",
  title: "ACHR QA Options Check",
  subtitle: "$10 Strike - QA",
  badge: "Needs Review",
  setupScore: 68,
  riskScore: 5.8,
  insight: "Structure has defined max loss.",
  strike: 10,
  timeframe: "1-2 Weeks",
  decision_snapshot: { setup_quality: 68, options_structure: 58, risk_budget_used: 2, profile_risk_limit: 2 },
  risk_math: { max_loss: 500, breakeven: 15, required_move_percent: 4.2, account_risk_percent: 2 },
  agent_docket: [
    { agent: "Bull Analyst", stance: "constructive", note: "Defined risk." },
    { agent: "Risk Manager", stance: "cautious", note: "Liquidity is thin." }
  ]
};

// The same check with the risk math and review panel absent.
const SPARSE_REPORT = {
  id: "qa-report-check",
  ticker: "ACHR",
  tradeType: "Call Option (Long)",
  title: "ACHR QA Options Check",
  subtitle: "$10 Strike - sparse payload",
  badge: "Needs Review",
  insight: "Backend returned a partial report on purpose.",
  strike: 10,
  timeframe: "1-2 Weeks"
};

async function openReport(page, report) {
  await installBackendMocks(page);
  // Registered after the shared mocks so this list wins over the empty one.
  await page.route(/\/saved-checks\//, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(savedCheck(report))
    })
  );

  await page.goto(PREVIEW_PATH, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Saved Checks")).toBeVisible({ timeout: 15000 });
  await page.getByText(/ACHR Call Option/i).first().click();
}

test("report screen opens a saved check and switches between its panels", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await openReport(page, FULL_REPORT);

  // Overview is the default panel.
  await expect(page.getByText("Decision Snapshot")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Contract Label")).toBeVisible();

  await page.getByText("Agents", { exact: true }).first().click();
  await expect(page.getByText("Review Panel")).toBeVisible();

  await page.getByText("Debate", { exact: true }).first().click();
  await expect(page.getByText("Setup Debate")).toBeVisible();

  expect(filteredErrors(errors)).toBe("");
});

test("report screen labels absent backend sections as missing instead of inventing them", async ({ page }) => {
  const errors = collectBrowserErrors(page);

  await openReport(page, SPARSE_REPORT);

  await expect(page.getByText("Decision Snapshot")).toBeVisible({ timeout: 15000 });

  // Sections the backend omitted must say so rather than render as numbers.
  await page.getByText("Risk Math", { exact: true }).first().click();
  await expect(page.getByText(/not available - .*was not returned for this check/i).first()).toBeVisible();

  expect(filteredErrors(errors)).toBe("");
});
