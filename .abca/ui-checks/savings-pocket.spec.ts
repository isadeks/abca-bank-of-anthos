// The Savings pocket card on the home page and moving its money back to the main account.
// Nothing funds the pocket yet (round-ups come next), so the check funds it with a direct
// transfer to the pocket through the ledgerwriter transfer API when that API is reachable
// (LEDGERWRITER_URL, default http://ledgerwriter:8080). If it isn't, only the empty pocket
// is checked.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

const LOCAL_ROUTING = process.env.LOCAL_ROUTING_NUM || '883745000';
const SAVINGS_ROUTING = process.env.SAVINGS_ROUTING_NUM || '883745999';
const LEDGERWRITER_URL = process.env.LEDGERWRITER_URL || 'http://ledgerwriter:8080';

function parseDollars(text: string): number {
  return parseFloat(text.replace(/[^0-9.\-]/g, ''));
}

test('the Savings pocket shows on the home page and moves back to the main account', async ({ page, context }) => {
  await signIn(page);
  await page.goto('/home');

  const card = page.locator('#pocket-card');
  const pocket = page.locator('#pocket-balance');
  const move = page.locator('#pocket-move-button');
  await expect(card).toContainText('Savings Pocket');
  await expect(pocket).toContainText('$');
  await highlight(page, card, 'Savings pocket');
  await shot(page, 'The Savings pocket next to the main balance', { focus: card });

  // fund the pocket with a direct transfer from the main account
  const account = (await page.locator('.account-number').innerText()).trim();
  const token = (await context.cookies()).find((c) => c.name === 'token')?.value;
  let funded = false;
  try {
    const resp = await page.request.post(`${LEDGERWRITER_URL}/transactions`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        fromAccountNum: account, fromRoutingNum: LOCAL_ROUTING,
        toAccountNum: account, toRoutingNum: SAVINGS_ROUTING,
        amount: 1234, uuid: `pocket-check-${Date.now()}`,
      },
      timeout: 15_000,
    });
    funded = resp.status() === 201;
  } catch {
    funded = false;
  }

  if (!funded) {
    // the transfer API is not reachable from here: check the empty state only
    await expect(move).toBeDisabled();
    await highlight(page, move, 'disabled when empty');
    await shot(page, 'Move to main account is disabled while the pocket is empty', { focus: card });
    return;
  }

  const balance = page.locator('#current-balance');
  await expect(async () => {
    await page.goto('/home');
    expect(parseDollars(await pocket.innerText())).toBeGreaterThanOrEqual(12.34);
  }).toPass({ timeout: 60_000 });
  const mainBefore = parseDollars((await balance.innerText()).replace(/,/g, ''));
  const pocketBefore = parseDollars((await pocket.innerText()).replace(/,/g, ''));
  await expect(move).toBeEnabled();
  await highlight(page, card, 'funded pocket');
  await shot(page, 'The funded Savings pocket with Move to main account enabled', { focus: card });

  await move.click();
  const alert = page.locator('#alert-message');
  await expect(alert).toContainText('Moved');
  await expect(alert).toContainText('to your main account');
  await expect(pocket).toContainText('$0.00');
  await expect(move).toBeDisabled();
  await expect(async () => {
    await page.goto('/home');
    expect(parseDollars((await balance.innerText()).replace(/,/g, ''))).toBeCloseTo(mainBefore + pocketBefore, 2);
  }).toPass({ timeout: 30_000 });
  await highlight(page, alert, 'success message');
  await shot(page, 'Pocket moved back: the pocket is empty and the main balance went up', { focus: card });
});
