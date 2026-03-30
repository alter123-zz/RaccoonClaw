#!/usr/bin/env node

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import readline from "node:readline/promises";

const STATE_ROOT = path.join(os.homedir(), ".openclaw", "playwright-community-publisher");
const AUTH_ROOT = path.join(STATE_ROOT, "auth");
const ARTIFACT_ROOT = path.join(STATE_ROOT, "artifacts", "auth");

const LOGIN_URLS = {
  xueqiu: "https://xueqiu.com/",
  futu: "https://www.futunn.com/",
  tiger: "https://www.itiger.com/",
};

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    console.error(
      JSON.stringify(
        {
          status: "blocked",
          reason: "missing_dependency",
          message: "未安装 playwright，请先在可联网环境执行 npm install playwright",
          detail: String(error?.message || error),
        },
        null,
        2,
      ),
    );
    process.exit(2);
  }
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
      continue;
    }
    args[key] = next;
    i += 1;
  }
  return args;
}

async function ensureDir(targetPath) {
  await fs.mkdir(targetPath, { recursive: true });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const site = args.site;
  if (!site || !LOGIN_URLS[site]) {
    console.error("Usage: node scripts/save_auth_state.mjs --site <xueqiu|futu|tiger> [--login-url <url>] [--headless true|false]");
    process.exit(1);
  }

  const loginUrl = args["login-url"] || LOGIN_URLS[site];
  const headless = ["1", "true", "yes"].includes(String(args.headless || "").toLowerCase());

  await ensureDir(AUTH_ROOT);
  await ensureDir(ARTIFACT_ROOT);

  const storageStatePath = args["storage-state"] || path.join(AUTH_ROOT, `${site}.json`);
  const screenshotPath = path.join(ARTIFACT_ROOT, `${site}-login-ready.png`);

  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(loginUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  console.log(`请在打开的浏览器里完成 ${site} 登录，然后回到终端按回车保存登录态。`);

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  await rl.question("登录完成后按回车继续...");
  await rl.close();

  await page.screenshot({ path: screenshotPath, fullPage: true });
  await context.storageState({ path: storageStatePath });
  await context.close();
  await browser.close();

  console.log(
    JSON.stringify(
      {
        status: "ok",
        site,
        storageStatePath,
        screenshotPath,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(
    JSON.stringify(
      {
        status: "blocked",
        reason: "auth_capture_failed",
        message: String(error?.message || error),
      },
      null,
      2,
    ),
  );
  process.exit(3);
});
