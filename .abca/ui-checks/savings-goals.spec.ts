// Savings goals: create a goal, save money into it, see the progress bar, delete it (DEM-325).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('create a savings goal, save toward it and delete it', async ({ page }) => {
  await signIn(page);
  const name = `Trip ${Date.now() % 100000}`;

  const section = page.locator('#savings-goals');
  await expect(section).toBeVisible();
  await page.locator('#goal-name').fill(name);
  await page.locator('#goal-target').fill('200');
  await highlight(page, page.locator('#goal-form'), 'new goal');
  await shot(page, 'Creating a savings goal with a name and a target', { focus: section });
  await page.locator('#goal-create-button').click();

  const goal = page.locator('[data-testid="goal"]', { hasText: name });
  await expect(goal).toBeVisible();
  await expect(goal.locator('.goal-target')).toHaveText('$200.00');
  await expect(goal.locator('.goal-saved')).toHaveText('$0.00');
  await highlight(page, goal, 'new goal');
  await shot(page, 'The goal on the home page with nothing saved yet', { focus: goal });

  const balanceBefore = await page.locator('#current-balance').innerText();
  await goal.locator('.goal-amount-input').fill('50');
  await goal.locator('.goal-contribute-button').click();

  await expect(page.locator('#alert-message')).toContainText('Money moved to goal');
  const saved = page.locator('[data-testid="goal"]', { hasText: name });
  await expect(saved.locator('.goal-saved')).toHaveText('$50.00');
  await expect(saved.locator('.goal-progress')).toHaveAttribute('aria-valuenow', '25');
  expect(await page.locator('#current-balance').innerText()).not.toBe(balanceBefore);
  await highlight(page, saved.locator('.progress'), '25% saved');
  await shot(page, '$50 of the $200 goal saved, and the checking balance went down', { focus: saved });

  // The money moved as a normal ledger transfer, so it shows in the history
  await expect(page.locator('#transaction-list tr').first()).toContainText('$50.00');

  await saved.locator('.goal-delete-button').click();
  await expect(page.locator('#alert-message')).toContainText('Goal deleted');
  await expect(page.locator('[data-testid="goal"]', { hasText: name })).toHaveCount(0);
  await shot(page, 'The goal is deleted', { focus: section });
});
