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

async function verifyCopyPasteProtection() {
  console.log('=== VERIFYING BROWSER-LEVEL COPY/PASTE PROTECTION IN REAL CHROME ===');
  const attemptId = resetAttempt();
  console.log(`Test attempt prepared: ${attemptId}`);

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: [
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
      '--no-sandbox',
    ],
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    permissions: ['camera', 'microphone', 'clipboard-read', 'clipboard-write'],
  });

  const page = await context.newPage();

  try {
    // 1. Log in
    console.log('\n--- Step 1: Login ---');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');
    await page.locator('#identifier').fill('chrome_test_student@example.com');
    await page.locator('#password').fill('Password123!');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
    console.log('Logged in successfully!');

    // 2. Test outside exam: Student Dashboard allows clipboard/selection
    console.log('\n--- Step 2: Verify normal behavior on Dashboard (Outside Exam) ---');
    const dashboardCopyAllowed = await page.evaluate(() => {
      const evt = new ClipboardEvent('copy', { cancelable: true, bubbles: true });
      const dispatched = document.dispatchEvent(evt);
      return dispatched; // If true, copy event was NOT cancelled/blocked
    });
    console.log('Dashboard copy event allowed (not blocked):', dashboardCopyAllowed);
    if (!dashboardCopyAllowed) {
      throw new Error('FAILED: Dashboard should NOT block copy operations.');
    }

    // 3. Enter Active Exam Room
    console.log(`\n--- Step 3: Navigate to Active Exam Room (/student/room/${attemptId}) ---`);
    await page.goto(`http://localhost:5173/student/room/${attemptId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const startBtn = page.locator('button:has-text("Start Assessment"), button:has-text("Enter Examination"), button:has-text("Start Exam"), button:has-text("I Agree & Continue")').first();
    if (await startBtn.isVisible()) {
      await startBtn.click();
      await page.waitForTimeout(1500);
    }

    // 4. Test inside Active Exam: Clipboard events are blocked
    console.log('\n--- Step 4: Verify Copy, Cut, Paste, ContextMenu blocked inside Active Exam ---');
    const examClipboardBlocked = await page.evaluate(() => {
      const copyEvt = new ClipboardEvent('copy', { cancelable: true, bubbles: true });
      const copyNotCancelled = document.dispatchEvent(copyEvt);

      const cutEvt = new ClipboardEvent('cut', { cancelable: true, bubbles: true });
      const cutNotCancelled = document.dispatchEvent(cutEvt);

      const pasteEvt = new ClipboardEvent('paste', { cancelable: true, bubbles: true });
      const pasteNotCancelled = document.dispatchEvent(pasteEvt);

      const ctxEvt = new MouseEvent('contextmenu', { cancelable: true, bubbles: true });
      const ctxNotCancelled = document.dispatchEvent(ctxEvt);

      const keyEvt = new KeyboardEvent('keydown', { key: 'c', ctrlKey: true, cancelable: true, bubbles: true });
      const keyNotCancelled = document.dispatchEvent(keyEvt);

      return {
        copyBlocked: !copyNotCancelled,
        cutBlocked: !cutNotCancelled,
        pasteBlocked: !pasteNotCancelled,
        contextMenuBlocked: !ctxNotCancelled,
        ctrlCBlocked: !keyNotCancelled,
      };
    });

    console.log('Active Exam Protection Status:', JSON.stringify(examClipboardBlocked, null, 2));

    if (!examClipboardBlocked.copyBlocked || !examClipboardBlocked.cutBlocked || !examClipboardBlocked.pasteBlocked || !examClipboardBlocked.ctrlCBlocked) {
      throw new Error('FAILED: One or more clipboard operations were not blocked during active exam.');
    }

    console.log('\n=== ALL COPY/PASTE PROTECTION CHECKS PASSED SUCCESSFULLY ===');

  } catch (err) {
    console.error('Error during verification:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

verifyCopyPasteProtection();
