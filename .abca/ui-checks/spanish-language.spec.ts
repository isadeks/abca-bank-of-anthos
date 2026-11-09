// The header has an English / Español switch that translates the login, home,
// deposit and payment pages (DEM-258).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the language switch translates login, home, deposit and payment to Spanish', async ({ page }) => {
  // Login page
  await page.goto('/login');
  const switcher = page.locator('#language-form');
  await expect(switcher).toBeVisible();
  await expect(page.locator('#lang-en')).toHaveClass(/active/);
  await highlight(page, switcher, 'language switch');
  await shot(page, 'The login page in English, with the language switch in the header', { focus: switcher });

  await page.locator('#lang-es').click();
  await expect(page.locator('#lang-es')).toHaveClass(/active/);
  const loginForm = page.locator('#login-form');
  await expect(loginForm).toContainText('Iniciar sesión');
  await expect(loginForm).toContainText('Usuario');
  await highlight(page, loginForm, 'formulario en español');
  await shot(page, 'The login page after choosing Español', { focus: loginForm });

  // Sign in in English (the helper's selectors), then switch the home page to Spanish
  await page.locator('#lang-en').click();
  await expect(loginForm).toContainText('Sign in');
  await signIn(page);
  await page.locator('#lang-es').click();
  await expect(page.locator('#lang-es')).toHaveClass(/active/);
  await expect(page.locator('.current-balance')).toHaveText('Saldo actual');
  await expect(page.locator('#depositSpan')).toHaveText('Depositar fondos');
  await expect(page.locator('#paymentSpan')).toHaveText('Enviar pago');
  const balance = page.locator('#current-balance');
  await highlight(page, balance, 'saldo actual');
  await shot(page, 'The home page in Spanish', { focus: page.locator('main') });

  // Deposit form
  await page.locator('#depositSpan').click();
  const deposit = page.locator('#deposit-form');
  await expect(deposit).toBeVisible();
  await expect(deposit).toContainText('Hacer un depósito');
  await expect(deposit).toContainText('Importe del depósito');
  await highlight(page, deposit, 'depósito');
  await shot(page, 'The deposit form in Spanish', { focus: deposit });
  await deposit.locator('.deposit-cancel').click();
  await expect(deposit).toBeHidden();

  // Payment form
  await page.locator('#paymentSpan').click();
  const payment = page.locator('#payment-form');
  await expect(payment).toBeVisible();
  await expect(payment).toContainText('Enviar un pago');
  await expect(payment).toContainText('Destinatario');
  await highlight(page, payment, 'pago');
  await shot(page, 'The payment form in Spanish', { focus: payment });
  await payment.locator('.payment-cancel').click();
  await expect(payment).toBeHidden();

  // Back to English
  await page.locator('#lang-en').click();
  await expect(page.locator('.current-balance')).toHaveText('Current Balance');
});
