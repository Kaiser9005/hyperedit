#!/usr/bin/env python3
"""Record ERP screen clips for tutorial videos using Playwright.

Each clip is a 10-15s screen recording of navigating an actual ERP page.
These clips replace static brand images in tutorial video scenes.

V-I-V: Real screen recordings, not static screenshots or stock images.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ERP_URL = "https://modules-rh-authentification-expert.vercel.app"
LOGIN_EMAIL = "ivanfodjo@hotmail.com"
LOGIN_PASSWORD = "Admin123!"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "erp_recordings"

# Each recording: key → { route, actions (scroll/click/wait), duration }
# Actions simulate real user behavior for authentic tutorial feel
RECORDING_MAP = {
    # ── Tutorial 1: Premiers Pas ──
    "login_page": {
        "route": "/login",
        "needs_auth": False,
        "duration": 8,
        "description": "Page de connexion ERP FOFAL",
        "actions": [
            {"type": "wait", "ms": 2000},
            {"type": "fill", "selector": "input[type='email']", "value": "demo@fofal.cm"},
            {"type": "wait", "ms": 1000},
            {"type": "fill", "selector": "input[type='password']", "value": "••••••••"},
            {"type": "wait", "ms": 2000},
        ],
    },
    "dashboard_main": {
        "route": "/dashboard",
        "duration": 12,
        "description": "Tableau de bord principal avec KPIs",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": -600},
            {"type": "wait", "ms": 2000},
        ],
    },
    "sidebar_navigation": {
        "route": "/dashboard",
        "duration": 10,
        "description": "Menu latéral de navigation",
        "actions": [
            {"type": "wait", "ms": 2000},
            {"type": "hover", "selector": "nav a, aside a, [role='navigation'] a"},
            {"type": "wait", "ms": 1500},
            {"type": "scroll_element", "selector": "nav, aside", "y": 200},
            {"type": "wait", "ms": 1500},
            {"type": "scroll_element", "selector": "nav, aside", "y": -200},
            {"type": "wait", "ms": 2000},
        ],
    },
    "help_onboarding": {
        "route": "/dashboard/help",
        "duration": 10,
        "description": "Centre d'aide et checklist d'onboarding",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -400},
            {"type": "wait", "ms": 2000},
        ],
    },

    # ── Tutorial 2: Employés et Paie ──
    "employee_list": {
        "route": "/dashboard/employees",
        "duration": 12,
        "description": "Liste des 34 employés actifs",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 2000},
            {"type": "scroll", "y": -600},
            {"type": "wait", "ms": 2000},
        ],
    },
    "employee_detail": {
        "route": "/dashboard/employees",
        "duration": 10,
        "description": "Dossier employé (clic sur premier employé)",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "click_first", "selector": "table tbody tr, [role='row']"},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 2000},
        ],
    },
    "payroll_main": {
        "route": "/dashboard/payroll",
        "duration": 10,
        "description": "Page principale de paie",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -400},
            {"type": "wait", "ms": 2000},
        ],
    },
    "payroll_calculator": {
        "route": "/dashboard/payroll/calculator",
        "duration": 10,
        "description": "Calculateur de paie CNPS/IRPP",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -300},
            {"type": "wait", "ms": 2000},
        ],
    },
    "payroll_advances": {
        "route": "/dashboard/payroll/advances",
        "duration": 10,
        "description": "Avances sur salaire",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -300},
            {"type": "wait", "ms": 2000},
        ],
    },

    # ── Tutorial 3: Travail Journalier ──
    "daily_work": {
        "route": "/dashboard/daily-work",
        "duration": 12,
        "description": "Saisie du travail journalier",
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
    "daily_work_operations": {
        "route": "/agriculture/operations",
        "duration": 10,
        "description": "Catalogue opérations plantation (125+)",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 500},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -500},
            {"type": "wait", "ms": 2000},
        ],
    },
    "daily_work_validation": {
        "route": "/dashboard/work-hours/validation",
        "duration": 10,
        "description": "Validation du travail journalier",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -300},
            {"type": "wait", "ms": 2000},
        ],
    },

    # ── Tutorial 4: Consulter mes infos ──
    "leaves_page": {
        "route": "/dashboard/leaves",
        "duration": 10,
        "description": "Page des congés",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -300},
            {"type": "wait", "ms": 2000},
        ],
    },
    "settings_user": {
        "route": "/dashboard/settings",
        "duration": 10,
        "description": "Paramètres utilisateur et préférences",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -400},
            {"type": "wait", "ms": 2000},
        ],
    },

    # ── Tutorial 5: Analytics et KPIs ──
    "analytics_dashboard": {
        "route": "/dashboard/analytics",
        "duration": 12,
        "description": "Suite analytique avancée",
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
    "analytics_reports": {
        "route": "/dashboard/analytics/department-reports",
        "duration": 10,
        "description": "Rapports départementaux",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -300},
            {"type": "wait", "ms": 2000},
        ],
    },
    "analytics_exports": {
        "route": "/dashboard/analytics/scheduled-exports",
        "duration": 10,
        "description": "Exports planifiés",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
        ],
    },

    # ── Tutorial 6: Agriculture ──
    "agriculture_main": {
        "route": "/agriculture",
        "duration": 12,
        "description": "Module agriculture principal",
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
    "agriculture_parcels": {
        "route": "/agriculture/parcels",
        "duration": 10,
        "description": "Gestion des 28 parcelles A-Z",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -400},
            {"type": "wait", "ms": 2000},
        ],
    },
    "agriculture_harvests": {
        "route": "/agriculture/harvests",
        "duration": 10,
        "description": "Suivi des récoltes",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
        ],
    },
    "agriculture_weather": {
        "route": "/agriculture/weather",
        "duration": 10,
        "description": "Données météo Ebondi",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -300},
            {"type": "wait", "ms": 2000},
        ],
    },
    "agriculture_crop_cycles": {
        "route": "/agriculture/crop-cycles",
        "duration": 10,
        "description": "Cycles de culture palmiers et papayes",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
        ],
    },

    # ── Tutorial 7: Ventes et CRM ──
    "sales_pipeline": {
        "route": "/dashboard/sales-crm",
        "duration": 12,
        "description": "Pipeline commercial",
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
    "sales_customers": {
        "route": "/dashboard/sales-crm/dashboard",
        "duration": 10,
        "description": "Gestion clients et scoring",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -400},
            {"type": "wait", "ms": 2000},
        ],
    },
    "sales_analytics": {
        "route": "/dashboard/sales-crm/analytics",
        "duration": 10,
        "description": "Analyses commerciales",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
        ],
    },

    # ── Tutorial 8: Stocks et Inventaire ──
    "inventory_dashboard": {
        "route": "/dashboard/inventory/dashboard",
        "duration": 12,
        "description": "Tableau de bord inventaire",
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
    "inventory_economat": {
        "route": "/dashboard/inventory/economat",
        "duration": 10,
        "description": "Économat (145 articles)",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -400},
            {"type": "wait", "ms": 2000},
        ],
    },
    "inventory_inputs": {
        "route": "/dashboard/inventory/agricultural-inputs",
        "duration": 10,
        "description": "Intrants agricoles",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
        ],
    },
    "inventory_counts": {
        "route": "/dashboard/inventory/counts",
        "duration": 10,
        "description": "Inventaires physiques et comptage",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
        ],
    },

    # ── Tutorial 9: GMAO ──
    "gmao_dashboard": {
        "route": "/dashboard/gmao",
        "duration": 12,
        "description": "Tableau de bord GMAO",
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
    "equipment_list": {
        "route": "/dashboard/equipment",
        "duration": 10,
        "description": "Liste des équipements",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": -400},
            {"type": "wait", "ms": 2000},
        ],
    },
    "equipment_iot": {
        "route": "/dashboard/equipment/iot-monitoring",
        "duration": 10,
        "description": "Monitoring IoT capteurs",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
        ],
    },
    "equipment_predictive": {
        "route": "/dashboard/equipment/predictive-maintenance",
        "duration": 10,
        "description": "Maintenance prédictive",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
        ],
    },

    # ── Tutorial 10: Comptabilité OHADA ──
    "accounting_dashboard": {
        "route": "/dashboard/accounting",
        "duration": 12,
        "description": "Tableau de bord comptable OHADA",
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
    "accounting_journals": {
        "route": "/dashboard/accounting/journals",
        "duration": 10,
        "description": "Journaux comptables",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
        ],
    },
    "accounting_entries": {
        "route": "/dashboard/accounting/entries",
        "duration": 10,
        "description": "Écritures comptables",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 300},
            {"type": "wait", "ms": 3000},
        ],
    },
    "accounting_reports": {
        "route": "/dashboard/accounting/reports",
        "duration": 10,
        "description": "Rapports financiers OHADA",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
        ],
    },
    "accounting_chart": {
        "route": "/dashboard/accounting/chart-of-accounts",
        "duration": 10,
        "description": "Plan comptable OHADA",
        "actions": [
            {"type": "wait", "ms": 3000},
            {"type": "scroll", "y": 400},
            {"type": "wait", "ms": 3000},
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
    elif atype == "scroll_element":
        try:
            el = page.locator(action["selector"]).first
            await el.evaluate(f"el => el.scrollBy(0, {action['y']})")
            await page.wait_for_timeout(500)
        except Exception:
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
    elif atype == "hover":
        try:
            el = page.locator(action["selector"]).first
            await el.hover(timeout=3000)
        except Exception:
            pass


async def record_screens():
    """Login to ERP and record screen clips for each tutorial scene."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ── Record login page (before auth) ──
        print("Recording login_page ...")
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR",
            record_video_dir=str(OUTPUT_DIR / "_tmp_login"),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        await page.goto(f"{ERP_URL}/login", wait_until="networkidle", timeout=30000)
        login_config = RECORDING_MAP["login_page"]
        for action in login_config["actions"]:
            await execute_action(page, action)

        await page.close()
        await context.close()

        # Move video to correct name
        tmp_login = OUTPUT_DIR / "_tmp_login"
        if tmp_login.exists():
            vids = list(tmp_login.glob("*.webm"))
            if vids:
                final_path = OUTPUT_DIR / "login_page.webm"
                vids[0].rename(final_path)
                print(f"  [OK] login_page.webm ({final_path.stat().st_size // 1024}KB)")
                results["login_page"] = str(final_path)
            import shutil
            shutil.rmtree(tmp_login, ignore_errors=True)

        # ── Login and record all other pages ──
        print("\nLogging in ...")
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR",
        )
        page = await context.new_page()

        await page.goto(f"{ERP_URL}/login", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Login
        try:
            await page.fill("input[type='email']", LOGIN_EMAIL, timeout=5000)
            await page.fill("input[type='password']", LOGIN_PASSWORD, timeout=5000)
            await page.click("button[type='submit']", timeout=5000)
            await page.wait_for_url("**/dashboard**", timeout=15000)
            print("  Logged in!\n")
        except Exception as e:
            print(f"  Login failed: {e}")
            try:
                inputs = page.locator("input")
                await inputs.first.fill(LOGIN_EMAIL)
                await page.locator("input[type='password']").fill(LOGIN_PASSWORD)
                await page.locator("button").filter(has_text="Connexion").first.click()
                await page.wait_for_timeout(5000)
                print("  Logged in (alt)!\n")
            except Exception as e2:
                print(f"  Login failed completely: {e2}")
                await browser.close()
                return results

        await page.close()
        await context.close()

        # Now get cookies/storage for auth persistence
        # Re-create context with auth
        auth_context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR",
        )
        auth_page = await auth_context.new_page()
        await auth_page.goto(f"{ERP_URL}/login", wait_until="networkidle", timeout=30000)
        await auth_page.wait_for_timeout(1000)
        await auth_page.fill("input[type='email']", LOGIN_EMAIL, timeout=5000)
        await auth_page.fill("input[type='password']", LOGIN_PASSWORD, timeout=5000)
        await auth_page.click("button[type='submit']", timeout=5000)
        await auth_page.wait_for_url("**/dashboard**", timeout=15000)
        await auth_page.wait_for_timeout(3000)

        # Save storage state
        storage_path = OUTPUT_DIR / "_auth_state.json"
        storage = await auth_context.storage_state(path=str(storage_path))
        await auth_page.close()
        await auth_context.close()
        print("  Auth state saved.\n")

        # ── Record each page ──
        total = len(RECORDING_MAP)
        for i, (key, config) in enumerate(RECORDING_MAP.items(), 1):
            if key == "login_page":
                continue
            if config.get("needs_auth") is False:
                continue

            route = config["route"]
            desc = config["description"]
            print(f"  [{i}/{total}] {key}: {route} ...")

            try:
                # Create context with video recording + auth
                rec_dir = OUTPUT_DIR / f"_tmp_{key}"
                rec_dir.mkdir(parents=True, exist_ok=True)

                rec_context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    locale="fr-FR",
                    record_video_dir=str(rec_dir),
                    record_video_size={"width": 1920, "height": 1080},
                    storage_state=str(storage_path),
                )
                rec_page = await rec_context.new_page()

                await rec_page.goto(
                    f"{ERP_URL}{route}",
                    wait_until="networkidle",
                    timeout=25000,
                )
                await rec_page.wait_for_timeout(2000)

                # Execute recording actions
                for action in config.get("actions", []):
                    await execute_action(rec_page, action)

                # Close to finalize video
                video_path = await rec_page.video.path()
                await rec_page.close()
                await rec_context.close()

                # Move video to correct name
                final_path = OUTPUT_DIR / f"{key}.webm"
                if video_path and Path(video_path).exists():
                    Path(video_path).rename(final_path)
                    size_kb = final_path.stat().st_size // 1024
                    print(f"       [OK] {size_kb}KB — {desc}")
                    results[key] = str(final_path)
                else:
                    # Check tmp dir for the video
                    vids = list(rec_dir.glob("*.webm"))
                    if vids:
                        vids[0].rename(final_path)
                        size_kb = final_path.stat().st_size // 1024
                        print(f"       [OK] {size_kb}KB — {desc}")
                        results[key] = str(final_path)
                    else:
                        print(f"       [FAIL] No video file created")
                        results[key] = None

                # Cleanup tmp dir
                import shutil
                shutil.rmtree(rec_dir, ignore_errors=True)

            except Exception as e:
                print(f"       [FAIL] {e}")
                results[key] = None
                import shutil
                shutil.rmtree(OUTPUT_DIR / f"_tmp_{key}", ignore_errors=True)

        await browser.close()

    # Cleanup auth state
    (OUTPUT_DIR / "_auth_state.json").unlink(missing_ok=True)

    # ── Convert webm to mp4 for pipeline compatibility ──
    print("\n=== Converting webm → mp4 ===")
    import subprocess
    for key, path in list(results.items()):
        if path and path.endswith(".webm"):
            mp4_path = path.replace(".webm", ".mp4")
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", path,
                        "-c:v", "libx264", "-preset", "fast",
                        "-crf", "23", "-pix_fmt", "yuv420p",
                        "-an",  # no audio in screen recordings
                        mp4_path,
                    ],
                    capture_output=True,
                    timeout=60,
                )
                if Path(mp4_path).exists():
                    size_kb = Path(mp4_path).stat().st_size // 1024
                    print(f"  {key}: {size_kb}KB mp4")
                    results[key] = mp4_path
                    Path(path).unlink()  # remove webm
            except Exception as e:
                print(f"  {key}: conversion failed: {e}")

    # ── Summary ──
    captured = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if v is None)
    print(f"\n=== Recording Summary ===")
    print(f"Total: {len(results)} | Captured: {captured} | Failed: {failed}")

    manifest = {
        "base_dir": str(OUTPUT_DIR),
        "erp_url": ERP_URL,
        "recordings": results,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest: {manifest_path}")

    return results


if __name__ == "__main__":
    start = time.time()
    results = asyncio.run(record_screens())
    elapsed = time.time() - start
    failed = sum(1 for v in results.values() if v is None)
    print(f"\nTotal time: {elapsed:.0f}s")
    sys.exit(1 if failed > 5 else 0)
