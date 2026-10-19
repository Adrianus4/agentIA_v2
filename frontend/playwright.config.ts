import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:4173';
const outputDir = process.env.PLAYWRIGHT_OUTPUT_DIR || './test-results';
const junitOutput = process.env.PLAYWRIGHT_JUNIT_OUTPUT_NAME || './test-results/playwright.junit.xml';
const jsonOutput = process.env.PLAYWRIGHT_JSON_OUTPUT_NAME || './test-results/playwright.report.json';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 180_000,
  expect: {
    timeout: 15_000,
  },
  outputDir,
  reporter: [
    ['list'],
    ['junit', { outputFile: junitOutput }],
    ['json', { outputFile: jsonOutput }],
  ],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    acceptDownloads: true,
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
