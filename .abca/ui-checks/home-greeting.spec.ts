import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('[DM1][DM4] the home page greets the user by first name', async ({ page }) => {
  await signIn(page);
  const greeting = page.locator('#home-greeting');
  await expect(greeting).toBeVisible();
  await highlight(page, greeting, '[DM1] greeting');
  await shot(page, '[DM1] Home page greeting with the first name', { focus: greeting });
  const text = (await greeting.innerText()).trim();
  expect(text).toMatch(/^Welcome back, \S+$/);
  await shot(page, '[DM4] Greeting uses only the first word of the name', { focus: greeting });
});
