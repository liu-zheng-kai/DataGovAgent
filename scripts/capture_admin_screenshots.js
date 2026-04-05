const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const IMAGES_DIR = path.join(ROOT, "docs", "images");
const PYTHON_EXE = path.join(ROOT, ".venv", "Scripts", "python.exe");
const BASE_URL = "http://127.0.0.1:8000";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function checkHealthOnce() {
  return new Promise((resolve) => {
    const req = http.get(`${BASE_URL}/health`, (res) => {
      resolve(res.statusCode === 200);
      res.resume();
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForHealth(maxMs = 45000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < maxMs) {
    if (await checkHealthOnce()) return true;
    await sleep(1000);
  }
  return false;
}

async function capture() {
  fs.mkdirSync(IMAGES_DIR, { recursive: true });

  let uvicornProc = null;
  let startedByScript = false;

  if (!(await checkHealthOnce())) {
    startedByScript = true;
    uvicornProc = spawn(
      PYTHON_EXE,
      ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
      {
        cwd: ROOT,
        stdio: "ignore",
        windowsHide: true,
      }
    );
  }

  const ready = await waitForHealth();
  if (!ready) {
    throw new Error("Service not ready on http://127.0.0.1:8000");
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 980 } });

  try {
    await page.goto(`${BASE_URL}/admin`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await page.screenshot({
      path: path.join(IMAGES_DIR, "admin_overview.png"),
      fullPage: true,
    });

    await page.click('button.menu-item[data-view="chat"]');
    await page.waitForSelector("#chat-timeline", { timeout: 10000 });
    await page.waitForTimeout(1200);
    const sessionCount = await page.locator(".chat-session-item").count();
    if (sessionCount > 0) {
      await page.locator(".chat-session-item").first().click();
      await page.waitForTimeout(1200);
    }
    await page.screenshot({
      path: path.join(IMAGES_DIR, "chat_effect.png"),
      fullPage: true,
    });

    await page.click('button.menu-item[data-view="prompt-templates"]');
    await page.waitForSelector("#pt-table-wrap", { timeout: 10000 });
    await page.waitForTimeout(1200);
    await page.screenshot({
      path: path.join(IMAGES_DIR, "prompt_template_effect.png"),
      fullPage: true,
    });
  } finally {
    await browser.close();
    if (startedByScript && uvicornProc) {
      uvicornProc.kill();
    }
  }
}

capture()
  .then(() => {
    console.log("Screenshots captured under docs/images");
  })
  .catch((err) => {
    console.error(err?.stack || String(err));
    process.exit(1);
  });

