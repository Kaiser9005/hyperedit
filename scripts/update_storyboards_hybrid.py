#!/usr/bin/env python3
"""Update ERP tutorial storyboards to use hybrid scene types.

Maps each scene to either:
- "ui_recording" with a recording_path (for ERP interface scenes)
- "branding" (for intro/outro scenes using FOFAL brand images)

V-I-V: Real ERP recordings for UI scenes, brand images only for cinematic intro/outro.
"""

import json
from pathlib import Path

STORYBOARD_DIR = Path(__file__).resolve().parent.parent / "templates" / "storyboards" / "erp_tutorials"
RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "assets" / "erp_recordings"

# Map: (storyboard_file, scene_id) → recording_key
# Scenes NOT in this map remain "branding" (brand image + Ken Burns)
SCENE_TO_RECORDING = {
    # ── Tutorial 1: Premiers Pas ──
    ("01_premiers_pas.json", 1): None,  # Intro → branding (plantation)
    ("01_premiers_pas.json", 2): "login_page",
    ("01_premiers_pas.json", 3): "dashboard_main",
    ("01_premiers_pas.json", 4): "sidebar_navigation",
    ("01_premiers_pas.json", 5): "help_onboarding",

    # ── Tutorial 2: Employés et Paie ──
    ("02_employes_paie.json", 1): "employee_list",
    ("02_employes_paie.json", 2): "employee_detail",
    ("02_employes_paie.json", 3): "payroll_main",
    ("02_employes_paie.json", 4): "payroll_calculator",
    ("02_employes_paie.json", 5): "payroll_advances",

    # ── Tutorial 3: Travail Journalier ──
    ("03_travail_journalier.json", 1): "daily_work",
    ("03_travail_journalier.json", 2): "daily_work",
    ("03_travail_journalier.json", 3): "daily_work_operations",
    ("03_travail_journalier.json", 4): "daily_work_validation",
    ("03_travail_journalier.json", 5): "daily_work_operations",

    # ── Tutorial 4: Consulter mes infos ──
    ("04_consulter_infos.json", 1): "dashboard_main",
    ("04_consulter_infos.json", 2): "leaves_page",
    ("04_consulter_infos.json", 3): "payroll_main",
    ("04_consulter_infos.json", 4): "settings_user",

    # ── Tutorial 5: Analytics et KPIs ──
    ("05_analytics_kpis.json", 1): "analytics_dashboard",
    ("05_analytics_kpis.json", 2): "analytics_dashboard",
    ("05_analytics_kpis.json", 3): "analytics_reports",
    ("05_analytics_kpis.json", 4): "analytics_exports",

    # ── Tutorial 6: Agriculture ──
    ("06_agriculture.json", 1): None,  # Intro → branding (plantation)
    ("06_agriculture.json", 2): "agriculture_crop_cycles",
    ("06_agriculture.json", 3): "agriculture_harvests",
    ("06_agriculture.json", 4): "agriculture_weather",
    ("06_agriculture.json", 5): "agriculture_parcels",

    # ── Tutorial 7: Ventes et CRM ──
    ("07_ventes_crm.json", 1): "sales_pipeline",
    ("07_ventes_crm.json", 2): "sales_customers",
    ("07_ventes_crm.json", 3): "sales_pipeline",
    ("07_ventes_crm.json", 4): "sales_analytics",

    # ── Tutorial 8: Stocks et Inventaire ──
    ("08_stocks_inventaire.json", 1): "inventory_dashboard",
    ("08_stocks_inventaire.json", 2): "inventory_economat",
    ("08_stocks_inventaire.json", 3): "inventory_inputs",
    ("08_stocks_inventaire.json", 4): "inventory_counts",

    # ── Tutorial 9: GMAO ──
    ("09_gmao_maintenance.json", 1): "gmao_dashboard",
    ("09_gmao_maintenance.json", 2): "equipment_iot",
    ("09_gmao_maintenance.json", 3): "equipment_predictive",
    ("09_gmao_maintenance.json", 4): "equipment_list",

    # ── Tutorial 10: Comptabilité OHADA ──
    ("10_comptabilite_ohada.json", 1): "accounting_dashboard",
    ("10_comptabilite_ohada.json", 2): "accounting_journals",
    ("10_comptabilite_ohada.json", 3): "accounting_entries",
    ("10_comptabilite_ohada.json", 4): "accounting_reports",
    ("10_comptabilite_ohada.json", 5): "accounting_chart",
}


from typing import Optional

def find_recording(key: str) -> Optional[str]:
    """Find the recording file for a given key (try mp4 then webm)."""
    for ext in (".mp4", ".webm"):
        p = RECORDINGS_DIR / f"{key}{ext}"
        if p.exists():
            return str(p)
    return None


def update_storyboards():
    """Update all storyboard files with scene_type and recording_path."""
    storyboards = sorted(STORYBOARD_DIR.glob("*.json"))
    stats = {"updated": 0, "ui_scenes": 0, "brand_scenes": 0, "missing_recordings": 0}

    for sb_path in storyboards:
        storyboard = json.loads(sb_path.read_text())
        modified = False

        for scene in storyboard["scenes"]:
            scene_id = scene["id"]
            key_tuple = (sb_path.name, scene_id)
            recording_key = SCENE_TO_RECORDING.get(key_tuple)

            if recording_key is None:
                # Keep as branding
                scene["scene_type"] = "branding"
                stats["brand_scenes"] += 1
                modified = True
            else:
                recording_path = find_recording(recording_key)
                if recording_path:
                    scene["scene_type"] = "ui_recording"
                    scene["recording_path"] = recording_path
                    stats["ui_scenes"] += 1
                    modified = True
                else:
                    # Recording not found, keep as branding with warning
                    scene["scene_type"] = "branding"
                    stats["missing_recordings"] += 1
                    print(f"  WARNING: {sb_path.name} scene {scene_id}: "
                          f"recording '{recording_key}' not found → fallback to branding")
                    modified = True

        if modified:
            sb_path.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n")
            stats["updated"] += 1
            print(f"  Updated: {sb_path.name}")

    print(f"\n=== Storyboard Update Summary ===")
    print(f"Files updated: {stats['updated']}")
    print(f"UI recording scenes: {stats['ui_scenes']}")
    print(f"Branding scenes: {stats['brand_scenes']}")
    print(f"Missing recordings (fallback): {stats['missing_recordings']}")

    return stats


if __name__ == "__main__":
    update_storyboards()
