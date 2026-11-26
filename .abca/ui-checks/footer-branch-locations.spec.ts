// The footer link "Locations" is now "Branch locations" (DEM-370).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the footer shows "Branch locations"', async ({ page }) => {
  await signIn(page);

  const links = page.locator('footer.footer .footer-links');
  await expect(links).toBeVisible();
  await expect(links).toContainText('Branch locations');
  await expect(links).toContainText('Personal Banking');
  await expect(links).toContainText('Business Banking');
  await expect(links).toContainText('Loans');
  await highlight(page, links, 'footer links');
  await shot(page, 'Footer link now reads Branch locations', { focus: links });
});
