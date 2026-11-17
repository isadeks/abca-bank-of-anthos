import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('footer no longer shows cluster, pod and zone', async ({ page }) => {
  await signIn(page);
  await page.goto('/home');
  const footer = page.locator('footer');
  await highlight(page, footer, 'Page footer');
  await shot(page, 'The footer without cluster, pod and zone details', { focus: footer });
  await expect(footer).not.toContainText('Cluster:');
  await expect(footer).not.toContainText('Zone:');
});
