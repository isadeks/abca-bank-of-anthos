// The Cymbal logo in the top navigation has a tooltip and alt text (DEM-371).
// The logo is only rendered when the frontend runs with CYMBAL_LOGO=true; the preview
// uses the default Larkspur text brand, so there we check the brand is shown instead.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('logo link has a tooltip and alt text', async ({ page }) => {
  await signIn(page);

  const nav = page.locator('.navbar-top');
  await expect(nav).toBeVisible();

  const logo = page.locator('#cymbal-logo');
  if (await logo.count() > 0) {
    await expect(page.locator('.logo-container a')).toHaveAttribute('title', 'Go to your home page');
    await expect(logo).toHaveAttribute('alt', 'Cymbal Bank');
    await highlight(page, logo, 'logo with tooltip');
    await shot(page, 'The Cymbal logo in the top navigation', { focus: logo });
  } else {
    const brand = page.locator('.navbar-brand');
    await expect(brand).toBeVisible();
    await highlight(page, brand, 'text brand (logo disabled)');
    await shot(page, 'Top navigation with the text brand; the Cymbal logo is not enabled here', { focus: brand });
  }
});
