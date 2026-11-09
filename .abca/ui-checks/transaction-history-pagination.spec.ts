// The home page shows the 10 most recent transactions and a "Load more" button
// that appends the next 10 (the demo account has a long history).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('transaction history shows 10 rows and loads 10 more on demand', async ({ page }) => {
  await signIn(page);

  const rows = page.locator('#transaction-list tr');
  const loadMore = page.locator('#load-more-transactions');

  await expect(rows.first()).toBeVisible();
  await expect(rows).toHaveCount(10);
  await expect(loadMore).toBeVisible();
  await highlight(page, page.locator('#transaction-table'), 'only the 10 most recent');
  await shot(page, 'Home page: the 10 most recent transactions and a Load more button', {
    focus: page.locator('#transaction-table'),
  });

  const firstRowBefore = await rows.first().innerText();
  await loadMore.scrollIntoViewIfNeeded();
  await highlight(page, loadMore, 'Load more');
  await loadMore.click();

  await expect(rows).toHaveCount(20);
  // the rows already shown stay in place; the new ones are appended below
  expect(await rows.first().innerText()).toBe(firstRowBefore);
  await highlight(page, page.locator('#transaction-table'), '20 transactions now');
  await shot(page, 'After Load more: the next 10 transactions are appended', {
    focus: page.locator('#transaction-table'),
  });
});

test('Load more is a full-width, easy-to-tap button on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await signIn(page);

  const loadMore = page.locator('#load-more-transactions');
  await expect(loadMore).toBeVisible();
  await loadMore.scrollIntoViewIfNeeded();
  await highlight(page, loadMore, 'Load more');
  await shot(page, 'On a phone, Load more spans the width of the card', { focus: loadMore });

  const button = await loadMore.boundingBox();
  const card = await page.locator('#load-more-container').boundingBox();
  expect(button!.height).toBeGreaterThanOrEqual(44);
  expect(button!.width).toBeGreaterThan(card!.width * 0.8);
});
