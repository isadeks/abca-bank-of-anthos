// The home page's Deposit action is now labelled "Add money" (DEM-301).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the deposit button and dialog are called Add money', async ({ page }) => {
  await signIn(page);

  const button = page.locator('#depositSpan');
  await expect(button).toContainText('Add money');
  await highlight(page, button, 'Add money button');
  await shot(page, 'The home page action reads Add money', { focus: button });

  await button.click();
  const title = page.locator('#deposit-form').locator('xpath=ancestor::div[contains(@class,"modal-content")]').locator('.modal-title');
  await expect(title).toHaveText('Add money');
  await highlight(page, title, 'Dialog title');
  await shot(page, 'The dialog title reads Add money', { focus: title });
});
