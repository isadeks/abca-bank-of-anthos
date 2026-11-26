// The Cymbal logo in the top navigation has a tooltip and alt text (DEM-371).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('logo link has a tooltip and alt text', async ({ page }) => {
  await signIn(page);

  const logo = page.locator('#cymbal-logo');
  // The logo is only rendered when the frontend runs with CYMBAL_LOGO=true.
  test.skip((await logo.count()) === 0, 'Cymbal logo is not enabled in this environment');

  const link = page.locator('.logo-container a');
  await expect(link).toHaveAttribute('title', 'Go to your home page');
  await expect(logo).toHaveAttribute('alt', 'Cymbal Bank');
  await highlight(page, logo, 'logo with tooltip');
  await shot(page, 'The Cymbal logo in the top navigation', { focus: logo });
});
