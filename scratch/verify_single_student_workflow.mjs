import { chromium } from '../frontend/node_modules/playwright-core/index.mjs';

async function testSingleStudentWorkflow() {
  console.log('============================================================');
  console.log('STARTING SINGLE STUDENT ACCOUNT CREATION VERIFICATION');
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
    // Step 0: Admin Login
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
    // Step 1: Valid Student Account Creation
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 1: VALID SINGLE STUDENT CREATION');
    console.log('============================================================');
    await page.goto('http://localhost:5173/admin/students');
    await page.waitForLoadState('networkidle');

    const rollNumber1 = `TST${Date.now().toString().slice(-6)}`;
    const email1 = `test_student_${rollNumber1.toLowerCase()}@codeguard.test`;
    const firstName1 = 'Test';
    const lastName1 = 'Student';

    console.log(`Creating student: ${firstName1} ${lastName1}, Roll: ${rollNumber1}, Email: ${email1}`);

    const addBtn = page.locator('button:has-text("Enroll Student"), button:has-text("Add Student")').first();
    await addBtn.click();
    await page.waitForSelector('text=Enroll New Student', { timeout: 5000 });

    await page.locator('input[placeholder*="Gaurav"]').fill(firstName1);
    await page.locator('input[placeholder*="Agarwal"]').fill(lastName1);
    await page.locator('input[placeholder*="BETN1AI"]').fill(rollNumber1);
    await page.locator('input[placeholder*="university.edu"]').fill(email1);

    // Track network request & response
    let createReqPayload = null;
    let createResStatus = null;
    let createResBody = null;

    const reqListener = (req) => {
      if (req.url().includes('/api/v1/admin/students/')) {
        createReqPayload = req.postData();
      }
    };
    const resListener = async (res) => {
      if (res.url().includes('/api/v1/admin/students/')) {
        createResStatus = res.status();
        try { createResBody = await res.text(); } catch (e) {}
      }
    };
    page.on('request', reqListener);
    page.on('response', resListener);

    await page.locator('button:has-text("Create Account")').click();
    await page.waitForTimeout(2000);

    page.off('request', reqListener);
    page.off('response', resListener);

    console.log('\n[NETWORK TRAFFIC]:');
    console.log('  PAYLOAD:', createReqPayload);
    console.log('  STATUS:', createResStatus);
    console.log('  RESPONSE:', createResBody);

    const isSuccessHeaderVisible = await page.locator('text=Student Account Created').isVisible();
    console.log('Modal Success State Visible:', isSuccessHeaderVisible);

    const modalText = await page.locator('div.animate-fade-in').first().innerText();
    console.log('Modal Success Content:\n', modalText.replace(/\n+/g, ' | '));

    await page.screenshot({ path: 'scratch/student_create_success_modal.png' });

    if (!isSuccessHeaderVisible || createResStatus !== 201) {
      throw new Error(`TEST 1 FAILED: Student creation failed with status ${createResStatus}`);
    }

    // Click "Done"
    await page.locator('button:has-text("Done")').click();
    await page.waitForTimeout(2000);

    // Verify student in table
    const tableText = await page.locator('table').innerText();
    const hasStudentInTable = tableText.includes(rollNumber1) && tableText.includes(email1);
    console.log('Student visible in management roster:', hasStudentInTable);
    await page.screenshot({ path: 'scratch/student_roster_verified.png' });

    if (!hasStudentInTable) {
      throw new Error('TEST 1 FAILED: Created student does not appear in table!');
    }
    console.log('>>> TEST 1 PASSED: Single student created and verified in roster.');

    // ------------------------------------------------------------
    // Step 2: Negative Test 1 — Duplicate Roll Number
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 2: NEGATIVE TEST — DUPLICATE ROLL NUMBER');
    console.log('============================================================');
    await addBtn.click();
    await page.waitForSelector('text=Enroll New Student', { timeout: 5000 });

    const duplicateEmail = `another_email_${Date.now()}@codeguard.test`;
    console.log(`Submitting existing Roll: ${rollNumber1} with new Email: ${duplicateEmail}`);
    await page.locator('input[placeholder*="Gaurav"]').fill('Duplicate');
    await page.locator('input[placeholder*="Agarwal"]').fill('Roll');
    await page.locator('input[placeholder*="BETN1AI"]').fill(rollNumber1);
    await page.locator('input[placeholder*="university.edu"]').fill(duplicateEmail);

    await page.locator('button:has-text("Create Account")').click();
    await page.waitForTimeout(2000);

    const errorDiv1 = page.locator('div.bg-rose-50');
    const isError1Visible = await errorDiv1.isVisible();
    const errorText1 = isError1Visible ? await errorDiv1.innerText() : '';
    console.log('Error Banner Visible:', isError1Visible);
    console.log('Error Banner Text:', JSON.stringify(errorText1));

    await page.screenshot({ path: 'scratch/negative_duplicate_roll.png' });

    if (errorText1.trim() === 'A' || !errorText1.includes('already exists')) {
      throw new Error(`TEST 2 FAILED: Expected full error message, got: ${JSON.stringify(errorText1)}`);
    }
    console.log('>>> TEST 2 PASSED: Real error message displayed for duplicate roll number.');

    // Close modal
    await page.locator('button:has-text("Cancel")').first().click();
    await page.waitForTimeout(1000);

    // ------------------------------------------------------------
    // Step 3: Negative Test 2 — Duplicate Email
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 3: NEGATIVE TEST — DUPLICATE EMAIL');
    console.log('============================================================');
    await addBtn.click();
    await page.waitForSelector('text=Enroll New Student', { timeout: 5000 });

    const newRoll = `NEW${Date.now().toString().slice(-6)}`;
    console.log(`Submitting new Roll: ${newRoll} with existing Email: ${email1}`);
    await page.locator('input[placeholder*="Gaurav"]').fill('Duplicate');
    await page.locator('input[placeholder*="Agarwal"]').fill('Email');
    await page.locator('input[placeholder*="BETN1AI"]').fill(newRoll);
    await page.locator('input[placeholder*="university.edu"]').fill(email1);

    await page.locator('button:has-text("Create Account")').click();
    await page.waitForTimeout(2000);

    const errorDiv2 = page.locator('div.bg-rose-50');
    const isError2Visible = await errorDiv2.isVisible();
    const errorText2 = isError2Visible ? await errorDiv2.innerText() : '';
    console.log('Error Banner Visible:', isError2Visible);
    console.log('Error Banner Text:', JSON.stringify(errorText2));

    await page.screenshot({ path: 'scratch/negative_duplicate_email.png' });

    if (errorText2.trim() === 'A' || !errorText2.includes('already exists')) {
      throw new Error(`TEST 3 FAILED: Expected full error message, got: ${JSON.stringify(errorText2)}`);
    }
    console.log('>>> TEST 3 PASSED: Real error message displayed for duplicate email.');

    // Close modal
    await page.locator('button:has-text("Cancel")').first().click();
    await page.waitForTimeout(1000);

    // ------------------------------------------------------------
    // Step 4: Negative Test 3 — Invalid Email Format
    // ------------------------------------------------------------
    console.log('\n============================================================');
    console.log('TEST 4: NEGATIVE TEST — INVALID EMAIL FORMAT');
    console.log('============================================================');
    await addBtn.click();
    await page.waitForSelector('text=Enroll New Student', { timeout: 5000 });

    const newRoll3 = `INV${Date.now().toString().slice(-6)}`;
    console.log(`Submitting Roll: ${newRoll3} with invalid email format 'notanemail'`);
    await page.locator('input[placeholder*="Gaurav"]').fill('Invalid');
    await page.locator('input[placeholder*="Agarwal"]').fill('Email');
    await page.locator('input[placeholder*="BETN1AI"]').fill(newRoll3);
    
    // Bypass browser HTML5 type=email validation to test server-side validator error extraction
    await page.evaluate(() => {
      const input = document.querySelector('input[placeholder*="university.edu"]');
      if (input) {
        input.setAttribute('type', 'text');
        input.value = 'invalidemailformat';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    await page.waitForTimeout(500);

    await page.locator('button:has-text("Create Account")').click();
    await page.waitForTimeout(2000);

    const errorDiv3 = page.locator('div.bg-rose-50');
    const isError3Visible = await errorDiv3.isVisible();
    const errorText3 = isError3Visible ? await errorDiv3.innerText() : '';
    console.log('Error Banner Visible:', isError3Visible);
    console.log('Error Banner Text:', JSON.stringify(errorText3));

    await page.screenshot({ path: 'scratch/negative_invalid_email.png' });

    if (errorText3.trim() === 'A' || (!errorText3.includes('valid email') && !errorText3.includes('email'))) {
      throw new Error(`TEST 4 FAILED: Expected full error message, got: ${JSON.stringify(errorText3)}`);
    }
    console.log('>>> TEST 4 PASSED: Real error message displayed for invalid email format.');

    console.log('\n============================================================');
    console.log('ALL SINGLE STUDENT CREATION TESTS COMPLETED SUCCESSFULLY!');
    console.log('============================================================');

  } catch (err) {
    console.error('\n[TEST EXECUTION ERROR]:', err);
    await page.screenshot({ path: 'scratch/single_student_test_failure.png', fullPage: true }).catch(() => {});
    process.exit(1);
  } finally {
    await browser.close();
  }
}

testSingleStudentWorkflow();
