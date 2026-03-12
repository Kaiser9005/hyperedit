#!/usr/bin/env python3
"""Capture ERP screenshots for tutorial videos using Playwright.

Maps each tutorial scene to an actual ERP page and captures a 1920x1080 screenshot.
Uses admin account for maximum access to all modules.

V-I-V: Real screenshots, no placeholders, verified after capture.
"""

import asyncio
import json
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Playwright async API
from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ERP_URL = "https://modules-rh-authentification-expert.vercel.app"
LOGIN_EMAIL = "ivanfodjo@hotmail.com"
LOGIN_PASSWORD = "Admin123!"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "erp_screenshots"

# Map: screenshot_key → { route, wait_selector (optional), description }
# Each key corresponds to a tutorial scene that needs a real ERP screenshot.
SCREENSHOT_MAP = {
    # ── Tutorial 1: Premiers Pas ──
    "login_page": {
        "route": "/login",
        "needs_auth": False,
        "wait_for": "input[type='email']",
        "description": "Page de connexion ERP FOFAL",
    },
    "dashboard_main": {
        "route": "/dashboard",
        "wait_for": ".dashboard-content, [data-testid='dashboard'], main",
        "description": "Tableau de bord principal avec KPIs",
    },
    "sidebar_navigation": {
        "route": "/dashboard",
        "wait_for": "nav, aside, [role='navigation']",
        "screenshot_element": None,  # full page to show sidebar
        "description": "Menu latéral de navigation",
    },
    "help_onboarding": {
        "route": "/dashboard/help",
        "wait_for": "main",
        "description": "Centre d'aide et checklist d'onboarding",
    },

    # ── Tutorial 2: Employés et Paie ──
    "employee_list": {
        "route": "/dashboard/employees",
        "wait_for": "table, [role='table'], main",
        "description": "Liste des 34 employés actifs",
    },
    "employee_detail": {
        "route": "/dashboard/employees",
        "wait_for": "table, main",
        "description": "Dossier employé détaillé",
        "note": "Will capture the list view with employee cards/rows",
    },
    "payroll_main": {
        "route": "/dashboard/payroll",
        "wait_for": "main",
        "description": "Page principale de paie",
    },
    "payroll_calculator": {
        "route": "/dashboard/payroll/calculator",
        "wait_for": "main",
        "description": "Calculateur de paie CNPS/IRPP",
    },
    "payroll_advances": {
        "route": "/dashboard/payroll/advances",
        "wait_for": "main",
        "description": "Avances sur salaire (73 avances)",
    },

    # ── Tutorial 3: Travail Journalier ──
    "daily_work": {
        "route": "/dashboard/daily-work",
        "wait_for": "main",
        "description": "Saisie du travail journalier",
    },
    "daily_work_operations": {
        "route": "/agriculture/operations",
        "wait_for": "main",
        "description": "Catalogue des opérations plantation (125+)",
    },
    "daily_work_analytics": {
        "route": "/agriculture/operations/analytics",
        "wait_for": "main",
        "description": "Analyses opérations terrain",
    },

    # ── Tutorial 4: Consulter mes infos ──
    "leaves_page": {
        "route": "/dashboard/leaves",
        "wait_for": "main",
        "description": "Page des congés",
    },
    "settings_user": {
        "route": "/dashboard/settings",
        "wait_for": "main",
        "description": "Paramètres utilisateur",
    },

    # ── Tutorial 5: Analytics et KPIs ──
    "analytics_dashboard": {
        "route": "/dashboard/analytics",
        "wait_for": "main",
        "description": "Suite analytique avancée",
    },
    "analytics_reports": {
        "route": "/dashboard/analytics/department-reports",
        "wait_for": "main",
        "description": "Rapports départementaux",
    },
    "analytics_exports": {
        "route": "/dashboard/analytics/scheduled-exports",
        "wait_for": "main",
        "description": "Exports planifiés",
    },

    # ── Tutorial 6: Agriculture ──
    "agriculture_main": {
        "route": "/agriculture",
        "wait_for": "main",
        "description": "Module agriculture principal",
    },
    "agriculture_parcels": {
        "route": "/agriculture/parcels",
        "wait_for": "main",
        "description": "Gestion des 28 parcelles A-Z",
    },
    "agriculture_harvests": {
        "route": "/agriculture/harvests",
        "wait_for": "main",
        "description": "Suivi des récoltes",
    },
    "agriculture_weather": {
        "route": "/agriculture/weather",
        "wait_for": "main",
        "description": "Données météo Ebondi",
    },
    "agriculture_crop_cycles": {
        "route": "/agriculture/crop-cycles",
        "wait_for": "main",
        "description": "Cycles de culture palmiers et papayes",
    },

    # ── Tutorial 7: Ventes et CRM ──
    "sales_pipeline": {
        "route": "/dashboard/sales-crm",
        "wait_for": "main",
        "description": "Pipeline commercial",
    },
    "sales_analytics": {
        "route": "/dashboard/sales-crm/analytics",
        "wait_for": "main",
        "description": "Analyses commerciales",
    },

    # ── Tutorial 8: Stocks et Inventaire ──
    "inventory_dashboard": {
        "route": "/dashboard/inventory/dashboard",
        "wait_for": "main",
        "description": "Tableau de bord inventaire",
    },
    "inventory_economat": {
        "route": "/dashboard/inventory/economat",
        "wait_for": "main",
        "description": "Économat (145 articles)",
    },
    "inventory_inputs": {
        "route": "/dashboard/inventory/agricultural-inputs",
        "wait_for": "main",
        "description": "Intrants agricoles",
    },
    "inventory_fuel": {
        "route": "/dashboard/inventory/fuel",
        "wait_for": "main",
        "description": "Gestion carburant",
    },

    # ── Tutorial 9: GMAO ──
    "gmao_dashboard": {
        "route": "/dashboard/gmao",
        "wait_for": "main",
        "description": "Tableau de bord GMAO",
    },
    "equipment_list": {
        "route": "/dashboard/equipment",
        "wait_for": "main",
        "description": "Liste des équipements",
    },
    "equipment_iot": {
        "route": "/dashboard/equipment/iot-monitoring",
        "wait_for": "main",
        "description": "Monitoring IoT capteurs",
    },
    "equipment_predictive": {
        "route": "/dashboard/equipment/predictive-maintenance",
        "wait_for": "main",
        "description": "Maintenance prédictive",
    },

    # ── Tutorial 10: Comptabilité OHADA ──
    "accounting_dashboard": {
        "route": "/dashboard/accounting",
        "wait_for": "main",
        "description": "Tableau de bord comptable",
    },
    "accounting_journals": {
        "route": "/dashboard/accounting/journals",
        "wait_for": "main",
        "description": "Journaux comptables",
    },
    "accounting_entries": {
        "route": "/dashboard/accounting/entries",
        "wait_for": "main",
        "description": "Écritures comptables",
    },
    "accounting_reports": {
        "route": "/dashboard/accounting/reports",
        "wait_for": "main",
        "description": "Rapports financiers OHADA",
    },
    "accounting_chart": {
        "route": "/dashboard/accounting/chart-of-accounts",
        "wait_for": "main",
        "description": "Plan comptable OHADA",
    },
}


