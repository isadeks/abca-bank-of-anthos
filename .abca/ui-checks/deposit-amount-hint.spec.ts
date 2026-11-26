// The deposit form hints at the allowed precision under the amount field (DEM-383).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('deposit form shows the amount hint', async ({ page }) => {
  await signIn(page);
  await page.locator('#depositSpan').click();
  const hint = page.locator('#deposit-amount-hint');
  await expect(hint).toBeVisible();
  await expect(hint).toHaveText('Amounts up to two decimal places');
  await highlight(page, hint, 'amount hint');
  await shot(page, 'Hint under the deposit amount field', { focus: hint });
});
