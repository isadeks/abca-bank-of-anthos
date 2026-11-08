// UI check: the header's dark mode toggle switches the whole UI to a dark theme and remembers it in a cookie.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('dark mode toggle switches the theme and is remembered', async ({ page, context }) => {
  await signIn(page);
  const html = page.locator('html');
  const toggle = page.locator('#theme-toggle');

  await expect(html).toHaveAttribute('data-theme', 'light');
  await highlight(page, toggle, 'dark mode toggle');
  await shot(page, 'Home page in the light theme, with the dark mode toggle in the header', { focus: toggle });

  await toggle.click();
  await expect(html).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(18, 18, 18)');
  const history = page.locator('#transaction-table');
  await highlight(page, history, 'dark transaction history');
  await shot(page, 'Dark mode: the whole page, including the transaction history, is dark', { focus: history });

  const cookies = await context.cookies();
  expect(cookies.find((c) => c.name === 'theme')?.value).toBe('dark');

  await page.reload();
  await expect(html).toHaveAttribute('data-theme', 'dark');
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await highlight(page, toggle, 'still dark after reload');
  await shot(page, 'After reloading the page the dark theme is remembered', { focus: toggle });

  await toggle.click();
  await expect(html).toHaveAttribute('data-theme', 'light');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await shot(page, 'Toggling again returns to the light theme');
});
