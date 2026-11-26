// The deposit entry point is titled "Add money" instead of "Deposit Funds" (DEM-379).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('deposit button is titled Add money', async ({ page }) => {
  await signIn(page);
  const title = page.locator('#depositSpan');
  await expect(title).toHaveText('Add money');
  await expect(page.getByText('Deposit Funds')).toHaveCount(0);
  await highlight(page, title, 'Add money');
  await shot(page, 'The deposit card is now titled Add money', { focus: title });
});
