import { chromium } from '../frontend/node_modules/playwright-core/index.mjs';

async function runAcceptanceTests() {
  console.log('============================================================');
  console.log('STARTING CHROME ACCEPTANCE TESTS: GOLDEN WORKFLOW FIX');
  console.log('============================================================\n');

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
    // ------------------------------------------------------------
    // LOGIN
    // ------------------------------------------------------------
    console.log('--- Step 0: Admin Login ---');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');

    await page.locator('#identifier').fill('e2e_health_admin@codeguard.test');
    await page.locator('#password').fill('Password123!');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
    console.log('Logged in successfully! URL:', page.url());

    // ------------------------------------------------------------
    // TEST 1 — QUESTION BANK HEALTH DISPLAY
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 1 — QUESTION BANK HEALTH DISPLAY');
    console.log('============================================================');
    await page.goto('http://localhost:5173/admin/questions');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const tableText = await page.locator('table').innerText();
    const hasIssuesText = tableText.includes('Issues');
    console.log('Contains "Issues" text in Question Bank:', hasIssuesText);
    if (hasIssuesText) {
      throw new Error('TEST 1 FAILED: Question Bank is displaying "Issues" badge!');
    }

    const q004Row = page.locator('tr:has-text("Print Hello World")').first();
    const q004Text = await q004Row.innerText();
    console.log('Q004 Question Row Text:\n', q004Text.replace(/\n+/g, ' | '));

    await page.screenshot({ path: 'scratch/test1_question_bank_health.png', fullPage: true });
    console.log('Screenshot saved to scratch/test1_question_bank_health.png');
    console.log('>>> TEST 1 PASSED: Question Bank displays healthy / ready status without "Issues" label.');

    // Helper for datetime-local
    const now = new Date();
    const pad = (n) => n.toString().padStart(2, '0');
    const formatDT = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    const startDT = formatDT(now);
    const endDT = formatDT(new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000));

    // ------------------------------------------------------------
    // TEST 2 — MANUAL CANDIDATES PUBLISH FLOW
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 2 — MANUAL CANDIDATES PUBLISH FLOW');
    console.log('============================================================');
    await page.goto('http://localhost:5173/admin/assessments/create');
    await page.waitForLoadState('networkidle');

    const test2Title = `E2E Manual Students Exam ${Date.now()}`;
    await page.locator('input[placeholder*="Exam"], input[name="title"], input[id="title"]').first().fill(test2Title);
    await page.locator('textarea').first().fill('Assessment testing manual student candidate assignment.');
    
    await page.locator('input[type="datetime-local"]').first().fill(startDT);
    await page.locator('input[type="datetime-local"]').nth(1).fill(endDT);

    const durationInput2 = page.locator('label:has-text("Duration")').locator('..').locator('input[type="number"]');
    if (await durationInput2.count() > 0) {
      await durationInput2.fill('60');
    }
    const pointsInput2 = page.locator('label:has-text("Total Points")').locator('..').locator('input[type="number"]');
    if (await pointsInput2.count() > 0) {
      await pointsInput2.fill('10');
    }

    await page.locator('button:has-text("Save Draft"), button:has-text("Create Draft Assessment")').first().click();
    await page.waitForURL((url) => url.pathname.match(/\/admin\/assessments\/[0-9a-f-]+$/), { timeout: 10000 });
    const test2Url = page.url();
    const test2Id = test2Url.split('/').pop();
    console.log(`Created Draft Assessment: ID=${test2Id}, URL=${test2Url}`);

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Add Q004 to Assessment
    console.log('Adding Q004 (10 pts) to Assessment...');
    await page.locator('button:has-text("Add Question")').click();
    await page.waitForSelector('text=Select Question for Assessment', { timeout: 5000 });
    await page.waitForTimeout(1000);

    const q004PickerItem2 = page.locator('div:has-text("Print Hello World")').locator('..').first();
    await q004PickerItem2.click();
    await page.waitForTimeout(500);
    await page.locator('button:has-text("Add to Assessment")').click();
    await page.waitForTimeout(1500);
    console.log('Q004 added to assessment.');

    // Configure Specific Candidates Mode
    console.log('Selecting "Selected Candidates Only" mode...');
    const specificRadio = page.locator('button:has-text("Selected Candidates Only")');
    await specificRadio.click();
    await page.waitForTimeout(1000);

    // Open Student Picker and add candidate
    console.log('Opening Student Picker to select individual candidate...');
    const addCandidatesBtn = page.locator('button:has-text("+ Add Candidates")');
    await addCandidatesBtn.click();
    await page.waitForTimeout(1000);

    // Click "+ Add" on the first student
    const addStudentBtn = page.locator('button:has-text("+ Add")').first();
    await addStudentBtn.click();
    await page.waitForTimeout(1000);

    // Save candidates
    await page.locator('button:has-text("Save Candidates")').click();
    await page.waitForTimeout(2000);
    console.log('Manual candidate saved.');

    // Capture network during Publish
    const test2PublishReqs = [];
    const test2ReqListener = (req) => {
      if (req.url().includes(test2Id)) {
        test2PublishReqs.push({ type: 'REQ', method: req.method(), url: req.url(), data: req.postData() });
      }
    };
    const test2ResListener = async (res) => {
      if (res.url().includes(test2Id)) {
        let body = '';
        try { body = await res.text(); } catch (e) {}
        test2PublishReqs.push({ type: 'RES', status: res.status(), url: res.url(), body });
      }
    };
    page.on('request', test2ReqListener);
    page.on('response', test2ResListener);

    // Click "Publish Examination" -> "Confirm & Publish"
    console.log('Opening Publish modal and confirming publish...');
    await page.locator('button:has-text("Publish Assessment")').click();
    await page.waitForSelector('text=Confirm candidate enrollment', { timeout: 5000 });
    await page.waitForTimeout(1000);

    await page.screenshot({ path: 'scratch/test2_manual_publish_modal.png' });

    await page.locator('button:has-text("Confirm & Publish")').click();
    await page.waitForTimeout(3000);

    page.off('request', test2ReqListener);
    page.off('response', test2ResListener);

    console.log('\n[TEST 2 NETWORK TRAFFIC]:');
    for (const item of test2PublishReqs) {
      console.log(`  ${item.type} [${item.method || item.status}] ${item.url}`);
      if (item.data) console.log(`    PAYLOAD: ${item.data}`);
      if (item.body) console.log(`    RESPONSE: ${item.body.slice(0, 250)}...`);
    }

    const isPublished2 = await page.locator('span:has-text("PUBLISHED"), div:has-text("PUBLISHED")').first().isVisible();
    console.log('Assessment Status is PUBLISHED:', isPublished2);
    await page.screenshot({ path: 'scratch/test2_manual_published_result.png', fullPage: true });

    if (!isPublished2) {
      throw new Error('TEST 2 FAILED: Assessment did not transition to PUBLISHED!');
    }
    console.log('>>> TEST 2 PASSED: Manual Student Publishing succeeded.');

    // ------------------------------------------------------------
    // TEST 3 — ALL STUDENTS PUBLISH FLOW
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 3 — ALL STUDENTS PUBLISH FLOW');
    console.log('============================================================');
    await page.goto('http://localhost:5173/admin/assessments/create');
    await page.waitForLoadState('networkidle');

    const test3Title = `E2E All Students Exam ${Date.now()}`;
    await page.locator('input[placeholder*="Exam"], input[name="title"], input[id="title"]').first().fill(test3Title);
    await page.locator('textarea').first().fill('Assessment testing All Students candidate assignment.');
    
    await page.locator('input[type="datetime-local"]').first().fill(startDT);
    await page.locator('input[type="datetime-local"]').nth(1).fill(endDT);

    const durationInput3 = page.locator('label:has-text("Duration")').locator('..').locator('input[type="number"]');
    if (await durationInput3.count() > 0) {
      await durationInput3.fill('60');
    }
    const pointsInput3 = page.locator('label:has-text("Total Points")').locator('..').locator('input[type="number"]');
    if (await pointsInput3.count() > 0) {
      await pointsInput3.fill('10');
    }

    await page.locator('button:has-text("Save Draft"), button:has-text("Create Draft Assessment")').first().click();
    await page.waitForURL((url) => url.pathname.match(/\/admin\/assessments\/[0-9a-f-]+$/), { timeout: 10000 });
    const test3Url = page.url();
    const test3Id = test3Url.split('/').pop();
    console.log(`Created Draft Assessment: ID=${test3Id}, URL=${test3Url}`);

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Add Q004 to Assessment
    console.log('Adding Q004 (10 pts) to Assessment...');
    await page.locator('button:has-text("Add Question")').click();
    await page.waitForSelector('text=Select Question for Assessment', { timeout: 5000 });
    await page.waitForTimeout(1000);

    const q004PickerItem3 = page.locator('div:has-text("Print Hello World")').locator('..').first();
    await q004PickerItem3.click();
    await page.waitForTimeout(500);
    await page.locator('button:has-text("Add to Assessment")').click();
    await page.waitForTimeout(1500);

    // Ensure "All Students" is selected
    console.log('Selecting "All Students" mode...');
    const allStudentsRadio = page.locator('button:has-text("All Students in System"), button:has-text("All Students")').first();
    await allStudentsRadio.click();
    await page.waitForTimeout(1000);

    // Save candidates
    await page.locator('button:has-text("Save Candidates")').click();
    await page.waitForTimeout(2000);
    console.log('All Students candidate targeting saved.');

    // Capture network during Publish
    const test3PublishReqs = [];
    const test3ReqListener = (req) => {
      if (req.url().includes(test3Id)) {
        test3PublishReqs.push({ type: 'REQ', method: req.method(), url: req.url(), data: req.postData() });
      }
    };
    const test3ResListener = async (res) => {
      if (res.url().includes(test3Id)) {
        let body = '';
        try { body = await res.text(); } catch (e) {}
        test3PublishReqs.push({ type: 'RES', status: res.status(), url: res.url(), body });
      }
    };
    page.on('request', test3ReqListener);
    page.on('response', test3ResListener);

    // Click "Publish Examination" -> "Confirm & Publish"
    console.log('Opening Publish modal for All Students and confirming publish...');
    await page.locator('button:has-text("Publish Assessment")').click();
    await page.waitForSelector('text=Confirm candidate enrollment', { timeout: 5000 });
    await page.waitForTimeout(1000);

    await page.screenshot({ path: 'scratch/test3_all_students_publish_modal.png' });

    await page.locator('button:has-text("Confirm & Publish")').click();
    await page.waitForTimeout(3000);

    page.off('request', test3ReqListener);
    page.off('response', test3ResListener);

    console.log('\n[TEST 3 NETWORK TRAFFIC]:');
    for (const item of test3PublishReqs) {
      console.log(`  ${item.type} [${item.method || item.status}] ${item.url}`);
      if (item.data) console.log(`    PAYLOAD: ${item.data}`);
      if (item.body) console.log(`    RESPONSE: ${item.body.slice(0, 250)}...`);
    }

    const isPublished3 = await page.locator('span:has-text("PUBLISHED"), div:has-text("PUBLISHED")').first().isVisible();
    console.log('Assessment Status is PUBLISHED:', isPublished3);
    await page.screenshot({ path: 'scratch/test3_all_students_published_result.png', fullPage: true });

    if (!isPublished3) {
      throw new Error('TEST 3 FAILED: All Students Assessment did not transition to PUBLISHED!');
    }
    console.log('>>> TEST 3 PASSED: All Students Publishing succeeded.');

    // ------------------------------------------------------------
    // TEST 4 — FAILURE SAFETY
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 4 — FAILURE SAFETY');
    console.log('============================================================');
    await page.goto('http://localhost:5173/admin/assessments/create');
    await page.waitForLoadState('networkidle');

    const test4Title = `E2E Failure Safety Exam ${Date.now()}`;
    await page.locator('input[placeholder*="Exam"], input[name="title"], input[id="title"]').first().fill(test4Title);
    await page.locator('textarea').first().fill('Assessment testing failure safety validation.');

    await page.locator('input[type="datetime-local"]').first().fill(startDT);
    await page.locator('input[type="datetime-local"]').nth(1).fill(endDT);

    const durationInput4 = page.locator('label:has-text("Duration")').locator('..').locator('input[type="number"]');
    if (await durationInput4.count() > 0) {
      await durationInput4.fill('60');
    }
    const pointsInput4 = page.locator('label:has-text("Total Points")').locator('..').locator('input[type="number"]');
    if (await pointsInput4.count() > 0) {
      await pointsInput4.fill('10');
    }

    await page.locator('button:has-text("Save Draft"), button:has-text("Create Draft Assessment")').first().click();
    await page.waitForURL((url) => url.pathname.match(/\/admin\/assessments\/[0-9a-f-]+$/), { timeout: 10000 });
    const test4Id = page.url().split('/').pop();
    console.log(`Created Draft Assessment: ID=${test4Id}`);

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Add Q004 (10 pts) -> points match (10 == 10)
    await page.locator('button:has-text("Add Question")').click();
    await page.waitForSelector('text=Select Question for Assessment', { timeout: 5000 });
    await page.waitForTimeout(1000);
    await page.locator('div:has-text("Print Hello World")').locator('..').first().click();
    await page.waitForTimeout(500);
    await page.locator('button:has-text("Add to Assessment")').click();
    await page.waitForTimeout(1500);

    // Select "All Students" and save candidates
    const allStudentsRadio4 = page.locator('button:has-text("All Students in System"), button:has-text("All Students")').first();
    await allStudentsRadio4.click();
    await page.waitForTimeout(1000);
    await page.locator('button:has-text("Save Candidates")').click();
    await page.waitForTimeout(2000);

    // Open Publish modal
    console.log('Opening Publish modal...');
    await page.locator('button:has-text("Publish Assessment")').click();
    await page.waitForSelector('text=Confirm candidate enrollment', { timeout: 5000 });
    await page.waitForTimeout(1000);

    // Intercept backend publish endpoint to simulate safe backend rejection
    await page.route(`**/api/v1/admin/assessments/${test4Id}/publish/`, async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'error',
          message: 'Server rejection: Assessment fails publication safety validation invariant.',
        }),
      });
    });

    console.log('Clicking Confirm & Publish with backend rejection route active...');
    await page.locator('button:has-text("Confirm & Publish")').click();
    await page.waitForTimeout(2000);

    const isModalStillOpen = await page.locator('text=Confirm candidate enrollment').isVisible();
    const isErrorVisible = await page.locator('text=Publication failed').isVisible();
    const errorText = await page.locator('div.bg-rose-50').first().innerText().catch(() => 'No error div');
    console.log('Modal remains open:', isModalStillOpen);
    console.log('Error banner visible:', isErrorVisible);
    console.log('Error content:', errorText.replace(/\n+/g, ' | '));

    await page.screenshot({ path: 'scratch/test4_failure_safety_modal.png' });

    if (!isModalStillOpen || !isErrorVisible) {
      throw new Error('TEST 4 FAILED: Modal closed or error was hidden upon failure!');
    }
    console.log('>>> TEST 4 PASSED: Failure safety kept modal open and displayed server error.');

    console.log('\n============================================================');
    console.log('ALL 4 CHROME ACCEPTANCE TESTS COMPLETED SUCCESSFULLY!');
    console.log('============================================================');

  } catch (err) {
    console.error('\n[TEST EXECUTION ERROR]:', err);
    await page.screenshot({ path: 'scratch/acceptance_test_failure.png', fullPage: true }).catch(() => {});
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runAcceptanceTests();
