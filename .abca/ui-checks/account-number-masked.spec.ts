// The home page shows the account number masked to its last 4 digits (DEM-263),
// keeping the full number available in a tooltip.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('home shows the account number masked with the full number in a tooltip', async ({ page }) => {
  await signIn(page);

  const account = page.locator('#account-number');
  await expect(account).toBeVisible();
  await expect(account).toHaveText(/^\s*[•]{4} \d{4}\s*$/);
  await highlight(page, account, 'masked account number');
  await shot(page, 'Account number shows only its last 4 digits', { focus: account });

  const full = await account.getAttribute('title');
  expect(full).toMatch(/^\d{10}$/);
  expect(await account.innerText()).not.toContain(full as string);
  expect(await account.innerText()).toContain((full as string).slice(-4));
  await highlight(page, account, `tooltip: ${full}`);
  await shot(page, 'The full account number stays in the tooltip', { focus: account });
});
