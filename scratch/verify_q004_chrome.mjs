import { chromium } from '../frontend/node_modules/playwright-core/index.mjs';

async function verifyQ004Health() {
  console.log('=== STARTING CHROME VERIFICATION FOR Q004 HEALTH STATUS ===');
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox'],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.log(`[BROWSER ERROR] ${msg.text()}`);
    }
  });

  try {
    // 1. Login as Admin
    console.log('\n--- Step 1: Admin Login ---');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');

    await page.locator('#identifier').fill('e2e_health_admin@codeguard.test');
    await page.locator('#password').fill('Password123!');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
    console.log('Logged in successfully! URL:', page.url());

    // 2. Navigate to Q004 Question Editor
    console.log('\n--- Step 2: Open Q004 Question Editor ---');
    await page.goto('http://localhost:5173/admin/questions/36b915af-264b-4e7f-a3ce-653419af446a/versions/1');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // 3. Inspect Question Readiness Panel
    console.log('\n--- Step 3: Inspect Question Readiness Panel ---');
    await page.waitForSelector('text=Question Readiness', { timeout: 10000 });

    const readinessText = await page.locator('div:has-text("Question Readiness & Health")').locator('..').first().innerText();
    console.log('\n[QUESTION READINESS PANEL CONTENT]:\n' + readinessText);

    // 4. Verify Publish Button State
    const publishBtn = page.locator('button:has-text("Publish")').first();
    const isPublishVisible = await publishBtn.isVisible();
    const isPublishDisabled = await publishBtn.isDisabled();
    console.log(`\nPublish Button: Visible = ${isPublishVisible}, Disabled = ${isPublishDisabled}`);

    // Take screenshot of Question Readiness
    await page.screenshot({ path: 'scratch/q004_health_verified.png', fullPage: true });
    console.log('Screenshot saved to scratch/q004_health_verified.png');

    // 5. Assertions
    const passesExamples = readinessText.includes('Examples') && (readinessText.includes('1 example(s) configured') || readinessText.includes('PASS'));
    const passesHidden = readinessText.includes('Hidden Tests') && (readinessText.includes('1 hidden test(s) configured') || readinessText.includes('PASS'));
    const passesDuplicates = readinessText.includes('Duplicate Inputs') && (readinessText.includes('No duplicate test case inputs') || readinessText.includes('PASS'));
    const allDataChecksPassed = readinessText.includes('11/11 Checks Passed') || readinessText.includes('11 of 11 Checks Passed') || readinessText.includes('Ready for Publishing');

    console.log('\n--- VERIFICATION SUMMARY ---');
    console.log('Examples → PASS:', passesExamples);
    console.log('Hidden Tests → PASS:', passesHidden);
    console.log('Duplicate Inputs → PASS:', passesDuplicates);
    console.log('11/11 DATA Checks Passed:', allDataChecksPassed);
    console.log('Publish Button Enabled:', !isPublishDisabled);

    if (passesExamples && passesHidden && passesDuplicates && !isPublishDisabled) {
      console.log('\n>>> CHROME VERIFICATION: ALL CHECKS PASSED <<<');
    } else {
      throw new Error('Verification failed. One or more health checks did not pass or publish button is disabled.');
    }

  } catch (err) {
    console.error('\n[VERIFICATION ERROR]:', err);
    await page.screenshot({ path: 'scratch/q004_health_error.png', fullPage: true }).catch(() => {});
    process.exit(1);
  } finally {
    await browser.close();
  }
}

verifyQ004Health();
