import { chromium } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../');
const screenshotsDir = path.join(rootDir, 'report', 'screenshots');

if (!fs.existsSync(screenshotsDir)) {
  fs.mkdirSync(screenshotsDir, { recursive: true });
}

async function run() {
  console.log('Starting Playwright Chromium for screenshot capture (Prompt 10 Limited Exception)...');
  const browser = await chromium.launch({ headless: true });

  const tasks = [
    {
      name: 'Landing Page Desktop',
      url: 'http://127.0.0.1:5173/',
      viewport: { width: 1360, height: 900 },
      outputPath: path.join(screenshotsDir, 'landing-desktop.png'),
    },
    {
      name: 'Landing Page Mobile (390px)',
      url: 'http://127.0.0.1:5173/',
      viewport: { width: 390, height: 844 },
      outputPath: path.join(screenshotsDir, 'landing-mobile.png'),
      checkOverflow: true,
    },
    {
      name: 'Login Page Desktop',
      url: 'http://127.0.0.1:5173/login',
      viewport: { width: 1360, height: 900 },
      outputPath: path.join(screenshotsDir, 'login-desktop.png'),
    },
    {
      name: 'Login Page Mobile (390px)',
      url: 'http://127.0.0.1:5173/login',
      viewport: { width: 390, height: 844 },
      outputPath: path.join(screenshotsDir, 'login-mobile.png'),
      checkOverflow: true,
    },
    {
      name: 'Branded 404 Page Desktop',
      url: 'http://127.0.0.1:5173/unknown-path-404',
      viewport: { width: 1360, height: 900 },
      outputPath: path.join(screenshotsDir, '404-desktop.png'),
    },
  ];

  for (const task of tasks) {
    const context = await browser.newContext({
      viewport: task.viewport,
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    await page.goto(task.url, { waitUntil: 'networkidle' });
    // Wait for animations/fonts to settle
    await page.waitForTimeout(600);

    if (task.checkOverflow) {
      const overflow = await page.evaluate(() => {
        const docElem = document.documentElement;
        const body = document.body;
        return {
          scrollWidth: Math.max(docElem.scrollWidth, body.scrollWidth),
          clientWidth: docElem.clientWidth,
          hasOverflow: Math.max(docElem.scrollWidth, body.scrollWidth) > docElem.clientWidth,
        };
      });
      console.log(`[390px Check] ${task.name}: scrollWidth=${overflow.scrollWidth}, clientWidth=${overflow.clientWidth}, hasOverflow=${overflow.hasOverflow}`);
    }

    await page.screenshot({ path: task.outputPath, fullPage: false });
    console.log(`Captured: ${task.outputPath}`);
    await context.close();
  }

  await browser.close();
  console.log('All screenshots captured successfully.');
}

run().catch((err) => {
  console.error('Screenshot capture failed:', err);
  process.exit(1);
});

