import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/** Full real user journeys against the real `apps/backend` (issue #21's own
 * Testing Decisions) - register, Garage CRUD, every Weigh Event Solo Ticket
 * branch, results, history, logout, and the protected-route redirect. No
 * mocking anywhere; a fresh Account per test run (unique email) against the
 * ephemeral SQLite DB `playwright.config.ts` wires up. */

function uniqueEmail(tag: string): string {
  return `e2e-${tag}-${Date.now()}-${Math.floor(Math.random() * 100000)}@example.com`;
}

async function registerAndLogin(page: Page, email: string): Promise<void> {
  await page.goto('/register');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill('correct-horse-battery-staple');
  await page.getByRole('button', { name: 'Register' }).click();
  await expect(page).toHaveURL(/\/garage$/);
}

async function addTruck(page: Page, nickname: string): Promise<void> {
  await page.getByRole('button', { name: '+ Add Truck' }).click();
  await page.getByLabel('GVWR (lb)').fill('10000');
  await page.getByLabel('Front GAWR (lb)').fill('4500');
  await page.getByLabel('Rear GAWR (lb)').fill('6500');
  await page.getByLabel('GCWR (lb) — optional').fill('20000');
  await page.getByLabel('Nickname — optional').fill(nickname);
  await page.getByRole('button', { name: 'Add Truck' }).click();
  await expect(page.getByText(nickname)).toBeVisible();
}

async function addTrailer(page: Page, nickname: string): Promise<void> {
  await page.getByRole('button', { name: '+ Add Trailer' }).click();
  await page.getByLabel('GVWR (lb)').fill('9500');
  await page.getByLabel('GAWR per axle (lb)').fill('5200');
  await page.getByLabel('Axle Count').fill('2');
  await page.getByLabel('Nickname — optional').fill(nickname);
  await page.getByRole('button', { name: 'Add Trailer' }).click();
  await expect(page.getByText(nickname)).toBeVisible();
}

