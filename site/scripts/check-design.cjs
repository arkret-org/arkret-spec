const { chromium, expect } = require(process.env.SITE_PLAYWRIGHT_MODULE || '@playwright/test');
const fs=require('node:fs/promises'), path=require('node:path'), crypto=require('node:crypto');
const base=process.env.SITE_TEST_URL||'http://127.0.0.1:4385',out=path.resolve(process.env.SITE_TEST_ARTIFACTS||'artifacts/site-design');
const sha=buffer=>crypto.createHash('sha256').update(buffer).digest('hex');
const luminance=value=>{const channels=value.startsWith('#')?[1,3,5].map(index=>parseInt(value.slice(index,index+2),16)):value.match(/[\d.]+/g).slice(0,3).map(Number);const c=channels.map(value=>{value/=255;return value<=.04045?value/12.92:((value+.055)/1.055)**2.4});return .2126*c[0]+.7152*c[1]+.0722*c[2]};
const contrast=(foreground,background)=>{const a=luminance(foreground),b=luminance(background);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
(async()=>{
 await fs.mkdir(out,{recursive:true});
 const browser=await chromium.launch({channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1280,height:720},permissions:['clipboard-read','clipboard-write'],acceptDownloads:true});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const checks=[],contrasts=[];
 const checkTextContrast=async(selector,metadata)=>{
  await expect(page.locator(selector).first()).toBeVisible();
  const rows=await page.locator(selector).evaluateAll(elements=>elements.filter(element=>element.getBoundingClientRect().height>0).map(element=>{
   let ancestor=element,background='rgba(0, 0, 0, 0)';while(ancestor){background=getComputedStyle(ancestor).backgroundColor;if(background!=='rgba(0, 0, 0, 0)')break;ancestor=ancestor.parentElement;}
   return{foreground:getComputedStyle(element).color,background};
  }));
  expect(rows.length).toBeGreaterThan(0);for(const row of rows){expect(row.background).not.toBe('rgba(0, 0, 0, 0)');const ratio=contrast(row.foreground,row.background);expect(ratio,JSON.stringify({selector,...metadata,...row})).toBeGreaterThanOrEqual(4.5);contrasts.push({...metadata,control:selector,...row,ratio});}
 };
 try {
  for(const url of ['/', '/zh/guide/','/zh/catalog/operations/','/zh/catalog/errors/','/zh/catalog/schemas/','/zh/catalog/event-kinds/','/zh/catalog/profiles/','/zh/openapi/','/zh/v1/models/realm-and-space/','/en/v1/spec-map/']){
   const response=await context.request.get(base+url);expect(response.status(),url).toBe(200);checks.push({url,status:response.status()});
  }
  for(const url of ['/zh/catalog/schemas/not-a-registered-schema/','/catalog/operations/not-a-registered-operation/','/this-page-does-not-exist/']){
   const response=await context.request.get(base+url);expect(response.status(),url).toBe(404);checks.push({url,status:response.status()});
  }
  for(const url of ['/catalog/operations/','/en/catalog/schemas/','/openapi/']){
   const response=await context.request.get(base+url,{maxRedirects:0});expect(response.status()).toBe(301);expect(response.headers().location).toMatch(/^\/zh\//);checks.push({url,status:301,location:response.headers().location});
  }
  await page.goto(base);
  const read=page.getByRole('link',{name:'开始阅读规范',exact:true});await expect(read).toBeVisible();
  expect((await read.boundingBox()).y).toBeLessThan(620);
  await page.screenshot({path:path.join(out,'home-desktop.png'),fullPage:true});
  await read.click();await expect(page).toHaveURL(/\/zh\/guide\//);await expect(page.locator('main')).toContainText('客户端');
  await expect(page.locator('.ak-nav [aria-current]:visible')).toHaveCount(1);
  await page.goto(base+'/zh/catalog/operations/');
  const groups=page.locator('.ak-operation-group');expect(await groups.count()).toBeGreaterThan(1);
  expect(await groups.evaluateAll(elements=>elements.every(el=>!el.open))).toBe(true);
  const search=page.locator('[data-query]');await search.fill('/_arkret/self/agents');
  await expect(page.locator('.ak-match-count')).not.toContainText('0 /');
  expect(await page.locator('tr[data-operation]:visible').count()).toBeGreaterThan(0);
  await expect(page.locator('.ak-transport-column:visible')).toHaveCount(0);
  await page.locator('[data-transports]').check();expect(await page.locator('.ak-transport-column:visible').count()).toBeGreaterThan(0);
  const detail=page.locator('tr[data-operation]:visible a').first();const href=await detail.getAttribute('href');await detail.click();
  await expect(page).toHaveURL(/q=/);await page.locator('.ak-breadcrumb a').click();await expect(search).toHaveValue('/_arkret/self/agents');
  await page.screenshot({path:path.join(out,'catalog-filter-desktop.png'),fullPage:true});
  await search.fill('absolutely-no-operation-matches');await expect(page.locator('[data-empty]')).toBeVisible();
  await page.locator('[data-clear]').click();await expect(search).toHaveValue('');
  await page.goto(base+'/zh/catalog/schemas/');await page.locator('.ak-schema-index-search').fill('event-payload');
  await page.locator('[data-schema-entry]:visible a').first().click();
  const root=page.locator('.ak-schema-viewer');await expect(root).toBeVisible();
  await root.locator('[data-field-query]').fill('payload');await expect(root.locator('[data-schema-count]')).not.toHaveText(/^0 \//);
  await root.locator('[data-field-query]').fill('totally-absent-field-name');await expect(root.locator('[data-schema-empty]')).toBeVisible();
  await root.locator('[data-reset]').click();await root.locator('[data-required-only]').check();
  expect(await root.locator('.ak-schema-node[data-required=true]:visible').count()).toBeGreaterThan(0);
  await root.locator('[data-reset]').click();await root.locator('[data-expand]').click();await root.locator('[data-collapse]').click();
  expect(await root.locator('details.ak-schema-node[open]').count()).toBe(0);
  await root.locator('.ak-schema-raw summary').click();await root.locator('[data-copy-json]').click();await expect(root.locator('[data-copy-status]')).toHaveText('已复制');
  const raw=await root.locator('.ak-schema-raw code').textContent();const copied=await page.evaluate(()=>navigator.clipboard.readText());expect(JSON.parse(copied)).toEqual(JSON.parse(raw));
  await page.screenshot({path:path.join(out,'schema-filter-and-json.png'),fullPage:true});
  // A blocked CDN must leave byte-identical canonical download and a working retry.
  await page.route('https://cdn.jsdelivr.net/**',route=>route.abort('failed'));
  await page.goto(base+'/zh/openapi/');await expect(page.locator('#openapi-load-status')).toContainText('暂不可用');
  const downloadPromise=page.waitForEvent('download');await page.locator('#openapi-download').click();const download=await downloadPromise;
  const downloaded=await fs.readFile(await download.path());const canonical=await fs.readFile(path.resolve(__dirname,'../../spec/v1/artifacts/openapi/arkret-service-api.openapi.yaml'));
  expect(sha(downloaded)).toBe(sha(canonical));
  await page.locator('#openapi-retry').click();await expect(page.locator('#openapi-load-status')).toContainText('暂不可用');
  await page.screenshot({path:path.join(out,'openapi-cdn-failure.png'),fullPage:true});
  await page.unroute('https://cdn.jsdelivr.net/**');await page.locator('#openapi-retry').click();
  try {await expect(page.locator('#openapi-load-status')).toContainText('已就绪',{timeout:60000});checks.push({scalar_live:true});}
  catch {checks.push({scalar_live:false,status:await page.locator('#openapi-load-status').textContent()});}
  await page.screenshot({path:path.join(out,'openapi-live-attempt.png'),fullPage:true});
  for(const width of [1280,390]){
   await page.setViewportSize({width,height:width===390?844:720});
   for(const theme of ['light','dark']){
    await page.goto(base);await page.evaluate(theme=>{localStorage.setItem('starlight-theme',theme);document.documentElement.dataset.theme=theme},theme);
    await expect(page.locator('body')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    for(const hover of [false,true]){
     const primary=page.locator('.ak-btn-primary').first();if(hover)await primary.hover();else await page.mouse.move(0,0);await page.waitForTimeout(250);
     const colors=await primary.evaluate(element=>{const s=getComputedStyle(element);return{foreground:s.color,background:s.backgroundColor,image:s.backgroundImage}});
     const backgrounds=colors.image.match(/rgb\([^)]*\)/g)||[colors.background];
     const ratios=backgrounds.map(background=>contrast(colors.foreground,background));for(const ratio of ratios)expect(ratio,JSON.stringify({width,theme,hover,colors})).toBeGreaterThanOrEqual(4.5);
     contrasts.push({width,theme,hover,control:'primary',...colors,ratios});
    }
    await page.mouse.move(0,0);await page.waitForTimeout(250);
    await checkTextContrast('.ak-stack-auth',{width,theme});
    const heading=await page.locator('.ak-h1-accent').evaluate(element=>({foreground:getComputedStyle(element).color,fill:getComputedStyle(element).webkitTextFillColor,background:getComputedStyle(document.documentElement).getPropertyValue('--ak-bg').trim()}));
    expect(heading.fill).not.toBe('rgba(0, 0, 0, 0)');const headingRatio=contrast(heading.foreground,heading.background);expect(headingRatio).toBeGreaterThanOrEqual(3);contrasts.push({width,theme,control:'heading',...heading,ratio:headingRatio});
    await page.screenshot({path:path.join(out,`home-${width}-${theme}.png`)});
    await page.goto(base+'/zh/catalog/operations/?q=agent');await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    if(width===390){const menu=page.locator('.ak-section-menu');await menu.locator('summary').click();await expect(menu.getByRole('link',{name:'目录参考',exact:true})).toBeVisible();await page.keyboard.press('Escape');await expect(menu).not.toHaveAttribute('open','');const nav=await page.locator('.ak-nav').boundingBox();expect(nav.height).toBeLessThanOrEqual(66);}
    await page.screenshot({path:path.join(out,`catalog-${width}-${theme}.png`)});
    await page.goto(base+'/zh/catalog/schemas/ak.schema.agent_provision.v1/');await checkTextContrast('.ak-schema-viewer .ak-required',{width,theme});
   }
  }
  expect(errors.filter(error=>!error.includes('Failed to fetch dynamically imported module'))).toEqual([]);
  await fs.writeFile(path.join(out,'results.json'),JSON.stringify({passed:true,checks,contrasts,openapi_sha256:sha(canonical),browser_errors:errors},null,2));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
