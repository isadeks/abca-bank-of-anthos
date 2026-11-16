// A rejected sign-up shows the user service's message in an alert above the form (DEM-315).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('sign-up with an empty field shows the error above the form', async ({ page }) => {
  await page.goto('/signup');
  const form = page.locator('#signup-form');
  await expect(form).toBeVisible();
  await page.locator('#signup-username').fill(`ui_${Date.now() % 1000000}`);
  await page.locator('#signup-password').fill('pw12345');
  await page.locator('#signup-password-repeat').fill('pw12345');
  await page.locator('#signup-firstname').fill('Ada');
  await page.locator('#signup-lastname').fill('Lovelace');
  await page.locator('#signup-birthday').fill('1990-01-01');
  // Leave the (read-only) state empty so userservice rejects the form; skip browser validation.
  await page.locator('#state').evaluate((el: HTMLSelectElement) => {
    el.innerHTML = '<option value="" selected>Choose...</option>';
  });
  await highlight(page, page.locator('#state'), 'state left empty');
  await shot(page, 'Sign-up form with a field left empty', { focus: form });

  await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/signup') && r.request().method() === 'POST'),
    form.evaluate((f: HTMLFormElement) => f.submit()),
  ]);

  const alert = page.locator('#signup-error');
  // The preview runs the user service as released: DEM-313 changes its wording to
  // 'Please fill in every field.', so accept either; what matters is that the
  // user service's own message is shown and the generic login error is not.
  await expect(alert).toContainText(/Please fill in every field\.|missing value for input field\(s\)/);
  await expect(page).toHaveURL(/\/signup$/);
  await highlight(page, alert, 'error from the user service');
  await shot(page, 'The sign-up page shows the error above the form', { focus: alert });
});
