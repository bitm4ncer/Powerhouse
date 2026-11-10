---
name: browser-qa
description: Test a web UI in a real browser with Playwright and produce evidence. Use for "test the UI", "browser check", "screenshot", "responsive", "console errors", "broken links", "login flow", "before I ship", or when a visual or interaction bug needs proof. Covers screenshots at breakpoints, console and network failures, auth state, forms, and accessibility.
---

# Browser QA

A page that returns 200 can still be broken. Drive the real app, capture what the
user would see, and report evidence, not impressions.

## Setup

```sh
npm i -D @playwright/test
npx playwright install chromium
```

For a one-off check, `npx playwright` is enough; for a suite, add
`playwright.config.ts` with `use: { baseURL, trace: 'on-first-retry' }`.

## The base check

```js
import { chromium } from 'playwright';

const url = process.env.URL || 'http://localhost:3000';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const problems = [];
page.on('console', m => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
page.on('pageerror', e => problems.push(`pageerror: ${e.message}`));
page.on('requestfailed', r => problems.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`));

const res = await page.goto(url, { waitUntil: 'networkidle' });
if (!res || res.status() >= 400) problems.push(`status: ${res?.status()}`);

await page.screenshot({ path: 'qa/desktop.png', fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: 'qa/mobile.png', fullPage: true });

console.log(JSON.stringify({ status: res?.status(), problems }, null, 2));
await browser.close();
```

Run it with `node qa.js` or as a Playwright test. Keep the screenshots; they are
the evidence.

## Breakpoints

Always check at least 390 (phone), 768 (tablet), and 1440 (desktop). Look for:
horizontal scroll, clipped text, overlapping fixed elements, tap targets under
44 px, and content that disappears.

```js
for (const [name, width, height] of [['phone', 390, 844], ['tablet', 768, 1024], ['desktop', 1440, 900]]) {
  await page.setViewportSize({ width, height });
  await page.screenshot({ path: `qa/${name}.png`, fullPage: true });
}
```

## Auth without repeating the login

```js
await page.goto('/login');
await page.fill('input[name=email]', process.env.QA_USER);
await page.fill('input[name=password]', process.env.QA_PASS);
await page.click('button[type=submit]');
await page.waitForURL('/dashboard');
await page.context().storageState({ path: 'qa/auth.json' });
```

Reuse it with `newContext({ storageState: 'qa/auth.json' })`. Never commit
`qa/auth.json`.

## Interaction checks

- Forms: submit empty, submit invalid, submit valid; check the success state.
- Navigation: every link in the header and footer returns < 400.
- Keyboard: Tab through the main flow; the focus ring must be visible.
- Loading: throttle the network (`page.route('**/*', r => setTimeout(() => r.continue(), 300))`)
  and check the skeleton, not just the fast path.
- Error states: force a 500 on the main API and confirm the UI shows a message.

## Accessibility (optional)

```sh
npm i -D @axe-core/playwright
```

```js
const results = await new AxeBuilder({ page }).analyze();
console.log(results.violations.map(v => `${v.id}: ${v.nodes.length}`));
```

Fix missing labels, contrast, and landmarks first; they are the highest-value
findings.

## Report

| Check | Result | Evidence |
| --- | --- | --- |
| Load (status, console, failed requests) | pass/fail | `qa/desktop.png`, log |
| Responsive 390/768/1440 | pass/fail | screenshots |
| Main flow | pass/fail | steps + screenshot |
| Error state | pass/fail | screenshot |

State what was **not** tested (payments, real emails, third-party OAuth) so the
result is not overread.

## Rules

- Test the real app and the real API unless the user asks for mocks.
- Never run destructive flows against production; use a test account and test data.
- Clean up created records and files.
- A passing screenshot is not a passing flow: assert the state, not only the pixels.
