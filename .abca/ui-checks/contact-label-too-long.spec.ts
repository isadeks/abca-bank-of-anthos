// A contact label over 30 characters is rejected by the contacts service and the
// payment form shows its message (DEM-274).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('a contact label longer than 30 characters is rejected with a clear message', async ({ page }) => {
  await signIn(page);

  await page.locator('#paymentSpan').click();
  const form = page.locator('#payment-form');
  await expect(form).toBeVisible();
  await page.locator('#payment-accounts').selectOption('add');
  await page.locator('#contact_account_num').fill('1234567891');
  // The browser caps the input at 30 characters; bypass that to reach the server check.
  await page.locator('#contact_label').evaluate((el: HTMLInputElement) => {
    el.removeAttribute('maxlength');
    el.removeAttribute('pattern');
    el.value = 'A'.repeat(31);
  });
  await page.locator('#payment-amount').fill('1');
  await highlight(page, page.locator('#contact_label'), '31 characters');
  await shot(page, 'Paying a new contact whose label is 31 characters long', { focus: form });

  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/payment') && r.request().method() === 'POST'),
    form.evaluate((f: HTMLFormElement) => f.submit()),
  ]);
  expect(response.status()).toBe(400);

  const message = page.locator('#alert-message');
  await expect(message).toContainText('Payment failed');
  await expect(message).toContainText('label must be 30 characters or fewer');
  await highlight(page, message, 'error message');
  await shot(page, 'The page explains that the label is too long', { focus: message });
});