test.describe('authenticated journey', () => {
  test('reaches login and register by clicking from the calculator, not by URL', async ({ page }) => {
    // Every other test in this file navigates via page.goto('/login' or
    // '/register') directly, which is exactly how a real, discoverable-nav
    // bug shipped undetected: the calculator (the only page a fully
    // anonymous visitor lands on) had no link to either page at all. This
    // is the one test that actually clicks through from '/', the real
    // entry point.
    await page.goto('/');
    await page.getByRole('navigation').getByRole('link', { name: 'Log in' }).click();
    await expect(page).toHaveURL(/\/login$/);

    // /login's own body also links to /register ("Need an account?"), so
    // scope to the nav specifically to stay unambiguous.
    await page.getByRole('navigation').getByRole('link', { name: 'Register' }).click();
    await expect(page).toHaveURL(/\/register$/);
  });

  test('register, build a Garage, and see the account is signed in (Story 2/6/9/10/14)', async ({ page }) => {
    const email = uniqueEmail('garage');
    await registerAndLogin(page, email);

    await expect(page.getByText(email)).toBeVisible();

    await addTruck(page, 'Addie');
    await addTrailer(page, 'Goose');
  });

  test('rejects a duplicate email registration and wrong-password login with generic messages (Story 3/5)', async ({ page }) => {
    const email = uniqueEmail('dupe');
    await registerAndLogin(page, email);
    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL(/\/login$/);

    await page.goto('/register');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill('another-strong-password');
    await page.getByRole('button', { name: 'Register' }).click();
    await expect(page.getByText(/already registered/i)).toBeVisible();

    await page.goto('/login');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill('totally-wrong-password');
    await page.getByRole('button', { name: 'Log in' }).click();
    await expect(page.getByText(/not valid/i)).toBeVisible();
  });

  test('redirects a signed-out visitor away from a protected route, and back after login (Story 8)', async ({ page }) => {
    await page.goto('/garage');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('records a full Weigh Event with no Solo Ticket, then sees it in history (Story 16/18/22/25/27)', async ({ page }) => {
    const email = uniqueEmail('noso');
    await registerAndLogin(page, email);
    await addTruck(page, 'Addie NoSolo');
    await addTrailer(page, 'Goose NoSolo');

    await page.goto('/weigh-events/new');
    await page.getByLabel('Truck Profile').selectOption({ label: 'Addie NoSolo' });
    await page.getByLabel('Trailer Profile').selectOption({ label: 'Goose NoSolo' });
    await page.getByRole('button', { name: 'Next' }).click();

    await page.getByLabel('Steer Axle (lb)').fill('4300');
    await page.getByLabel('Drive Axle (lb)').fill('6100');
    await page.getByLabel('Trailer Axle group (lb)').fill('9200');
    await page.getByLabel('Gross Weight (lb)').fill('19600');
    await page.getByRole('button', { name: 'Next' }).click();

    await expect(page.getByText(/No reusable Solo weight/)).toBeVisible();
    await page.getByLabel('Skip the Solo Ticket').check();
    await page.getByRole('button', { name: 'See results' }).click();

    await expect(page.getByText('Steer Axle', { exact: true })).toBeVisible();
    await expect(page.getByText('GCWR', { exact: true })).toBeVisible();
    await expect(page.getByText(/Unverified Value/)).toBeVisible(); // GCWR is always unverified when evaluated.

    await page.getByRole('link', { name: 'View history' }).click();
    await expect(page).toHaveURL(/\/weigh-events$/);
    await expect(page.getByText('Addie NoSolo')).toBeVisible();
    await expect(page.getByText('Goose NoSolo')).toBeVisible();
  });

  test('records a fresh linked Solo Ticket (matching Reweigh Reference)', async ({ page }) => {
    const email = uniqueEmail('linked');
    await registerAndLogin(page, email);
    await addTruck(page, 'Addie Linked');
    await addTrailer(page, 'Goose Linked');

    await page.goto('/weigh-events/new');
    await page.getByLabel('Truck Profile').selectOption({ label: 'Addie Linked' });
    await page.getByLabel('Trailer Profile').selectOption({ label: 'Goose Linked' });
    await page.getByRole('button', { name: 'Next' }).click();

    await page.getByLabel('Steer Axle (lb)').fill('4300');
    await page.getByLabel('Drive Axle (lb)').fill('6100');
    await page.getByLabel('Trailer Axle group (lb)').fill('9200');
    await page.getByLabel('Gross Weight (lb)').fill('19600');
    await page.getByLabel('Reweigh Reference — optional').fill('REF-100');
    await page.getByRole('button', { name: 'Next' }).click();

    await page.getByLabel('Enter a new Solo Ticket').check();
    await page.getByLabel('Solo Steer Axle (lb)').fill('4300');
    await page.getByLabel('Solo Drive Axle (lb)').fill('6200');
    await page.getByLabel('Solo Gross Weight (lb)').fill('10500');
    await page.getByLabel('Reweigh Reference — optional').fill('REF-100');
    await page.getByRole('button', { name: 'See results' }).click();

    // A matching Reweigh Reference auto-links - no confirm step, straight to results.
    await expect(page.getByText('Trailer GVWR', { exact: true })).toBeVisible();
    await expect(page.getByText('Confirm Solo Ticket link')).not.toBeVisible();
  });

  test('confirms a fresh mismatched Solo Ticket link, then a second run declines it (Story 23/24)', async ({ page }) => {
    const email = uniqueEmail('mismatch');
    await registerAndLogin(page, email);
    await addTruck(page, 'Addie Mismatch');
    await addTrailer(page, 'Goose Mismatch');

    async function fillThroughSolo(steerRef: string, soloRef: string) {
      await page.goto('/weigh-events/new');
      await page.getByLabel('Truck Profile').selectOption({ label: 'Addie Mismatch' });
      await page.getByLabel('Trailer Profile').selectOption({ label: 'Goose Mismatch' });
      await page.getByRole('button', { name: 'Next' }).click();

      await page.getByLabel('Steer Axle (lb)').fill('4300');
      await page.getByLabel('Drive Axle (lb)').fill('6100');
      await page.getByLabel('Trailer Axle group (lb)').fill('9200');
      await page.getByLabel('Gross Weight (lb)').fill('19600');
      await page.getByLabel('Reweigh Reference — optional').fill(steerRef);
      await page.getByRole('button', { name: 'Next' }).click();

      await page.getByLabel('Enter a new Solo Ticket').check();
      await page.getByLabel('Solo Steer Axle (lb)').fill('4300');
      await page.getByLabel('Solo Drive Axle (lb)').fill('6200');
      await page.getByLabel('Solo Gross Weight (lb)').fill('10500');
      await page.getByLabel('Reweigh Reference — optional').fill(soloRef);
      await page.getByRole('button', { name: 'See results' }).click();
    }

    // Story 23: confirm.
    await fillThroughSolo('REF-A', 'REF-B');
    await expect(page.getByText('Confirm Solo Ticket link')).toBeVisible();
    await page.getByRole('button', { name: 'Yes, they belong together' }).click();
    await expect(page.getByText('Trailer GVWR', { exact: true })).toBeVisible();

    // Story 24: decline - Weigh Event still saves, with just the Combined Ticket.
    await fillThroughSolo('REF-C', 'REF-D');
    await expect(page.getByText('Confirm Solo Ticket link')).toBeVisible();
    await page.getByRole('button', { name: 'No, save Combined Ticket only' }).click();
    await expect(page.getByText('Steer Axle', { exact: true })).toBeVisible();
  });

  test('reuses a past Solo weight unchanged, then adjusted on a later Weigh Event (Story 19/20/21)', async ({ page }) => {
    const email = uniqueEmail('reuse');
    await registerAndLogin(page, email);
    await addTruck(page, 'Addie Reuse');
    await addTrailer(page, 'Goose Reuse');

    // First Weigh Event: a fresh Solo Ticket, to give a later run something reusable.
    await page.goto('/weigh-events/new');
    await page.getByLabel('Truck Profile').selectOption({ label: 'Addie Reuse' });
    await page.getByLabel('Trailer Profile').selectOption({ label: 'Goose Reuse' });
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByLabel('Steer Axle (lb)').fill('4300');
    await page.getByLabel('Drive Axle (lb)').fill('6100');
    await page.getByLabel('Trailer Axle group (lb)').fill('9200');
    await page.getByLabel('Gross Weight (lb)').fill('19600');
    await page.getByLabel('Reweigh Reference — optional').fill('REF-REUSE-1');
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByLabel('Enter a new Solo Ticket').check();
    await page.getByLabel('Solo Steer Axle (lb)').fill('4300');
    await page.getByLabel('Solo Drive Axle (lb)').fill('6200');
    await page.getByLabel('Solo Gross Weight (lb)').fill('10500');
    await page.getByLabel('Reweigh Reference — optional').fill('REF-REUSE-1');
    await page.getByRole('button', { name: 'See results' }).click();
    await expect(page.getByText('Steer Axle', { exact: true })).toBeVisible();

    // Second Weigh Event: Story 19 - told upfront a reusable weight exists.
    await page.goto('/weigh-events/new');
    await page.getByLabel('Truck Profile').selectOption({ label: 'Addie Reuse' });
    await page.getByLabel('Trailer Profile').selectOption({ label: 'Goose Reuse' });
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByLabel('Steer Axle (lb)').fill('4300');
    await page.getByLabel('Drive Axle (lb)').fill('6100');
    await page.getByLabel('Trailer Axle group (lb)').fill('9200');
    await page.getByLabel('Gross Weight (lb)').fill('19600');
    await page.getByRole('button', { name: 'Next' }).click();

    await expect(page.getByText(/A past Solo weight is available/)).toBeVisible();
    await page.getByLabel('Reuse the past Solo weight').check();
    await page.getByRole('button', { name: 'See results' }).click();
    await expect(page.getByText('Steer Axle', { exact: true })).toBeVisible();

    // Third Weigh Event: Story 21 - reuse, but adjusted.
    await page.goto('/weigh-events/new');
    await page.getByLabel('Truck Profile').selectOption({ label: 'Addie Reuse' });
    await page.getByLabel('Trailer Profile').selectOption({ label: 'Goose Reuse' });
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByLabel('Steer Axle (lb)').fill('4300');
    await page.getByLabel('Drive Axle (lb)').fill('6100');
    await page.getByLabel('Trailer Axle group (lb)').fill('9200');
    await page.getByLabel('Gross Weight (lb)').fill('19600');
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByLabel('Reuse the past Solo weight').check();
    await page.getByLabel('Something has changed since then (adjust the weight)').check();
    await page.getByLabel('Adjusted Solo Gross Weight (lb)').fill('10800');
    await page.getByRole('button', { name: 'See results' }).click();

    // Story 26: an adjusted reused Solo weight labels Trailer GVWR as Unverified.
    await expect(page.getByText(/Unverified Value/).first()).toBeVisible();
  });

  test('shows Weigh Event history newest-first with pagination controls (Story 27/28/29)', async ({ page }) => {
    const email = uniqueEmail('history');
    await registerAndLogin(page, email);
    await addTruck(page, 'Addie History');
    await addTrailer(page, 'Goose History');

    for (let i = 0; i < 2; i++) {
      await page.goto('/weigh-events/new');
      await page.getByLabel('Truck Profile').selectOption({ label: 'Addie History' });
      await page.getByLabel('Trailer Profile').selectOption({ label: 'Goose History' });
      await page.getByRole('button', { name: 'Next' }).click();
      await page.getByLabel('Steer Axle (lb)').fill('4300');
      await page.getByLabel('Drive Axle (lb)').fill('6100');
      await page.getByLabel('Trailer Axle group (lb)').fill('9200');
      await page.getByLabel('Gross Weight (lb)').fill('19600');
      await page.getByRole('button', { name: 'Next' }).click();
      await page.getByLabel('Skip the Solo Ticket').check();
      await page.getByRole('button', { name: 'See results' }).click();
      await expect(page.getByText('Steer Axle', { exact: true })).toBeVisible();
    }

    await page.goto('/weigh-events');
    await expect(page.getByText('Addie History').first()).toBeVisible();
    // Fewer than one page's worth - "Older" is disabled (Story 28: not
    // loaded/paginated as if there were more than there are).
    await expect(page.getByRole('button', { name: 'Older' })).toBeDisabled();
  });

  test('logs out and confirms a protected route redirects to login again (Story 7/8)', async ({ page }) => {
    const email = uniqueEmail('logout');
    await registerAndLogin(page, email);

    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL(/\/login$/);

    await page.goto('/garage');
    await expect(page).toHaveURL(/\/login$/);
  });
});
