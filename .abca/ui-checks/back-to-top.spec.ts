// The transaction history ends with a "Back to top" link (DEM-368).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('Back to top returns to the top of the home page', async ({ page }) => {
  await signIn(page);

  const link = page.locator('#back-to-top');
  await link.scrollIntoViewIfNeeded();
  await expect(link).toBeVisible();
  await expect(link).toHaveText('Back to top');
  await highlight(page, link, 'back to top');
  await shot(page, 'The Back to top link after the last transaction', { focus: link });

  await link.click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await shot(page, 'Back at the top of the page');
});
