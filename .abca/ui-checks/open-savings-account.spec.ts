// A signed-in user can open a savings account from the home page (DEM-285).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('a new user opens a savings account from the home page', async ({ page }) => {
  // A fresh user, so the check starts without a savings account and can be re-run.
  const username = `sav_${Date.now().toString(36)}`.slice(0, 15);
  await page.goto('/signup');
  await page.locator('#signup-username').fill(username);
  await page.locator('#signup-password').fill('bells');
  await page.locator('#signup-password-repeat').fill('bells');
  await page.locator('#signup-firstname').fill('Sav');
  await page.locator('#signup-lastname').fill('Ings');
  await page.locator('#signup-birthday').fill('1981-01-01');
  await Promise.all([
    page.waitForURL(/\/home/),
    page.locator('#signup-form button[type=submit]').click(),
  ]);

  const section = page.locator('#savings-account');
  await expect(section).toContainText("You don't have a savings account yet");
  const open = page.locator('#open-savings-button');
  await expect(open).toBeVisible();
  await highlight(page, open, 'open a savings account');
  await shot(page, 'The home page offers to open a savings account', { focus: section });

  await open.click();

  const message = page.locator('#alert-message');
  await expect(message).toContainText('Savings account opened');
  const number = page.locator('#savings-account-number');
  await expect(number).toHaveText(/^\d{10}$/);
  await expect(page.locator('#open-savings-button')).toHaveCount(0);
  await highlight(page, number, 'savings account number');
  await shot(page, 'The savings account is open and shows its account number', { focus: section });

  // The account stays after a reload, and it is not the checking account number.
  await page.reload();
  await expect(number).toHaveText(/^\d{10}$/);
  await expect(number).not.toHaveText((await page.locator('.account-number').first().textContent())!.trim());
});
