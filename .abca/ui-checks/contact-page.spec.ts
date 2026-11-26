// A 'Contact us' page is linked from the footer (DEM-382).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the footer Contact us link shows email and opening hours', async ({ page }) => {
  await signIn(page);

  const link = page.locator('footer.footer a#footer-contact-link');
  await expect(link).toBeVisible();
  await highlight(page, link, 'Contact us link');
  await shot(page, 'The Contact us link in the footer', { focus: link });

  await link.click();
  await expect(page).toHaveURL(/\/contact$/);
  const content = page.locator('#contact-page');
  await expect(content.locator('#contact-email')).toContainText('support@larkspur-demo.example');
  await expect(content.locator('#contact-hours')).toContainText('Opening hours');
  await highlight(page, content, 'Contact us');
  await shot(page, 'The Contact us page: support email and opening hours', { focus: content });
});
