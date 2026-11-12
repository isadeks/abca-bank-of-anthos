// A customer schedules a recurring payment to a saved contact, sees it listed on the
// home page with its next payment date, and cancels it.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('schedule a weekly payment to a contact, see it listed, then cancel it', async ({ page }) => {
  await signIn(page);

  const form = page.locator('#schedule-form');
  await expect(form).toBeVisible();
  await highlight(page, form, 'schedule form');
  await shot(page, 'The home page offers to schedule a recurring payment', { focus: form });

  // A unique amount identifies this run's row even if earlier runs left schedules behind.
  const cents = 100 + (Date.now() % 800);
  const amount = (cents / 100).toFixed(2);
  const option = page.locator('#schedule-account option', { hasText: 'Alice' }).first();
  const accountNum = await option.getAttribute('value');
  await page.locator('#schedule-account').selectOption(accountNum!);
  await page.locator('#schedule-amount').fill(amount);
  await page.locator('#schedule-frequency').selectOption('weekly');
  await highlight(page, page.locator('#schedule-amount'), `$${amount} weekly`);
  await shot(page, `Scheduling $${amount} every week to Alice`, { focus: form });

  await page.locator('#schedule-submit').click();

  const message = page.locator('#alert-message');
  await expect(message).toContainText('Scheduled payment created');

  const list = page.locator('#scheduled-payments');
  const row = list.locator('tr.schedule-row', { hasText: `$${amount}` }).first();
  await expect(row).toBeVisible();
  await expect(row.locator('.schedule-contact')).toContainText('Alice');
  await expect(row.locator('.schedule-frequency')).toHaveText('Weekly');
  await expect(row.locator('.schedule-next-date')).toHaveText(/[A-Z][a-z]{2} \d{2}, \d{4}/);
  await highlight(page, row, 'new schedule');
  await shot(page, 'The schedule is listed with its contact, amount, frequency and next payment date', { focus: list });

  const scheduleId = await row.getAttribute('data-schedule-id');
  await row.locator('.schedule-cancel').click();

  await expect(page.locator('#alert-message')).toContainText('Scheduled payment cancelled');
  await expect(page.locator(`tr[data-schedule-id="${scheduleId}"]`)).toHaveCount(0);
  await highlight(page, page.locator('#scheduled-payments'), 'cancelled');
  await shot(page, 'After cancelling, the schedule is gone from the list', { focus: page.locator('#scheduled-payments') });
});
