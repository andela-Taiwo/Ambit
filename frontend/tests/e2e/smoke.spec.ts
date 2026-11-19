import { expect, test } from '@playwright/test';

test.describe('Critical journeys', () => {
  test('an anonymous visitor is sent to sign in', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
  });

  test('register, create an account and record a transaction', async ({ page }) => {
    const email = `e2e-${String(Date.now())}@example.com`;

    await page.goto('/register');
    await page.getByLabel('Name').fill('E2E User');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill('correct-horse-battery-staple');
    await page.getByRole('button', { name: 'Create account' }).click();

    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole('link', { name: 'Accounts' }).first().click();
    await page.getByRole('button', { name: 'New account' }).click();
    const accountDialog = page.getByRole('dialog');
    await accountDialog.getByLabel('Name').fill('E2E Current');
    await accountDialog.getByLabel('Opening balance').fill('1000.00');
    await accountDialog.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByText('E2E Current')).toBeVisible();

    await page.getByRole('link', { name: 'Transactions' }).first().click();
    await page.getByRole('button', { name: 'New transaction' }).click();
    const transactionDialog = page.getByRole('dialog');
    await transactionDialog.getByLabel('Category').selectOption({ label: 'Groceries' });
    await transactionDialog.getByLabel(/Amount/).fill('24.99');
    await transactionDialog.getByLabel('Description').fill('E2E coffee');
    await transactionDialog.getByRole('button', { name: 'Add transaction' }).click();

    await expect(page.getByText('E2E coffee')).toBeVisible();
    await expect(page.getByText(/£24\.99/)).toBeVisible();
  });

  test('the shell exposes landmarks and the app title', async ({ page }) => {
    await page.goto('/login');

    await expect(page).toHaveTitle(/finance tracker/i);
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
  });
});
