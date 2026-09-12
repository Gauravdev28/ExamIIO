import { chromium } from '/Users/gauravagarwal/Documents/Exam Website /frontend/node_modules/playwright-core/index.mjs';

async function runPhase6BrowserVerification() {
  console.log('--- Launching Browser for Phase 6 C Language UI Verification ---');
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  let dialogTriggered = false;
  page.on('dialog', (dialog) => {
    dialogTriggered = true;
    console.log(`[ALERT DETECTED]: ${dialog.message()}`);
    dialog.dismiss();
  });

  try {
    // 1. Log in
    console.log('[Step 1] Logging in as admin...');
    await page.goto('http://localhost:5173/login');
    await page.waitForLoadState('networkidle');
    await page.locator('#identifier').fill('admin@codeguard.local');
    await page.locator('#password').fill('AdminSecure123!');
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
    console.log('✓ Successfully logged in');

    // 2. Navigate to Create Coding Question
    console.log('[Step 2] Navigating to /admin/questions/create?type=CODING...');
    await page.goto('http://localhost:5173/admin/questions/create?type=CODING');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('text=Coding Configuration', { timeout: 10000 });
    console.log('✓ Question Editor Page loaded with Coding Configuration');

    // 3. Verify all 4 checkboxes are visible and checked
    console.log('[Step 3] Verifying language checkboxes...');
    const langLabels = ['Python', 'C++', 'Java', 'C'];
    for (const label of langLabels) {
      const checkbox = page.getByRole('checkbox', { name: label, exact: true });
      const isVisible = await checkbox.isVisible();
      const isChecked = await checkbox.isChecked();
      console.log(`  - ${label}: visible=${isVisible}, checked=${isChecked}`);
      if (!isVisible || !isChecked) {
        throw new Error(`Expected ${label} checkbox to be visible and checked by default for new questions`);
      }
    }
    console.log('✓ All 4 language checkboxes (Python, C++, Java, C) are present and checked');

    // 4. Verify minimal templates in Monaco Editor
    console.log('[Step 4] Verifying minimal starter templates for each language...');
    const selectDropdown = page.locator('label:has-text("Starter Code Language:") ~ select');
    const expectedSnippets = {
      PYTHON: 'def solve():',
      CPP: '#include <bits/stdc++.h>',
      JAVA: 'import java.io.*;',
      C: '#include <stdio.h>',
    };

    for (const [lang, snippet] of Object.entries(expectedSnippets)) {
      await selectDropdown.selectOption(lang);
      await page.waitForTimeout(600);
      const rawText = await page.locator('.monaco-editor').first().innerText();
      const editorText = rawText.replace(/\u00a0/g, ' ');
      const hasSnippet = editorText.includes(snippet);
      console.log(`  - ${lang} contains "${snippet}": ${hasSnippet}`);
      if (!hasSnippet) {
        throw new Error(`Monaco editor for ${lang} does not contain minimal template snippet "${snippet}" (got: ${JSON.stringify(rawText)})`);
      }
    }
    console.log('✓ All 4 languages have minimal starter templates');

    // 5. Test Rule 1 & Rule 2 (Fallback on Disable)
    console.log('[Step 5] Testing language toggle rules (Rule 1 & 2)...');
    // Currently C is selected in dropdown
    // Uncheck C checkbox
    const cCheckbox = page.getByRole('checkbox', { name: 'C', exact: true });
    await cCheckbox.click();
    await page.waitForTimeout(300);
    // Active should have fallen back to Python (updated[0])
    const newActiveVal = await selectDropdown.inputValue();
    console.log(`  - After unchecking C, active starter language is: ${newActiveVal}`);
    if (newActiveVal !== 'PYTHON') {
      throw new Error(`Expected active language to fall back to PYTHON, got ${newActiveVal}`);
    }

    // 6. Test Rule 3 (Zero Enabled State without alert)
    console.log('[Step 6] Testing Rule 3 (Zero Enabled State)...');
    const pyCheckbox = page.getByRole('checkbox', { name: 'Python', exact: true });
    const cppCheckbox = page.getByRole('checkbox', { name: 'C++', exact: true });
    const javaCheckbox = page.getByRole('checkbox', { name: 'Java', exact: true });

    await pyCheckbox.click();
    await cppCheckbox.click();
    await javaCheckbox.click();
    await page.waitForTimeout(500);

    if (dialogTriggered) {
      throw new Error('Browser alert was triggered when unchecking all languages! Rule 3 violated.');
    }

    // Verify inline validation message
    const inlineError = page.locator('text=At least one programming language must be enabled.');
    const isInlineVisible = await inlineError.isVisible();
    console.log(`  - Inline validation visible: ${isInlineVisible}`);
    if (!isInlineVisible) {
      throw new Error('Inline validation "At least one programming language must be enabled." not displayed');
    }

    // Verify placeholder in editor
    const placeholder = page.locator('text=Please enable at least one programming language above to edit starter code.');
    const isPlaceholderVisible = await placeholder.isVisible();
    console.log(`  - Clean placeholder visible: ${isPlaceholderVisible}`);
    if (!isPlaceholderVisible) {
      throw new Error('Placeholder not displayed when 0 languages enabled');
    }

    // 7. Verify Save Draft is blocked when 0 languages are enabled
    console.log('[Step 7] Verifying Save Draft blocked when 0 languages enabled...');
    const saveDraftBtn = page.locator('button:has-text("Save Draft")');
    await saveDraftBtn.click();
    await page.waitForTimeout(500);
    const bannerError = page.locator('.bg-red-50:has-text("At least one programming language must be enabled.")');
    const isBannerVisible = await bannerError.isVisible();
    console.log(`  - Error banner on Save Draft: ${isBannerVisible}`);
    if (!isBannerVisible) {
      throw new Error('Expected save draft error banner when 0 languages enabled');
    }

    // 8. Test Rule 4 (No Hijacking on Re-enable)
    console.log('[Step 8] Testing Rule 4 (Re-enabling languages)...');
    // Re-enable C
    await cCheckbox.click();
    await page.waitForTimeout(300);
    let currentSel = await selectDropdown.inputValue();
    console.log(`  - Re-enabled C, active is: ${currentSel}`);
    if (currentSel !== 'C') {
      throw new Error(`Expected active language to be C after re-enabling from 0, got ${currentSel}`);
    }

    // Re-enable Python while C is active
    await pyCheckbox.click();
    await page.waitForTimeout(300);
    currentSel = await selectDropdown.inputValue();
    console.log(`  - Re-enabled Python while C active, active is: ${currentSel}`);
    if (currentSel !== 'C') {
      throw new Error(`Active language was hijacked when enabling Python! Expected C, got ${currentSel}`);
    }
    console.log('✓ Rule 4 verified: Re-enabling a language does not hijack active starter language');

    // 9. Save question with C and Python enabled
    console.log('[Step 9] Creating and saving a test question with C...');
    await page.locator('input[placeholder="Descriptive title"]').fill('Browser Test C Question');
    await page.locator('textarea[placeholder="Detailed problem statement..."]').fill('Test problem statement for C language.');
    await saveDraftBtn.click();

    await page.waitForSelector('text=Question created successfully in DRAFT status', { timeout: 10000 });
    console.log('✓ Question created successfully with C language in DRAFT status!');

    console.log('\n======================================================');
    console.log('🎉 ALL PHASE 6 BROWSER UI VERIFICATION CHECKS PASSED 🎉');
    console.log('======================================================\n');
  } catch (err) {
    console.error('❌ Phase 6 Browser Verification Failed:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runPhase6BrowserVerification();
