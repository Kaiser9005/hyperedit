#!/usr/bin/env python3
"""Update ERP tutorial storyboards: FOFAL ERP → TerraFlow ERP + genericize for multi-tenant.

V-I-V: Product renamed to TerraFlow ERP. Tutorials must work for any client, not just FOFAL.
Changes:
  1. Watermark: "FOFAL ERP" → "TerraFlow ERP"
  2. Narration: Replace FOFAL-specific product name with "TerraFlow ERP"
  3. Narration: Genericize FOFAL-specific data (employee counts, amounts) for multi-tenant
  4. visual_description: Update where referencing FOFAL brand in UI tutorial context
"""

import json
from pathlib import Path

STORYBOARD_DIR = Path(__file__).resolve().parent.parent / "templates" / "storyboards" / "erp_tutorials"

# Exact narration replacements per (file, scene_id)
# Format: (old_substring, new_substring)
NARRATION_FIXES = {
    # ── Tutorial 1: Premiers Pas ──
    ("01_premiers_pas.json", 1): [
        (
            "Bienvenue dans l'ERP FOFAL, votre outil de gestion integre pour la plantation.",
            "Bienvenue dans TerraFlow ERP, votre plateforme de gestion integree pour l'entreprise agricole.",
        ),
    ],

    # ── Tutorial 2: Employés et Paie ──
    ("02_employes_paie.json", 1): [
        (
            "la gestion des ressources humaines chez FOFAL. Avec plus de 40 collaborateurs actifs, il vous permet de gerer l'ensemble des dossiers du personnel.",
            "le coeur de la gestion des ressources humaines de votre entreprise. Il vous permet de gerer l'ensemble des dossiers du personnel et de suivre vos collaborateurs actifs.",
        ),
    ],
    ("02_employes_paie.json", 4): [
        (
            "FOFAL gere actuellement 73 avances pour un total de 1,8 million de francs CFA. Chaque avance est tracee et deductible automatiquement.",
            "Le systeme centralise toutes vos avances sur salaire. Chaque avance est tracee et deductible automatiquement lors du calcul de paie.",
        ),
    ],

    # ── Tutorial 3: Travail Journalier ──
    ("03_travail_journalier.json", 1): [
        (
            "Avec plus de 5700 entrees deja enregistrees, c'est l'outil central du suivi operationnel.",
            "C'est l'outil central du suivi operationnel de votre entreprise.",
        ),
    ],
    ("03_travail_journalier.json", 4): [
        (
            "chacune des 28 parcelles de A a Z",
            "chacune de vos parcelles",
        ),
    ],

    # ── Tutorial 4: Consulter mes infos ──
    ("04_consulter_infos.json", 1): [
        (
            "En tant qu'employe FOFAL, vous disposez",
            "En tant qu'utilisateur TerraFlow ERP, vous disposez",
        ),
    ],

    # ── Tutorial 5: Analytics et KPIs ──
    ("05_analytics_kpis.json", 1): [
        (
            "Le module Analytics de FOFAL ERP offre",
            "Le module Analytics de TerraFlow ERP offre",
        ),
    ],
    ("05_analytics_kpis.json", 3): [
        (
            "chiffre d'affaires de 272 millions de francs CFA, couts de production, marges par produit",
            "chiffre d'affaires, couts de production, marges par produit",
        ),
    ],

    # ── Tutorial 6: Agriculture ──
    ("06_agriculture.json", 1): [
        (
            "Le module Agriculture de FOFAL ERP gere l'ensemble des operations sur nos 80 hectares et 28 parcelles.",
            "Le module Agriculture de TerraFlow ERP gere l'ensemble de vos operations agricoles sur vos parcelles.",
        ),
    ],

    # ── Tutorial 7: Ventes et CRM ──
    ("07_ventes_crm.json", 1): [
        (
            "tout le cycle commercial de FOFAL",
            "tout votre cycle commercial",
        ),
    ],

    # ── Tutorial 8: Stocks et Inventaire ──
    ("08_stocks_inventaire.json", 1): [
        (
            "l'ensemble des approvisionnements de FOFAL. Economat, intrants agricoles, carburant: tout est suivi en temps reel avec 145 articles references.",
            "l'ensemble de vos approvisionnements. Economat, intrants agricoles, carburant: tout est suivi en temps reel.",
        ),
    ],

    # ── Tutorial 9: GMAO ──
    ("09_gmao_maintenance.json", 1): [
        (
            "le parc d'equipements de FOFAL:",
            "votre parc d'equipements:",
        ),
    ],

    # ── Tutorial 10: Comptabilité OHADA ──
    ("10_comptabilite_ohada.json", 1): [
        (
            "Le module Comptabilite OHADA de FOFAL ERP est conforme",
            "Le module Comptabilite OHADA de TerraFlow ERP est conforme",
        ),
    ],
    ("10_comptabilite_ohada.json", 4): [
        (
            "Les 272 millions de francs CFA de transactions historiques sont integres pour une vision complete de la sante financiere de FOFAL.",
            "Toutes vos transactions historiques sont integrees pour une vision complete de la sante financiere de votre entreprise.",
        ),
    ],
}

