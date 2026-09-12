import { execSync } from 'child_process';
import { chromium } from '../frontend/node_modules/playwright-core/index.mjs';

function clearBackendRateLimit() {
  try {
    execSync('../.venv/bin/python manage.py shell -c "from django.core.cache import cache; cache.clear()"', {
      cwd: '/Users/gauravagarwal/Documents/Exam Website /backend',
      stdio: 'pipe',
    });
  } catch (e) {
    console.warn('Warning: Could not clear backend cache:', e.message);
  }
}

async function verifyStep1Python() {
  console.log('=== STARTING REAL BROWSER STEP 1 (PYTHON RUN CODE) ===');
  clearBackendRateLimit();

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
    permissions: ['camera', 'microphone'],
  });
  const page = await context.newPage();

  // Track network events
  page.on('request', (req) => {
    if (req.url().includes('/run/') || req.url().includes('/submissions/')) {
      console.log(`\n[NETWORK REQ] ${req.method()} ${req.url()}`);
      if (req.postData()) {
        console.log(`[REQ BODY] ${req.postData()}`);
      }
    }
  });

  page.on('response', async (res) => {
    if (res.url().includes('/run/') || res.url().includes('/submissions/')) {
      try {
        const body = await res.json();
        console.log(`[NETWORK RES ${res.status()}] ${res.url()}`);
        console.log(`[RES BODY]`, JSON.stringify(body, null, 2));
      } catch (e) {
        console.log(`[NETWORK RES ${res.status()}] ${res.url()}`);
      }
    }
  });

  try {
    // 1. Login
    console.log('\n--- Step 1: Login ---');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');
    await page.locator('#identifier').fill('vikultomar@gmail.com');
    await page.locator('#password').fill('Password123!');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
    console.log('Successfully logged in! Current URL:', page.url());

    // 2. Navigate to Assessment Room
    console.log('\n--- Step 2: Navigate to Assessment Room ---');
    await page.goto('http://localhost:5173/student/room/11e53f38-3c1d-46c0-a05e-519fb4742209');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 3. Navigate to Coding Question (Q3)
    console.log('\n--- Step 3: Navigate to Coding Question ---');
    const q3Btn = page.locator('button:has-text("3"), button:has-text("Q3"), [data-testid="question-nav-3"]').first();
    if (await q3Btn.isVisible()) {
      await q3Btn.click();
    } else {
      const navButtons = page.locator('div.grid button, div.flex button:has-text("Next")');
      const count = await navButtons.count();
      for (let i = 0; i < count; i++) {
        const btn = navButtons.nth(i);
        const text = await btn.innerText();
        if (text.trim() === '3') {
          await btn.click();
          break;
        }
      }
    }
    await page.waitForTimeout(1500);

    // 4. Select Python
    console.log('\n--- Step 4: Select Python Language ---');
    const select = page.locator('select').first();
    await select.waitFor({ state: 'visible' });
    await select.selectOption({ value: 'PYTHON' });
    await page.waitForTimeout(1000);

    // 5. Enter Code: print("HELLO CODEGUARD")
    console.log('\n--- Step 5: Enter Code in Monaco Editor ---');
    await page.waitForFunction(() => Boolean(window.monacoEditor), { timeout: 15000 });
    await page.evaluate(() => {
      if (window.monacoEditor) {
        window.monacoEditor.setValue('print("HELLO CODEGUARD")');
      }
    });
    await page.waitForTimeout(1500);

    // 6. Click Run Code
    console.log('\n--- Step 6: Click Run Code ---');
    const runBtn = page.locator('button:has-text("Run Code")');
    await runBtn.click();
    console.log('Clicked "Run Code", waiting for backend & Piston execution...');

    // 7. Wait for UI Result
    await page.waitForSelector('text=Sample Test Run Output', { timeout: 20000 });
    await page.waitForTimeout(2500);

    const consoleText = await page.locator('div:has-text("Sample Test Run Output")').locator('..').first().innerText();
    console.log('\n[UI RESULT CONSOLE]:\n' + consoleText);

    // Take screenshot of student UI
    await page.screenshot({ path: 'scratch/step1_python_browser_result.png', fullPage: true });
    console.log('Screenshot saved to scratch/step1_python_browser_result.png');

    // 8. Verify Output
    if (consoleText.includes('HELLO CODEGUARD')) {
      console.log('\n>>> STEP 1 (PYTHON RUN CODE): PASSED <<<');
    } else {
      throw new Error('Expected "HELLO CODEGUARD" in output console, but was not found.');
    }

  } catch (err) {
    console.error('\n[STEP 1 ERROR]:', err);
    await page.screenshot({ path: 'scratch/step1_error.png', fullPage: true }).catch(() => {});
    process.exit(1);
  } finally {
    await browser.close();
  }
}

verifyStep1Python();
