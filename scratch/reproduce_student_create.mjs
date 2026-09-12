import { chromium } from '../frontend/node_modules/playwright-core/index.mjs';

async function reproduce() {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox'],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  
  // Login as admin
  await page.goto('http://localhost:5173/login');
  await page.waitForLoadState('networkidle');
  await page.locator('#identifier').fill('e2e_health_admin@codeguard.test');
  await page.locator('#password').fill('Password123!');
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
  console.log('Logged in successfully! URL:', page.url());

  await page.goto('http://localhost:5173/admin/students');
  await page.waitForLoadState('networkidle');

  // Track network
  page.on('request', req => {
    if (req.url().includes('/api/v1/admin/students')) {
      console.log('\n[NETWORK REQ]:', req.method(), req.url());
      console.log('  PAYLOAD:', req.postData());
    }
  });
  page.on('response', async res => {
    if (res.url().includes('/api/v1/admin/students')) {
      let text = '';
      try { text = await res.text(); } catch (e) {}
      console.log('\n[NETWORK RES]:', res.status(), res.url());
      console.log('  RESPONSE BODY:', text);
    }
  });

  // Click Enroll/Add Student
  const addBtn = page.locator('button:has-text("Enroll Student"), button:has-text("Add Student")').first();
  await addBtn.click();
  await page.waitForSelector('text=Enroll New Student', { timeout: 5000 });

  // Fill form with:
  // First Name: Test
  // Last Name: Student
  // Roll Number: TEST001
  // Email: unique valid email
  const testEmail = `test_single_${Date.now()}@codeguard.test`;
  console.log(`Filling form with First Name: Test, Last Name: Student, Roll: TEST001, Email: ${testEmail}`);
  await page.locator('input[placeholder*="Gaurav"]').fill('Test');
  await page.locator('input[placeholder*="Agarwal"]').fill('Student');
  await page.locator('input[placeholder*="BETN1AI"]').fill('TEST001');
  await page.locator('input[placeholder*="university.edu"]').fill(testEmail);

  // Submit
  console.log('Clicking Create Account...');
  await page.locator('button:has-text("Create Account")').click();
  await page.waitForTimeout(3000);

  const errorBanner = page.locator('div.bg-rose-50');
  if (await errorBanner.isVisible()) {
    console.log('\n>>> ERROR BANNER IS VISIBLE IN UI!');
    console.log('>>> Error Banner Text:', JSON.stringify(await errorBanner.innerText()));
  } else {
    console.log('\n>>> SUCCESS! Modal moved to success state.');
    const successHeader = page.locator('text=Student Account Created');
    console.log('Success header visible:', await successHeader.isVisible());
  }
  await page.screenshot({ path: 'scratch/single_student_reproduce.png' });

  await browser.close();
}

reproduce().catch(err => {
  console.error('Test execution error:', err);
  process.exit(1);
});
