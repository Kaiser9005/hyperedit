#!/usr/bin/env python3
"""Record additional ERP screen clips for tutorials 11-13.

Only records the 2 pages not yet captured:
- forgot_password (no auth needed)
- security_dashboard (admin page)
"""

import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from playwright.async_api import async_playwright

ERP_URL = "https://modules-rh-authentification-expert.vercel.app"
LOGIN_EMAIL = "ivanfodjo@hotmail.com"
LOGIN_PASSWORD = "Admin123!"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "erp_recordings"

EXTRA_RECORDINGS = {
    "forgot_password": {
        "route": "/forgot-password",
        "needs_auth": False,
        "duration": 10,
        "description": "Page de reinitialisation de mot de passe",
        "actions": [
            {"type": "wait", "ms": 2000},
            {"type": "fill", "selector": "input[type='email']", "value": "demo@example.com"},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": 200},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": -200},
            {"type": "wait", "ms": 2000},
        ],
    },
    "security_dashboard": {
        "route": "/admin/security",
        "needs_auth": True,
        "duration": 12,
        "description": "Tableau de bord securite administrateur",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": -800},
            {"type": "wait", "ms": 2000},
        ],
    },
}


async def execute_action(page, action):
    """Execute a single recording action."""
    atype = action["type"]
    if atype == "wait":
        await page.wait_for_timeout(action["ms"])
    elif atype == "scroll":
        await page.mouse.wheel(0, action["y"])
        await page.wait_for_timeout(500)
    elif atype == "fill":
        try:
            await page.fill(action["selector"], action["value"], timeout=3000)
        except Exception:
            pass
    elif atype == "click_first":
        try:
            el = page.locator(action["selector"]).first
            await el.click(timeout=3000)
        except Exception:
            pass


async def record_page(browser, key, config, storage_path: Optional[str] = None):
    """Record a single page."""
    rec_dir = OUTPUT_DIR / f"_tmp_{key}"
    rec_dir.mkdir(parents=True, exist_ok=True)

    ctx_args = {
        "viewport": {"width": 1920, "height": 1080},
        "locale": "fr-FR",
        "record_video_dir": str(rec_dir),
        "record_video_size": {"width": 1920, "height": 1080},
    }
    if storage_path and config.get("needs_auth", True):
        ctx_args["storage_state"] = storage_path

    context = await browser.new_context(**ctx_args)
    page = await context.new_page()

    route = config["route"]
    await page.goto(f"{ERP_URL}{route}", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)

    for action in config.get("actions", []):
        await execute_action(page, action)

    video_path = await page.video.path()
    await page.close()
    await context.close()

    # Move video
    final_path = OUTPUT_DIR / f"{key}.webm"
    if video_path and Path(video_path).exists():
        Path(video_path).rename(final_path)
    else:
        vids = list(rec_dir.glob("*.webm"))
        if vids:
            vids[0].rename(final_path)
        else:
            shutil.rmtree(rec_dir, ignore_errors=True)
            return None

    shutil.rmtree(rec_dir, ignore_errors=True)
    return str(final_path)


async def record_extra_screens():
    """Record the 2 extra pages needed for tutorials 11-13."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Record forgot_password (no auth needed)
        print("Recording forgot_password ...")
        path = await record_page(browser, "forgot_password", EXTRA_RECORDINGS["forgot_password"])
        if path:
            print(f"  [OK] {Path(path).stat().st_size // 1024}KB")
            results["forgot_password"] = path
        else:
            print("  [FAIL]")
            results["forgot_password"] = None

        # Login for auth-required pages
        print("\nLogging in for auth pages ...")
        auth_context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR",
        )
        auth_page = await auth_context.new_page()
        await auth_page.goto(f"{ERP_URL}/login", wait_until="networkidle", timeout=30000)
        await auth_page.wait_for_timeout(1000)

        try:
            await auth_page.fill("input[type='email']", LOGIN_EMAIL, timeout=5000)
            await auth_page.fill("input[type='password']", LOGIN_PASSWORD, timeout=5000)
            await auth_page.click("button[type='submit']", timeout=5000)
            await auth_page.wait_for_url("**/dashboard**", timeout=15000)
            await auth_page.wait_for_timeout(3000)
            print("  Logged in!")
        except Exception as e:
            print(f"  Login failed: {e}")
            try:
                await auth_page.locator("input").first.fill(LOGIN_EMAIL)
                await auth_page.locator("input[type='password']").fill(LOGIN_PASSWORD)
                await auth_page.locator("button").filter(has_text="Connexion").first.click()
                await auth_page.wait_for_timeout(5000)
                print("  Logged in (alt)!")
            except Exception as e2:
                print(f"  Login failed completely: {e2}")
                await browser.close()
                return results

        storage_path = str(OUTPUT_DIR / "_auth_state_extra.json")
        await auth_context.storage_state(path=storage_path)
        await auth_page.close()
        await auth_context.close()

        # Record security_dashboard
        print("\nRecording security_dashboard ...")
        path = await record_page(
            browser, "security_dashboard",
            EXTRA_RECORDINGS["security_dashboard"],
            storage_path=storage_path,
        )
        if path:
            print(f"  [OK] {Path(path).stat().st_size // 1024}KB")
            results["security_dashboard"] = path
        else:
            print("  [FAIL]")
            results["security_dashboard"] = None

        await browser.close()

    # Cleanup
    Path(OUTPUT_DIR / "_auth_state_extra.json").unlink(missing_ok=True)

    # Convert webm to mp4
    print("\n=== Converting webm -> mp4 ===")
    for key, path in list(results.items()):
        if path and path.endswith(".webm"):
            mp4_path = path.replace(".webm", ".mp4")
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", path,
                        "-c:v", "libx264", "-preset", "fast",
                        "-crf", "23", "-pix_fmt", "yuv420p",
                        "-an", mp4_path,
                    ],
                    capture_output=True,
                    timeout=60,
                )
                if Path(mp4_path).exists() and Path(mp4_path).stat().st_size > 100:
                    size_kb = Path(mp4_path).stat().st_size // 1024
                    print(f"  {key}: {size_kb}KB mp4")
                    results[key] = mp4_path
                    Path(path).unlink()
                else:
                    print(f"  {key}: mp4 too small or missing, keeping webm")
            except Exception as e:
                print(f"  {key}: conversion failed: {e}")

    captured = sum(1 for v in results.values() if v)
    print(f"\n=== Extra Recording Summary ===")
    print(f"Total: {len(results)} | Captured: {captured}")
    return results


if __name__ == "__main__":
    start = time.time()
    results = asyncio.run(record_extra_screens())
    elapsed = time.time() - start
    print(f"Time: {elapsed:.0f}s")
    failed = sum(1 for v in results.values() if v is None)
    sys.exit(1 if failed > 0 else 0)
