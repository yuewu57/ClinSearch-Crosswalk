import {test,expect, type Page} from '@playwright/test';
async function convert(page: Page, source: string) {
  await page.locator('#source').fill(source);
  await page.locator('#convert').click();
  await expect(page.locator('#convert')).toBeEnabled({timeout:60000});
}
test('real browser conversion with production CSP, correct numbering and no outbound requests', async({page}) => {
  const requests: string[]=[];const errors:string[]=[];
  page.on('request',r=>requests.push(r.url()));
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  const csp=await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content');
  expect(csp).toContain("'wasm-unsafe-eval'");
  await convert(page,'1 asthma.tw.\n2 2022*.dt.\n3 1 and 2');
  await expect(page.locator('#query')).toHaveValue('asthma[tw]');
  await expect(page.locator('#numbered')).toHaveText('#1 asthma[tw]\n#3 #1\n');
  await expect(page.locator('#state-pill')).toHaveText('Local checks passed');
  expect(requests.every(url=>url.startsWith('http://127.0.0.1:4173/'))).toBeTruthy();
  expect(errors).toEqual([]);
  requests.length=0;
  await convert(page,'1 asthma.tw.\n2 cancer.tw.\n3 limit 1 to humans');
  await expect(page.locator('#query')).toHaveValue('asthma[tw]');
  expect(requests).toEqual([]);
  await page.screenshot({path:'test-results/desktop-converter.png',fullPage:true});
});
test('failure gate removes old query and download eligibility', async({page})=>{
  await page.goto('/');await convert(page,'1 cancer.ab.');
  await expect(page.locator('#copy')).toBeEnabled();
  await page.locator('#source').fill('1 cancer.ab./freq=x');
  await expect(page.locator('#copy')).toBeDisabled();
  await expect(page.locator('#query')).toHaveValue('');
  await page.locator('#convert').click();await expect(page.locator('#convert')).toBeEnabled({timeout:60000});
  await expect(page.locator('#state-pill')).toHaveText('Review required');
  await expect(page.locator('#copy')).toBeDisabled();await expect(page.locator('#download-query')).toBeDisabled();
  await expect(page.locator('#query')).toHaveValue('');
});
test('RTF bytes stay local and use the same reference parser', async({page})=>{
  await page.goto('/');await page.locator('#mode-rtf').click();
  await page.locator('#rtf').setInputFiles({name:'sample.rtf',mimeType:'application/rtf',buffer:Buffer.from('{\\rtf1\\ansi Medline:\\par 1 asthma.tw.\\par 2 wheeze.tw.\\par 3 1 or 2}')});
  await page.locator('#convert').click();await expect(page.locator('#convert')).toBeEnabled({timeout:60000});
  await expect(page.locator('#query')).toHaveValue('(asthma[tw]) OR (wheeze[tw])');
});
test('unsafe update-date OR is blocked; literal phrase OR survives',async({page})=>{
  await page.goto('/');await convert(page,'1 asthma.tw.\n2 2022*.ed,dt.\n3 1 or 2');
  await expect(page.locator('#copy')).toBeDisabled();
  await convert(page,'1 "law or polic*".tw.');
  await expect(page.locator('#query')).toHaveValue('"law or polic*"[tw]');
});
test('full MeSH snapshot resolves uncached evaluation terms and preserves fallback',async({page})=>{
  await page.goto('/');await convert(page,'1 occupational therapist/');
  await expect(page.locator('#preview-notice')).toContainText('31,110 descriptors');
  await expect(page.locator('#preview-notice')).toContainText('267,012 exact preferred/entry-term labels');
  await expect(page.locator('#query')).toHaveValue('"Occupational Therapists"[mh]');
  await expect(page.locator('#warning-list')).not.toContainText('not verified');
  await convert(page,'1 Crosswalk Unmapped Heading 991/');
  await expect(page.locator('#warning-list')).toContainText('not verified');
  await expect(page.locator('#query-note')).toContainText('not submitted to PubMed');
});
test('untrusted markup is rendered as text, and downloadable report has correct extension',async({page})=>{
  await page.goto('/');await convert(page,'1 "<img src=x onerror=alert(1)>".tw.');
  expect(await page.locator('#audit-body img').count()).toBe(0);
  const pending=page.waitForEvent('download');await page.locator('#download-report').click();
  const download=await pending;expect(download.suggestedFilename()).toMatch(/_v1_YW_\d{8}\.json$/);
});
test('cancel initialization, then restart cleanly',async({page})=>{
  await page.goto('/');await page.locator('#source').fill('1 cancer.ab.');
  await page.locator('#convert').click();await page.locator('#cancel').click();
  await expect(page.locator('#status')).toContainText('Cancelled');
  await expect(page.locator('#copy')).toBeDisabled();
  await page.locator('#convert').click();await expect(page.locator('#convert')).toBeEnabled({timeout:60000});
  await expect(page.locator('#query')).toHaveValue('cancer[tiab]');
});
test('mobile layout does not overflow; clear discards previous results',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  await page.locator('#example').selectOption('limit');await page.locator('#convert').click();
  await expect(page.locator('#convert')).toBeEnabled({timeout:60000});
  await expect(page.locator('#query')).toHaveValue('asthma[tw]');
  const widths=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,view:innerWidth}));
  expect(widths.doc).toBeLessThanOrEqual(widths.view);
  await page.screenshot({path:'test-results/mobile-converter.png',fullPage:true});
  await page.locator('#clear').click();await expect(page.locator('#source')).toHaveValue('');
  await expect(page.locator('#query')).toHaveValue('');await expect(page.locator('#copy')).toBeDisabled();
});
