// The sign-up page shows a privacy note under the SSN field (DEM-373).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('sign-up shows a privacy note under the SSN field', async ({ page }) => {
  await page.goto('/signup');
  const ssn = page.locator('#ssn');
  await expect(ssn).toBeVisible();
  await highlight(page, ssn, 'SSN field');

  const note = page.locator('#ssn-help');
  await expect(note).toBeVisible();
  await expect(note).toHaveText('We only use your SSN to verify your identity.');
  await expect(note).toHaveClass(/text-muted/);
  const [a, b] = await Promise.all([ssn.boundingBox(), note.boundingBox()]);
  expect(b!.y).toBeGreaterThanOrEqual(a!.y + a!.height - 1);
  await highlight(page, note, 'privacy note');
  await shot(page, 'Privacy note under the SSN field on sign-up', { focus: note });
});
