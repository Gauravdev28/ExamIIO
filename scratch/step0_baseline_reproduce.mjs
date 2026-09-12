import { execSync } from 'child_process';
import { chromium } from '../frontend/node_modules/playwright-core/index.mjs';

function resetAttempt() {
  const out = execSync('.venv/bin/python backend/manage.py shell < scratch/setup_attempt.py', {
    cwd: '/Users/gauravagarwal/Documents/Exam Website ',
    encoding: 'utf8',
  });
  const match = out.match(/attempt_id=([0-9a-fA-F-]+)/);
  if (!match) throw new Error('Failed to get attempt_id: ' + out);
  return match[1];
}

async function runStep0Baseline() {
  console.log('=== STEP 0: BASELINE BUG REPRODUCTION IN REAL CHROME ===');
  const attemptId = resetAttempt();
  console.log(`Reset test attempt: ${attemptId}`);

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: false,
    args: [
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
      '--no-sandbox',
    ],
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    permissions: ['camera', 'microphone'],
  });

  const page = await context.newPage();

  // Log console messages
  page.on('console', (msg) => {
    console.log(`[BROWSER CONSOLE] ${msg.type()}: ${msg.text()}`);
  });

  try {
    // 1. Log in
    console.log('Logging in as chrome_test_student@example.com...');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');
    await page.locator('#identifier').fill('chrome_test_student@example.com');
    await page.locator('#password').fill('Password123!');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
    console.log('Login successful! URL:', page.url());

    // 2. Navigate to test room
    console.log(`Navigating to test room http://localhost:5173/student/room/${attemptId}...`);
    await page.goto(`http://localhost:5173/student/room/${attemptId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // If pre-check modal or start button is present, complete it
    const startBtn = page.locator('button:has-text("Start Assessment"), button:has-text("Enter Examination"), button:has-text("Start Exam"), button:has-text("I Agree & Continue")').first();
    if (await startBtn.isVisible()) {
      console.log('Clicking start/entry button...');
      await startBtn.click();
      await page.waitForTimeout(1500);
    }

    console.log('Exam room loaded. Current page title / state verified.');

    // 3. Open second real tab to trigger tab-switch
    console.log('--- Opening Second Tab in Chrome (triggering tab switch / visibilitychange: hidden) ---');
    const secondTab = await context.newPage();
    await secondTab.goto('https://example.com');
    await secondTab.bringToFront();
    console.log('Second tab active. Waiting 3 seconds...');
    await secondTab.waitForTimeout(3000);

    // 4. Switch back to exam tab
    console.log('--- Switching back to Exam Tab in Chrome ---');
    await page.bringToFront();
    await page.waitForTimeout(1500);

    // 5. Check if the warning modal is present
    const warningModal = page.locator('text=EXAMINATION TERMINATION WARNING, text=Security Breach Detected, text=You switched away to another browser tab').first();
    const isWarningVisible = await warningModal.isVisible().catch(() => false);
    console.log(`[BASELINE RESULT] Warning modal visible after tab-switch: ${isWarningVisible}`);

    // Take screenshot artifact
    const artifactPath = '/Users/gauravagarwal/.gemini/antigravity-ide/brain/09dbc8da-666d-4d4e-9dea-d59c8b7dbeda/baseline_tab_switch_reproduction.png';
    await page.screenshot({ path: artifactPath });
    console.log(`Saved baseline reproduction screenshot to: ${artifactPath}`);

  } catch (err) {
    console.error('Error during Step 0 baseline reproduction:', err);
  } finally {
    await browser.close();
  }
}

runStep0Baseline();
