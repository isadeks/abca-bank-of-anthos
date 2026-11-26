// A 'Fees' page is linked from the footer (DEM-381).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the footer Fees link opens the fees page', async ({ page }) => {
  await signIn(page);

  const link = page.locator('footer.footer a#footer-fees-link');
  await expect(link).toBeVisible();
  await highlight(page, link, 'Fees link');
  await shot(page, 'The Fees link in the footer', { focus: link });

  await link.click();
  await expect(page).toHaveURL(/\/fees$/);
  const content = page.locator('#fees-page');
  await expect(content).toContainText('Transfers between customers are free of charge');
  await expect(content).toContainText('Deposits are free');
  await highlight(page, content, 'Fees');
  await shot(page, 'The Fees page: free transfers and free deposits', { focus: content });
});
