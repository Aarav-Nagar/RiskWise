const { defineConfig, devices } = require("@playwright/test");

const port = process.env.RISKWISE_QA_PORT || "8099";
const baseURL = process.env.RISKWISE_PREVIEW_URL || `http://127.0.0.1:${port}`;
const webServer = process.env.RISKWISE_SKIP_WEBSERVER
  ? undefined
  : {
      command: `node qa-static-server.cjs --port ${port} --dir dist-web`,
      url: baseURL,
      reuseExistingServer: false,
      timeout: 30_000,
    };

module.exports = defineConfig({
  testMatch: ["qa-*.spec.js"],
  timeout: 60_000,
  globalTimeout: 180_000,
  workers: 1,
  expect: { timeout: 12_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer,
});
