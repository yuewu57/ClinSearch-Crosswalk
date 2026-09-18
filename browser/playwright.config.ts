import {defineConfig, devices} from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', timeout:90000, fullyParallel:false, workers:1,
  reporter:[['list'],['json',{outputFile:'test-results/browser-results.json'}]],
  use:{baseURL:'http://127.0.0.1:4173',trace:'retain-on-failure',screenshot:'only-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome'],launchOptions:process.env.CHROMIUM_EXECUTABLE ? {executablePath:process.env.CHROMIUM_EXECUTABLE}: {}}}],
  webServer:{command:'node scripts/serve-preview.mjs',url:'http://127.0.0.1:4173',reuseExistingServer:false,timeout:20000},
});
