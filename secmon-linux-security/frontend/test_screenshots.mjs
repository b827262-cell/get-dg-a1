import { chromium, firefox } from 'playwright';
import { join } from 'path';

const artifactDir = '/home/b822726/.gemini/antigravity-cli/brain/6ec0c049-cb14-450a-b866-683c5a1a8d5b';

async function run() {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    console.log("Launched Chromium successfully!");
  } catch (err) {
    console.log("Chromium failed, trying Firefox...", err);
    browser = await firefox.launch({ headless: true });
    console.log("Launched Firefox successfully!");
  }

  // 1. Login mobile version (375x667)
  const mobileContext = await browser.newContext({
    viewport: { width: 375, height: 667 }
  });
  const mobilePage = await mobileContext.newPage();
  await mobilePage.goto('http://127.0.0.1:8000/#/login');
  await mobilePage.waitForSelector('input[autocomplete="username"]');
  await mobilePage.screenshot({ path: join(artifactDir, 'login_mobile.png') });
  console.log("Login mobile screenshot captured.");

  // 2. Login desktop version (1440x900)
  const desktopContext = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await desktopContext.newPage();
  await page.goto('http://127.0.0.1:8000/#/login');
  await page.waitForSelector('input[autocomplete="username"]');

  // Perform login
  await page.fill('input[autocomplete="username"]', 'admin');
  await page.fill('input[type="password"]', 'correct-horse-battery-staple');
  await page.click('button[type="submit"]');
  
  // Wait for dashboard elements
  await page.waitForSelector('.stats-grid', { timeout: 10000 });
  await page.screenshot({ path: join(artifactDir, 'dashboard_desktop.png') });
  console.log("Dashboard desktop screenshot captured.");

  // 3. Login mobile version to dashboard
  await mobilePage.fill('input[autocomplete="username"]', 'admin');
  await mobilePage.fill('input[type="password"]', 'correct-horse-battery-staple');
  await mobilePage.click('button[type="submit"]');
  
  await mobilePage.waitForSelector('.stats-grid', { timeout: 10000 });
  await mobilePage.screenshot({ path: join(artifactDir, 'dashboard_mobile.png') });
  console.log("Dashboard mobile screenshot captured.");

  // 4. Mobile navigation drawer open screenshot
  await mobilePage.waitForSelector('.header-mobile-menu-btn');
  await mobilePage.click('.header-mobile-menu-btn');
  await mobilePage.waitForSelector('.sidebar.mobile-open', { timeout: 5000 });
  await mobilePage.screenshot({ path: join(artifactDir, 'mobile_navigation.png') });
  console.log("Mobile navigation screenshot captured.");

  // Close the mobile navigation drawer safely via JS evaluation to avoid click interception
  await mobilePage.evaluate(() => {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.querySelector('.mobile-nav-backdrop');
    if (sidebar) sidebar.classList.remove('mobile-open');
    if (backdrop) backdrop.classList.remove('show');
  });
  await mobilePage.waitForTimeout(500);

  // Navigate rest of the pages on desktop
  const routes = [
    ['events', 'events.png'],
    ['attackers', 'attack_ips.png'],
    ['alerts', 'alerts.png'],
    ['rules', 'rules.png'],
    ['operations', 'operations.png'],
    ['allowlist', 'allowlist.png'],
    ['audit', 'audit_log.png'],
    ['admin', 'users.png']
  ];

  for (const [route, filename] of routes) {
    await page.goto(`http://127.0.0.1:8000/#/${route}`);
    await page.waitForSelector('.table-container, .empty-state, .error-state', { timeout: 10000 });
    await page.screenshot({ path: join(artifactDir, filename) });
    console.log(`Screenshot for route #${route} captured to ${filename}`);
  }

  await browser.close();
  console.log("All screenshots captured successfully!");
}

run().catch(console.error);
