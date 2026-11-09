// UI check: every page footer shows the app version and the environment name.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('footer shows the app version and environment on login and home', async ({ page }) => {
  await page.goto('/login');
  let info = page.locator('#app-build-info');
  await expect(info).toBeVisible();
  await expect(page.locator('#app-version')).not.toBeEmpty();
  await expect(page.locator('#app-environment')).not.toBeEmpty();
  await highlight(page, info, 'version and environment');
  await shot(page, 'Version and environment in the login page footer', { focus: info });

  await signIn(page);
  info = page.locator('#app-build-info');
  await expect(info).toContainText('Version:');
  await expect(info).toContainText('Environment:');
  const env = (await page.locator('#app-environment').innerText()).trim();
  expect(env).toMatch(/^pr-\d+$|^boa$/);
  await highlight(page, info, 'version and environment');
  await shot(page, `Footer on the home page: environment ${env}`, { focus: info });
});
