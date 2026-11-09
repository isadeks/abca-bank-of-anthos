// Split a bill: pick 2 to 4 contacts and a total, review the summary (the last share
// absorbs the rounding so the total is exact), then send each contact its share.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('split a bill between three contacts with a summary before sending', async ({ page }) => {
  await signIn(page);

  const open = page.locator('#splitSpan');
  await expect(open).toHaveText(/Split a Bill/);
  await highlight(page, open, 'Split a Bill');
  await shot(page, 'The new "Split a Bill" action on the home page', { focus: open });

  await open.click();
  const form = page.locator('#split-form');
  await expect(form).toBeVisible();
  const contacts = form.locator('input.split-contact');
  await expect(contacts.nth(2)).toBeAttached();
  for (let i = 0; i < 3; i++) {
    await contacts.nth(i).check({ force: true });
  }
  await page.locator('#split-amount').fill('10.01');
  await highlight(page, page.locator('#split-contacts'), 'three contacts');
  await shot(page, 'Picking three contacts and a $10.01 total', { focus: form });

  await page.locator('#split-review').click();
  const rows = page.locator('#split-summary-rows tr');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText('$3.33');
  await expect(rows.nth(1)).toContainText('$3.33');
  await expect(rows.nth(2)).toContainText('$3.35');
  await expect(page.locator('#split-summary-total')).toHaveText('$10.01');
  await highlight(page, page.locator('#split-summary'), 'summary before sending');
  await shot(page, 'Summary before sending: $3.33, $3.33 and $3.35 (last share takes the rounding)', { focus: form });

  await page.locator('#split-send').click();
  const alert = page.locator('#alert-message');
  await expect(alert).toContainText('Bill split between 3 contacts');
  await highlight(page, alert, 'split sent');
  await shot(page, 'Each contact was sent its share', { focus: alert });

  const history = page.locator('#transaction-table');
  await expect(history.locator('tbody tr').first()).toBeVisible();
  await highlight(page, history, 'new payments');
  await shot(page, 'The three payments in the transaction history', { focus: history });
});
