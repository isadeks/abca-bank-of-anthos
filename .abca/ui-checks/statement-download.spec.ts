// Monthly statement download on the home page (DEM-300).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the home page lets the user download a monthly statement', async ({ page }) => {
  await signIn(page);

  const form = page.locator('#statement-form');
  await expect(form).toBeVisible();
  await highlight(page, form, 'statement form');
  await shot(page, 'Download statement form above the transaction history', { focus: form });

  const now = new Date();
  const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  await page.locator('#statement-month').fill(month);
  await shot(page, `Month ${month} picked`, { focus: form });

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.locator('#statement-download').click(),
  ]);
  expect(download.suggestedFilename()).toBe(`statement-${month}.csv`);
});
