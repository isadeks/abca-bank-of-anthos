import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('Print link sits under Transaction History', async ({ page }) => {
  await signIn(page);
  const heading = page.locator('#transaction-history-heading');
  const link = page.locator('#print-link');
  await expect(link).toBeVisible();
  await expect(link).toHaveText('Print');
  const h = await heading.boundingBox();
  const l = await link.boundingBox();
  expect(l!.y).toBeGreaterThan(h!.y);
  await highlight(page, link, 'Print link');
  await shot(page, 'Print link under Transaction History', { focus: link });
});