# visual_description fixes (genericize FOFAL references in tutorial context)
VISUAL_FIXES = {
    ("01_premiers_pas.json", 1): (
        "Vue aerienne de la plantation FOFAL, ambiance professionnelle",
        "Ecran d'accueil TerraFlow ERP, ambiance professionnelle",
    ),
    ("02_employes_paie.json", 1): (
        "Equipe FOFAL au travail, gestion du personnel",
        "Interface de gestion du personnel, liste des employes",
    ),
    ("06_agriculture.json", 1): (
        "Vue aerienne des 80 hectares de plantation FOFAL",
        "Module agriculture TerraFlow ERP, gestion des parcelles",
    ),
    ("07_ventes_crm.json", 1): (
        "Produits FOFAL presentes pour la vente commerciale",
        "Pipeline commercial et gestion des ventes",
    ),
    ("08_stocks_inventaire.json", 2): (
        "Equipements et fournitures dans l'entrepot FOFAL",
        "Interface economat avec mouvements de stock",
    ),
    ("10_comptabilite_ohada.json", 4): (
        "Produits FOFAL symbolisant la valeur financiere de l'entreprise",
        "Rapports financiers OHADA et etats de synthese",
    ),
}


def update_storyboards():
    """Apply all TerraFlow rename + genericization fixes."""
    storyboards = sorted(STORYBOARD_DIR.glob("*.json"))
    stats = {"files": 0, "watermark": 0, "narration": 0, "visual": 0, "errors": []}

    for sb_path in storyboards:
        storyboard = json.loads(sb_path.read_text())
        modified = False

        # 1. Watermark: "FOFAL ERP" → "TerraFlow"
        if storyboard.get("watermark", {}).get("text") == "FOFAL ERP":
            storyboard["watermark"]["text"] = "TerraFlow ERP"
            stats["watermark"] += 1
            modified = True

        # 2. Process each scene
        for scene in storyboard["scenes"]:
            scene_id = scene["id"]
            key = (sb_path.name, scene_id)

            # Narration fixes
            if key in NARRATION_FIXES:
                for old, new in NARRATION_FIXES[key]:
                    if old in scene["narration_text"]:
                        scene["narration_text"] = scene["narration_text"].replace(old, new)
                        stats["narration"] += 1
                        modified = True
                    else:
                        stats["errors"].append(
                            f"{sb_path.name} scene {scene_id}: narration substring not found: '{old[:50]}...'"
                        )

            # Visual description fixes
            if key in VISUAL_FIXES:
                old_vis, new_vis = VISUAL_FIXES[key]
                if scene.get("visual_description") == old_vis:
                    scene["visual_description"] = new_vis
                    stats["visual"] += 1
                    modified = True
                else:
                    stats["errors"].append(
                        f"{sb_path.name} scene {scene_id}: visual_description mismatch"
                    )

        if modified:
            sb_path.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n")
            stats["files"] += 1
            print(f"  ✅ {sb_path.name}")

    print(f"\n=== TerraFlow Storyboard Update ===")
    print(f"Files updated: {stats['files']}/10")
    print(f"Watermarks fixed: {stats['watermark']}")
    print(f"Narrations fixed: {stats['narration']}")
    print(f"Visuals fixed: {stats['visual']}")
    if stats["errors"]:
        print(f"\n⚠️  Errors ({len(stats['errors'])}):")
        for e in stats["errors"]:
            print(f"  - {e}")
    else:
        print(f"\n✅ Zero errors — all replacements matched")

    return stats


if __name__ == "__main__":
    update_storyboards()
