// The consent page's Approve and Deny buttons have aria-labels (DEM-374).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('consent buttons have descriptive aria-labels', async ({ page }) => {
  await signIn(page);
  await page.goto('/consent?state=x&redirect_uri=http%3A%2F%2Fexample.com%2Fcb&app_name=Demo%20App');

  await expect(page.getByRole('heading', { name: 'Do you consent?' })).toBeVisible();

  const approve = page.getByRole('button', { name: 'Approve access for this app' });
  const deny = page.getByRole('button', { name: 'Deny access for this app' });
  await expect(approve).toHaveText('Approve');
  await expect(deny).toHaveText('Deny');
  await expect(approve).toHaveAttribute('aria-label', 'Approve access for this app');
  await expect(deny).toHaveAttribute('aria-label', 'Deny access for this app');

  await highlight(page, approve, 'Approve');
  await shot(page, 'Approve button, labelled for screen readers', { focus: approve });
  await highlight(page, deny, 'Deny');
  await shot(page, 'Deny button, labelled for screen readers', { focus: deny });
});
