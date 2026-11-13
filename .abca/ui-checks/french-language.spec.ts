// The UI can be switched to French and back to English (DEM-293).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the home page can be shown in French and back in English', async ({ page }) => {
  await signIn(page);

  const balanceLabel = page.locator('.current-balance');
  await expect(balanceLabel).toHaveText('Current Balance');
  const switcher = page.locator('#language-switcher');
  await highlight(page, switcher, 'language switcher');
  await shot(page, 'The home page in English, with a language switcher in the header', { focus: switcher });

  await page.locator('#lang-fr').click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
  await expect(balanceLabel).toHaveText('Solde actuel');
  await expect(page.locator('#depositSpan')).toHaveText('Déposer des fonds');
  await expect(page.locator('#paymentSpan')).toHaveText('Envoyer un paiement');
  await expect(page.locator('#transaction-table')).toBeVisible();
  await expect(page.locator('#current-balance')).toContainText('$');
  await highlight(page, balanceLabel, 'solde');
  await shot(page, 'The same page in French: balance, deposit and payment buttons', { focus: page.locator('main') });

  // the choice is remembered on the next page
  await page.reload();
  await expect(balanceLabel).toHaveText('Solde actuel');
  await page.locator('#depositSpan').click();
  const title = page.locator('#depositFunds .modal-title');
  await expect(title).toHaveText('Effectuer un dépôt');
  await highlight(page, title, 'dépôt');
  await shot(page, 'The deposit form in French', { focus: page.locator('#depositFunds .modal-content') });
  await page.locator('#depositFunds .btn-secondary').click();
  await expect(title).toBeHidden();

  await page.locator('#lang-en').click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(balanceLabel).toHaveText('Current Balance');
  await shot(page, 'Back to English with the same switcher', { focus: switcher });
});
