import { expect, test } from '@playwright/test';

test.describe('Phase 0 smoke', () => {
  test('the app shell loads and reports backend connectivity', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { name: /finance tracker/i })).toBeVisible();
    await expect(page.getByRole('status')).toContainText(/connected/i, { timeout: 15_000 });
  });

  test('the page has no obvious accessibility blockers', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('main')).toBeVisible();
    await expect(page).toHaveTitle(/finance tracker/i);
  });
});
