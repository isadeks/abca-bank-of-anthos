// A deposit that fails must be reported as a failure: a failure status and a clear
// error message on the page (DEM-225), not a silent redirect to a "normal" home page.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('a rejected deposit answers with a failure status and shows an error', async ({ page }) => {
  await signIn(page);

  await page.locator('#depositSpan').click();
  const form = page.locator('#deposit-form');
  await expect(form).toBeVisible();
  await page.locator('#accounts').selectOption('add');
  await page.locator('#external_account_num').fill('1234567890');
  // 883745000 is this bank's own routing number, which a deposit may not use.
  await page.locator('#external_routing_num').fill('883745000');
  await page.locator('#deposit-amount').fill('5');
  await highlight(page, page.locator('#external_routing_num'), 'local routing number');
  await shot(page, 'Depositing from an account with the bank\'s own routing number', { focus: form });

  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/deposit') && r.request().method() === 'POST'),
    form.evaluate((f: HTMLFormElement) => f.submit()),
  ]);
  expect(response.status()).toBe(400);

  const message = page.locator('#alert-message');
  await expect(message).toContainText('Deposit failed');
  await expect(message).toContainText('invalid routing number');
  await highlight(page, message, 'error message');
  await shot(page, 'The page reports the failed deposit with a clear error', { focus: message });
});
