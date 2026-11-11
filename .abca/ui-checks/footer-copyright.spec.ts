// The footer no longer shows the "© 2020-2024 Google LLC" line (DEM-283).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the footer has no copyright line but keeps the demo disclaimer', async ({ page }) => {
  await signIn(page);

  const footer = page.locator('footer.footer');
  await expect(footer).toBeVisible();
  await expect(footer).toContainText('This website is hosted for demo purposes only');
  await expect(footer).not.toContainText('2020-2024');
  await expect(footer).not.toContainText('Google LLC');
  await highlight(page, footer, 'footer');
  await shot(page, 'The footer shows the demo disclaimer without the copyright line', { focus: footer });
});
