// The home page greets the signed-in user by first name, using the time of day (DEM-245).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('home greets the user by first name', async ({ page }) => {
  await signIn(page);

  const greeting = page.locator('#greeting');
  await expect(greeting).toHaveText(/^Good (morning|afternoon|evening), \S+$/);
  // Only the first name, not the full name shown in the navigation bar.
  const fullName = (await page.locator('#account-user-name').innerText()).trim();
  const firstName = fullName.split(/\s+/)[0];
  await expect(greeting).toHaveText(new RegExp(`, ${firstName}$`));
  await highlight(page, greeting, 'greeting');
  await shot(page, 'The home page greets the user by first name for the time of day', { focus: greeting });

  const balance = page.locator('#current-balance');
  await expect(balance).toContainText('$');
  await highlight(page, balance, 'balance');
  await shot(page, 'The rest of the home page is unchanged', { focus: balance });
});
