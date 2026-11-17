// The footer shows the balance service version (DEM-318).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the footer shows the balance service version', async ({ page }) => {
  await signIn(page);

  const footer = page.locator('footer.footer');
  await expect(footer).toBeVisible();
  const item = footer.locator('#balance-version');
  await expect(item).toContainText('Balance service:');
  await expect(item).toHaveText(/Balance service:\s*\S+/);
  await highlight(page, item, 'balance service version');
  await shot(page, 'The footer shows the balance service version', { focus: item });
});
