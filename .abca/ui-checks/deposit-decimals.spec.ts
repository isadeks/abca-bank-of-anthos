// A deposit with more than two decimal places is rejected with a clear message
// instead of being silently rounded (DEM-270).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('a deposit of 10.005 is rejected, not rounded', async ({ page }) => {
  await signIn(page);

  await page.locator('#depositSpan').click();
  const form = page.locator('#deposit-form');
  await expect(form).toBeVisible();
  await page.locator('#accounts').selectOption('add');
  await page.locator('#external_account_num').fill('1234567890');
  await page.locator('#external_routing_num').fill('123456789');
  await page.locator('#deposit-amount').fill('10.005');
  await highlight(page, page.locator('#deposit-amount'), 'three decimals');
  await shot(page, 'Depositing 10.005, which has more than two decimal places', { focus: form });

  // Submit directly so the server-side check is what answers.
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/deposit') && r.request().method() === 'POST'),
    form.evaluate((f: HTMLFormElement) => f.submit()),
  ]);
  expect(response.status()).toBe(400);

  const message = page.locator('#alert-message');
  await expect(message).toContainText('Deposit failed');
  await expect(message).toContainText('10.005 has more than two decimal places');
  await highlight(page, message, 'error message');
  await shot(page, 'The deposit is refused with a clear message', { focus: message });
});
