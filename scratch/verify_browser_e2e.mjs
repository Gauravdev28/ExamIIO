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

async function runVerification() {
  console.log('=== STARTING REAL BROWSER E2E VERIFICATION ===');
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

  // Network logs listener
  page.on('request', (req) => {
    if (req.url().includes('/run/') || req.url().includes('/submissions/') || req.url().includes('/submit/')) {
      console.log(`\n[NETWORK REQ] ${req.method()} ${req.url()}`);
      if (req.postData()) {
        console.log(`[REQ BODY] ${req.postData()}`);
      }
    }
  });

  page.on('response', async (res) => {
    if (res.url().includes('/run/') || res.url().includes('/submissions/') || res.url().includes('/submit/')) {
      try {
        const body = await res.json();
        console.log(`[NETWORK RES ${res.status()}] ${res.url()}`);
        console.log(`[RES BODY]`, JSON.stringify(body, null, 2));
      } catch (e) {
        console.log(`[NETWORK RES ${res.status()}] ${res.url()}`);
      }
    }
  });

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.log(`[BROWSER CONSOLE ERROR] ${msg.text()}`);
    }
  });

  try {
    // 1. Go to login
    console.log('\n--- Step 1: Login ---');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');

    await page.locator('#identifier').fill('vikultomar@gmail.com');
    await page.locator('#password').fill('Password123!');
    await page.locator('button[type="submit"]').click();
    console.log('Submitted login credentials, waiting for redirect...');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
    console.log('Successfully logged in! Current URL:', page.url());

    // 2. Go to Test Room
    console.log('\n--- Step 2: Navigate to Test Room ---');
    await page.goto('http://localhost:5173/student/room/11e53f38-3c1d-46c0-a05e-519fb4742209');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 3. Navigate to Question 3 (Coding question)
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

    // Helper to select language dropdown
    async function selectLanguage(lang) {
      const select = page.locator('select').first();
      await select.waitFor({ state: 'visible' });
      await select.selectOption({ value: lang });
      await page.waitForTimeout(1000);
    }

    // Helper to cleanly set code in Monaco Editor
    async function setEditorCode(code) {
      await page.waitForFunction(() => Boolean(window.monacoEditor), { timeout: 15000 });
      await page.evaluate((newCode) => {
        if (window.monacoEditor) {
          window.monacoEditor.setValue(newCode);
        }
      }, code);
      await page.waitForTimeout(1500);
    }

    // Helper to click Run Code and wait for result
    async function clickRunCodeAndWait() {
      clearBackendRateLimit();
      const runBtn = page.locator('button:has-text("Run Code")');
      await runBtn.click();
      console.log('Clicked "Run Code", waiting for execution...');

      // Wait for execution result container
      await page.waitForSelector('text=Sample Test Run Output', { timeout: 20000 });
      await page.waitForTimeout(2500);

      // Extract stdout / result container text
      const consoleText = await page.locator('div:has-text("Sample Test Run Output")').locator('..').first().innerText();
      console.log('\n[UI RESULT CONSOLE]:\n' + consoleText);
      return consoleText;
    }

    const results = {};

    // --- TEST 1: Python ---
    console.log('\n==============================');
    console.log('TEST 1: Python Run Code');
    console.log('==============================');
    await selectLanguage('PYTHON');
    await setEditorCode('print("CODEGUARD_E2E_PYTHON")');
    const pyOutput = await clickRunCodeAndWait();
    if (pyOutput.includes('CODEGUARD_E2E_PYTHON')) {
      console.log('>>> TEST 1 (PYTHON): PASSED <<<');
      results.python = true;
    } else {
      console.error('>>> TEST 1 (PYTHON): FAILED <<<');
      results.python = false;
    }

    // --- TEST 2: C++ ---
    console.log('\n==============================');
    console.log('TEST 2: C++ Run Code');
    console.log('==============================');
    await selectLanguage('CPP');
    await setEditorCode('#include <iostream>\nint main() {\n    std::cout << "CODEGUARD_CPP_TRACE";\n    return 0;\n}');
    const cppOutput = await clickRunCodeAndWait();
    if (cppOutput.includes('CODEGUARD_CPP_TRACE')) {
      console.log('>>> TEST 2 (C++): PASSED <<<');
      results.cpp = true;
    } else {
      console.error('>>> TEST 2 (C++): FAILED <<<');
      results.cpp = false;
    }

    // --- TEST 3: Java ---
    console.log('\n==============================');
    console.log('TEST 3: Java Run Code');
    console.log('==============================');
    await selectLanguage('JAVA');
    await setEditorCode('public class Main {\n    public static void main(String[] args) {\n        System.out.println("CODEGUARD_JAVA_TRACE");\n    }\n}');
    const javaOutput = await clickRunCodeAndWait();
    if (javaOutput.includes('CODEGUARD_JAVA_TRACE')) {
      console.log('>>> TEST 3 (JAVA): PASSED <<<');
      results.java = true;
    } else {
      console.error('>>> TEST 3 (JAVA): FAILED <<<');
      results.java = false;
    }

    // --- TEST 4: C ---
    console.log('\n==============================');
    console.log('TEST 4: C Run Code');
    console.log('==============================');
    await selectLanguage('C');
    await setEditorCode('#include <stdio.h>\nint main() {\n    printf("CODEGUARD_C_TRACE");\n    return 0;\n}');
    const cOutput = await clickRunCodeAndWait();
    if (cOutput.includes('CODEGUARD_C_TRACE')) {
      console.log('>>> TEST 4 (C): PASSED <<<');
      results.c = true;
    } else {
      console.error('>>> TEST 4 (C): FAILED <<<');
      results.c = false;
    }

    // --- TEST 5: Python Solution with Stdin ---
    console.log('\n==============================');
    console.log('TEST 5: Python Solution with Stdin');
    console.log('==============================');
    await selectLanguage('PYTHON');
    await setEditorCode('n = int(input())\narr = list(map(int, input().split()))\nans = arr[0]\nfor x in arr:\n    if x > ans:\n        ans = x\nprint(ans)');
    const stdinOutput = await clickRunCodeAndWait();
    if (stdinOutput.includes('Passed: 2 / 2') || (stdinOutput.includes('PASSED') && stdinOutput.includes('9'))) {
      console.log('>>> TEST 5 (STDIN SOLUTION): PASSED <<<');
      results.stdin = true;
    } else {
      console.error('>>> TEST 5 (STDIN SOLUTION): FAILED <<<');
      results.stdin = false;
    }

    console.log('\n==============================');
    console.log('FINAL REAL BROWSER SUMMARY:');
    console.log(JSON.stringify(results, null, 2));
    console.log('==============================');

    const allPassed = Object.values(results).every(Boolean);
    if (!allPassed) {
      process.exit(1);
    }
  } catch (err) {
    console.error('\n[TEST ERROR]:', err);
    await page.screenshot({ path: 'scratch/browser_test_error.png', fullPage: true }).catch(() => {});
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runVerification();

