// Optional two-factor sign-in with an authenticator app (DEM-307): turn it on from the
// Security page, sign in with a code, and turn it off again with a recovery code.
// Uses a fresh user so the demo account is never left with 2FA on.
import { test, expect, Page } from '@playwright/test';
import { createHmac } from 'crypto';
import { highlight, shot } from './ui-annotate';

function base32Decode(input: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of input.replace(/=+$/, '').toUpperCase()) {
    bits += alphabet.indexOf(c).toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

// RFC 6238 code for `stepOffset` 30-second steps from now
function totp(secret: string, stepOffset = 0): string {
  const counter = Math.floor(Date.now() / 30000) + stepOffset;
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter));
  const h = createHmac('sha1', base32Decode(secret)).update(buf).digest();
  const o = h[h.length - 1] & 0x0f;
  const n = ((h[o] & 0x7f) << 24) | (h[o + 1] << 16) | (h[o + 2] << 8) | h[o + 3];
  return String(n % 1000000).padStart(6, '0');
}

async function signUp(page: Page, username: string, password: string) {
  await page.goto('/signup');
  await page.locator('#signup-username').fill(username);
  await page.locator('#signup-password').fill(password);
  await page.locator('#signup-password-repeat').fill(password);
  await page.locator('#signup-firstname').fill('Two');
  await page.locator('#signup-lastname').fill('Factor');
  await page.locator('#signup-birthday').fill('1981-01-01');
  await page.locator('#signup-form').evaluate((f: HTMLFormElement) => f.submit());
  await page.waitForURL('**/home');
}

test('a user turns on two-factor sign-in, signs in with a code, and turns it off', async ({ page }) => {
  const username = 'tf' + Date.now().toString(36).slice(-10);
  const password = 'pw-' + username;
  await signUp(page, username, password);

  // Security page, 2FA off
  await page.goto('/security');
  await expect(page.locator('#twofa-status')).toHaveText('off');
  await highlight(page, page.locator('#security-card'), 'two-factor sign-in is off');
  await shot(page, 'The Security page: two-factor sign-in is off', { focus: page.locator('#security-card') });

  // Set up: QR code and secret
  await page.locator('#setup-submit').click();
  await expect(page.locator('#totp-qr svg')).toBeVisible();
  const secret = (await page.locator('#totp-secret').innerText()).trim();
  expect(secret).toMatch(/^[A-Z2-7]{16,}$/);
  await highlight(page, page.locator('#totp-qr'), 'scan with an authenticator app');
  await shot(page, 'QR code and secret to add to an authenticator app', { focus: page.locator('#setup-section') });

  // A wrong code is refused, the right one shows the recovery codes once
  await page.locator('#enable-code').fill('000000');
  await page.locator('#enable-submit').click();
  await expect(page.locator('#security-message')).toContainText('not accepted');
  await page.locator('#enable-code').fill(totp(secret));
  await page.locator('#enable-submit').click();
  const codes = page.locator('#recovery-codes li');
  await expect(codes).toHaveCount(8);
  const recovery = (await codes.first().innerText()).trim();
  await highlight(page, page.locator('#recovery-codes'), '8 one-time recovery codes');
  await shot(page, 'Eight recovery codes, shown only once', { focus: page.locator('#recovery-codes-section') });
  await page.locator('#recovery-codes-done').click();
  await expect(page.locator('#twofa-status')).toHaveText('on');
  await expect(page.locator('#recovery-codes')).toHaveCount(0);

  // Sign out, then sign in: password first, then the code
  await page.locator('#logout-form').evaluate((f: HTMLFormElement) => f.submit());
  await page.waitForURL('**/login');
  await page.locator('#login-username').fill(username);
  await page.locator('#login-password').fill(password);
  await page.locator('#login-form button[type=submit]').click();
  await expect(page.locator('#login-code')).toBeVisible();
  await highlight(page, page.locator('#login-code'), 'asks for the code after the password');
  await shot(page, 'After the password, sign-in asks for the 6-digit code', { focus: page.locator('#login-form') });
  await page.locator('#login-code').fill('000000');
  await page.locator('#login-form button[type=submit]').click();
  await expect(page.locator('#mfa-error')).toContainText('not accepted');
  // The first code was used to turn 2FA on, so use the next 30-second code
  await page.locator('#login-code').fill(totp(secret, 1));
  await page.locator('#login-form button[type=submit]').click();
  await page.waitForURL('**/home');
  await expect(page.locator('#current-balance')).toBeVisible();

  // Turn it off with a recovery code
  await page.goto('/security');
  await expect(page.locator('#twofa-status')).toHaveText('on');
  await page.locator('#disable-code').fill(recovery);
  await highlight(page, page.locator('#disable-form'), 'confirm with a code');
  await shot(page, 'Turning two-factor sign-in off needs a code', { focus: page.locator('#disable-form') });
  await page.locator('#disable-submit').click();
  await expect(page.locator('#twofa-status')).toHaveText('off');
  await expect(page.locator('#security-message')).toContainText('off');
  await shot(page, 'Two-factor sign-in is off again', { focus: page.locator('#security-card') });
});
