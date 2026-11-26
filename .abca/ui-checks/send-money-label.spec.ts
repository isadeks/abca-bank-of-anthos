import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('send payment button is renamed to Send money', async ({ page }) => {
  await signIn(page);
  const label = page.locator('#paymentSpan');
  await expect(label).toHaveText('Send money');
  await highlight(page, label, 'Send money');
  await shot(page, 'The home page button reads Send money', { focus: label });

  await label.click();
  const title = page.locator('#sendPayment .modal-title');
  await expect(title).toHaveText('Send money');
  await highlight(page, title, 'dialog title');
  await shot(page, 'The dialog title reads Send money', { focus: title });
});
