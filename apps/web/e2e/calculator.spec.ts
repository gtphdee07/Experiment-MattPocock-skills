import { test, expect } from '@playwright/test';

/** Story 1/32: the free calculator, completely unauthenticated, driven end
 * to end against its own pre-existing reference backend
 * (docs/design/web/api) - confirming it's genuinely untouched by the #30
 * promotion. No login anywhere in this flow. */
test('completes the free calculator flow with no login required', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Know before you tow.' })).toBeVisible();

  // Step 0: Tow Vehicle ratings.
  await page.getByPlaceholder('e.g. 10000').fill('10000');
  await page.getByPlaceholder('e.g. 4500').fill('4500');
  await page.getByPlaceholder('e.g. 6500').fill('6500');
  await page.getByRole('button', { name: 'Next' }).click();

  // Step 1: Trailer ratings.
  await page.getByPlaceholder('e.g. 9500').fill('9500');
  await page.getByPlaceholder('e.g. 5200').fill('5200');
  await page.getByRole('button', { name: 'Next' }).click();

  // Step 2: Combined Ticket.
  await page.getByPlaceholder('e.g. 4300').fill('4300');
  await page.getByPlaceholder('e.g. 6100').fill('6100');
  await page.getByPlaceholder('e.g. 9200').fill('9200');
  await page.getByPlaceholder('e.g. 19600').fill('19600');
  await page.getByRole('button', { name: 'Next' }).click();

  // Step 3: Solo Ticket - skip it entirely.
  await page.getByRole('button', { name: 'See results' }).click();

  // Step 4: results - the six-check grid.
  await expect(page.getByRole('heading', { name: 'Rig Evaluation' })).toBeVisible();
  await expect(page.getByText('Steer Axle')).toBeVisible();
  await expect(page.getByText('Drive Axle')).toBeVisible();
  await expect(page.getByText('Trailer Axle', { exact: true })).toBeVisible();
  await expect(page.getByText('Hitched GVWR')).toBeVisible();
  await expect(page.getByText('GCWR', { exact: true })).toBeVisible();
  await expect(page.getByText('Trailer GVWR')).toBeVisible();
});