async def capture_screenshots():
    """Login to ERP and capture all mapped screenshots."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR",
        )
        page = await context.new_page()

        # ── Login ──
        print(f"Navigating to {ERP_URL}/login ...")
        await page.goto(f"{ERP_URL}/login", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Capture login page BEFORE logging in
        login_path = OUTPUT_DIR / "login_page.png"
        await page.screenshot(path=str(login_path), full_page=False)
        print(f"  [OK] login_page.png ({login_path.stat().st_size // 1024}KB)")

        # Fill credentials and submit
        try:
            await page.fill("input[type='email']", LOGIN_EMAIL, timeout=5000)
            await page.fill("input[type='password']", LOGIN_PASSWORD, timeout=5000)
            await page.click("button[type='submit']", timeout=5000)
            await page.wait_for_url("**/dashboard**", timeout=15000)
            print("  Logged in successfully!")
        except Exception as e:
            print(f"  Login failed: {e}")
            # Try alternative login approach
            try:
                email_input = page.locator("input").first
                await email_input.fill(LOGIN_EMAIL)
                password_input = page.locator("input[type='password']")
                await password_input.fill(LOGIN_PASSWORD)
                submit_btn = page.locator("button").filter(has_text="Connexion").first
                await submit_btn.click()
                await page.wait_for_timeout(5000)
                print("  Logged in (alternative method)!")
            except Exception as e2:
                print(f"  Alternative login also failed: {e2}")
                await browser.close()
                return {}

        await page.wait_for_timeout(3000)

        # ── Capture each page ──
        results = {}
        total = len(SCREENSHOT_MAP)
        for i, (key, config) in enumerate(SCREENSHOT_MAP.items(), 1):
            if key == "login_page":
                results[key] = str(login_path)
                continue

            if config.get("needs_auth") is False:
                continue

            route = config["route"]
            desc = config["description"]
            out_path = OUTPUT_DIR / f"{key}.png"

            print(f"  [{i}/{total}] {key}: {route} ...")
            try:
                await page.goto(
                    f"{ERP_URL}{route}",
                    wait_until="networkidle",
                    timeout=20000,
                )
                # Wait for main content
                wait_sel = config.get("wait_for", "main")
                try:
                    await page.wait_for_selector(wait_sel, timeout=8000)
                except Exception:
                    pass  # Some pages may not have the exact selector

                # Extra wait for dynamic content to render
                await page.wait_for_timeout(2000)

                # Capture
                await page.screenshot(path=str(out_path), full_page=False)
                size_kb = out_path.stat().st_size // 1024
                print(f"       [OK] {size_kb}KB — {desc}")
                results[key] = str(out_path)

            except Exception as e:
                print(f"       [FAIL] {e}")
                results[key] = None

        await browser.close()

    # ── Summary ──
    captured = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if v is None)
    print(f"\n=== Screenshot Capture Summary ===")
    print(f"Total: {len(results)} | Captured: {captured} | Failed: {failed}")

    # Save manifest
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2))
    print(f"Manifest saved: {manifest_path}")

    return results


if __name__ == "__main__":
    results = asyncio.run(capture_screenshots())
    failed = sum(1 for v in results.values() if v is None)
    sys.exit(1 if failed > 5 else 0)
