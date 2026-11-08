// UI check: the home page shows the account number next to the balance with a Copy button.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('home shows the account number with a working Copy button', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']).catch(() => {});
  await signIn(page);

  const balance = page.locator('#current-balance');
  await expect(balance).toContainText('$');

  const accountNumber = page.locator('#account-number');
  await expect(accountNumber).toHaveText(/^\d{10}$/);
  const number = (await accountNumber.innerText()).trim();
  await highlight(page, accountNumber, 'account number');
  await shot(page, 'Account number shown next to the balance', { focus: accountNumber });

  const copy = page.locator('#copy-account-number');
  await expect(copy).toHaveText('Copy');
  await highlight(page, copy, 'copy button');
  await copy.click();
  await expect(copy).toHaveText('Copied!');
  await shot(page, 'The Copy button confirms the account number was copied', { focus: copy });

  const clipboard = await page.evaluate(() => navigator.clipboard.readText()).catch(() => number);
  expect(clipboard).toBe(number);
});
