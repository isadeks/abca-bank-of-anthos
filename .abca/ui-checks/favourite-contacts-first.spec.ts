// Favourite contacts are listed first, with a star, on the payment form (DEM-304).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('starring a contact moves it to the top of the payment form with a star', async ({ page }) => {
  await signIn(page);
  await page.locator('#paymentSpan').click();
  const select = page.locator('#payment-accounts');
  await expect(select).toBeVisible();

  // pick a contact that is not yet a favourite and star it
  const plain = select.locator('option[data-label][data-favorite="false"]').last();
  const label = await plain.getAttribute('data-label');
  await select.selectOption({ label: (await plain.textContent())!.trim() });
  const toggle = page.locator('#favorite-toggle');
  await expect(toggle).toContainText('Star this contact');
  await highlight(page, toggle, 'star this contact');
  await shot(page, `Starring ${label} from the payment form`, { focus: select });
  await toggle.click();

  await page.locator('#paymentSpan').click();
  const first = select.locator('option').first();
  await expect(first).toContainText(`★ ${label}`);
  await expect(first).toHaveAttribute('data-favorite', 'true');
  await highlight(page, select, 'favourites first');
  await shot(page, 'The starred contact is now first in the list', { focus: select });

  // unstar again so the demo account is left as it was
  await select.selectOption({ index: 0 });
  await expect(toggle).toContainText('Unstar this contact');
  await toggle.click();
  await page.locator('#paymentSpan').click();
  await expect(select.locator('option[data-favorite="true"]')).toHaveCount(0);
});
