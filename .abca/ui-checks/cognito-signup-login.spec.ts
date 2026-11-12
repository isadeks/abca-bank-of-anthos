// Sign-up and sign-in go through the Cognito user pool: a new user can register, lands on the
// home page with the display name and account number carried by the ID token claims, and can
// sign out and back in with the same credentials.
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('a new user signs up and signs in again through Cognito', async ({ page }) => {
  const username = 'cg' + Date.now().toString(36).slice(-8);
  const password = 'Anthos-' + Date.now().toString(36) + '!A1';

  await page.goto('/signup');
  await page.locator('#signup-username').fill(username);
  await page.locator('#signup-password').fill(password);
  await page.locator('#signup-password-repeat').fill(password);
  await page.locator('#signup-firstname').fill('Cora');
  await page.locator('#signup-lastname').fill('Nito');
  await page.locator('#signup-birthday').fill('1990-02-03');
  await highlight(page, page.locator('#signup-form'), 'registering a new user');
  await shot(page, 'Registering a new account (the user is created in Cognito)',
    { focus: page.locator('#signup-form') });
  await page.locator('#signup-form button[type=submit]').click();

  // Signed in right after sign-up: name and account id come from the token claims
  const name = page.locator('#account-user-name');
  await expect(name).toHaveText('Cora Nito');
  const accountNumber = page.locator('.account-number');
  await expect(accountNumber).toHaveText(/^\d{10}$/);
  const account = (await accountNumber.innerText()).trim();
  await highlight(page, name, 'display name from the token');
  await shot(page, 'Signed in after sign-up: display name from the Cognito ID token',
    { focus: name });

  // Sign out and sign in again with the credentials Cognito now owns
  await page.locator('#accountDropdown').click();
  await page.locator('#logout-form a').click();
  await page.locator('#login-username').fill(username);
  await page.locator('#login-password').fill(password);
  await highlight(page, page.locator('#login-form'), 'signing in with Cognito credentials');
  await shot(page, 'Signing in again with the same username and password',
    { focus: page.locator('#login-form') });
  await page.locator('#login-form button[type=submit]').click();

  await expect(name).toHaveText('Cora Nito');
  await expect(accountNumber).toHaveText(account);
  await highlight(page, accountNumber, 'same account number');
  await shot(page, 'Same account number after signing in again', { focus: accountNumber });
});
