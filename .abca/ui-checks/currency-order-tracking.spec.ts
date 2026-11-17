// A customer orders foreign cash for delivery and tracks the order (DEM-332).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('place a foreign currency order and see it tracked', async ({ page }) => {
  await signIn(page);

  await page.goto('/foreign-currency?currency=EUR&amount=20');
  const quote = page.locator('#fx-quote');
  const unavailable = page.locator('#fx-error');
  await expect(quote.or(unavailable)).toBeVisible();
  if (!(await quote.isVisible())) {
    // Live rates cannot be reached from here: no order can be placed, and the orders page still works.
    await expect(unavailable).toContainText('unavailable');
    await shot(page, 'Without exchange rates no quote is given, so no order can be placed', { focus: unavailable });
    await page.goto('/currency-orders');
    await expect(page.locator('#orders-title')).toHaveText('My currency orders');
    await expect(page.locator('#orders-table').or(page.locator('#orders-empty'))).toBeVisible();
    return;
  }
  await highlight(page, quote, 'quote');
  await shot(page, 'The quote now offers to place the order', { focus: quote });

  const address = '12 Harbour Road, Springfield';
  await page.locator('#fx-address').fill(address);
  const orderForm = page.locator('#fx-order-form');
  await highlight(page, orderForm, 'delivery address');
  await shot(page, 'Enter a delivery address and place the order', { focus: orderForm });
  await page.locator('#fx-order-submit').click();

  // The order page shows the status timeline, starting at Placed.
  await expect(page.locator('#order-title')).toContainText('20.00 EUR');
  await expect(page.locator('#order-status')).toHaveText('Placed');
  await expect(page.locator('#order-address')).toHaveText(address);
  const timeline = page.locator('#order-timeline');
  await expect(timeline.locator('li')).toHaveText([/Placed/, /Preparing/, /Out for delivery/, /Delivered/]);
  await expect(timeline.locator('li.current')).toContainText('Placed');
  await highlight(page, timeline, 'status timeline');
  await shot(page, 'The order is placed and tracked through Placed, Preparing, Out for delivery and Delivered', { focus: timeline });

  // And it is listed under My currency orders.
  await page.locator('#order-back').click();
  await expect(page.locator('#orders-title')).toHaveText('My currency orders');
  const row = page.locator('.order-row').first();
  await expect(row).toContainText('20.00 EUR');
  await expect(row.locator('.order-status')).toHaveText(/Placed|Preparing|Out for delivery|Delivered/);
  await highlight(page, row, 'new order');
  await shot(page, 'My currency orders lists the new order with its status', { focus: row });
});
