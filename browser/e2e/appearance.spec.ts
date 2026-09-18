import {test, expect, type Page} from '@playwright/test';

async function runExample(page: Page, example: string) {
  await page.locator('#example').selectOption(example);
  await page.locator('#convert').click();
  await expect(page.locator('#convert')).toBeEnabled({timeout: 60000});
}

test('full bold wordmark and strictly one-way conversion symbols', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('.brand-name')).toHaveText('ClinSearch-CrossWalk');
  await expect(page.locator('.brand')).toHaveAttribute('aria-label', 'ClinSearch-CrossWalk home');
  await expect(page.locator('.brand-mark')).toHaveText('→');
  await expect(page.locator('#empty-state > span')).toHaveText('→');
  const weight = await page.locator('.brand-name').evaluate(node => getComputedStyle(node).fontWeight);
  expect(Number(weight)).toBeGreaterThanOrEqual(700);
  expect(await page.locator('body').innerText()).not.toMatch(/[⇄↔⇆⇌]/u);
});

test('blue light and dark previews preserve a completed query and audit', async ({page}) => {
  await page.setViewportSize({width: 1440, height: 1040});
  await page.emulateMedia({colorScheme: 'light'});
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await runExample(page, 'date');
  await expect(page.locator('#query')).toHaveValue('asthma[tw]');
  await page.locator('.numbered').evaluate(node => node.setAttribute('open', ''));
  const audit = await page.locator('#audit-body').innerText();
  const requests: string[] = [];
  page.on('request', request => requests.push(request.url()));
  for (const theme of ['light', 'dark']) {
    await page.getByRole('combobox', {name: 'Colour theme'}).selectOption(theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await expect(page.locator('#query')).toHaveValue('asthma[tw]');
    await expect(page.locator('#copy')).toBeEnabled();
    expect(await page.locator('#audit-body').innerText()).toBe(audit);
    await page.screenshot({path: `test-results/desktop-${theme}-converter.png`, fullPage: true});
    await page.screenshot({path: `test-results/desktop-${theme}-overview.png`});
  }
  expect(requests).toEqual([]);
  expect(errors).toEqual([]);
});

test('system preference, explicit override, persistence and return to system', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await page.goto('/');
  const select = page.getByRole('combobox', {name: 'Colour theme'});
  await expect(select).toHaveValue('system');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.emulateMedia({colorScheme: 'light'});
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await select.selectOption('dark');
  await page.reload();
  await expect(select).toHaveValue('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await select.selectOption('system');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.emulateMedia({colorScheme: 'dark'});
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => localStorage.getItem('clinsearch-crosswalk-theme'))).toBeNull();
});

test('theme control works when browser storage is unavailable', async ({page}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', {get() { throw new Error('storage denied'); }});
  });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.locator('#theme').selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await runExample(page, 'basic');
  await expect(page.locator('#query')).toHaveValue('(asthma[tw]) OR (wheeze[tw])');
  await page.locator('#theme').selectOption('light');
  await expect(page.locator('#copy')).toBeEnabled();
  expect(errors).toEqual([]);
});

test('dark mode retains the invalid-query gate and stores only theme preference', async ({page}) => {
  await page.goto('/');
  await runExample(page, 'invalid');
  await page.locator('#theme').selectOption('dark');
  await expect(page.locator('#state-pill')).toHaveText('Review required');
  await expect(page.locator('#copy')).toBeDisabled();
  await expect(page.locator('#download-query')).toBeDisabled();
  await expect(page.locator('#query')).toHaveValue('');
  const stored = await page.evaluate(() => Object.entries(localStorage));
  expect(stored).toEqual([['clinsearch-crosswalk-theme', 'dark']]);
  await page.locator('#theme').selectOption('light');
  await expect(page.locator('#copy')).toBeDisabled();
});

test('theme selector remains usable without overflow on narrow mobile layouts', async ({page}) => {
  await page.goto('/');
  await runExample(page, 'limit');
  for (const width of [390, 320]) {
    await page.setViewportSize({width, height: 844});
    for (const theme of ['light', 'dark']) {
      await page.locator('#theme').selectOption(theme);
      await expect(page.locator('#theme')).toBeVisible();
      await expect(page.locator('.brand-name')).toBeVisible();
      await expect(page.locator('#query')).toHaveValue('asthma[tw]');
      const widths = await page.evaluate(() => ({doc: document.documentElement.scrollWidth, view: innerWidth}));
      expect(widths.doc).toBeLessThanOrEqual(widths.view);
      if (width === 390) await page.screenshot({path: `test-results/mobile-${theme}-converter.png`, fullPage: true});
    }
  }
});
