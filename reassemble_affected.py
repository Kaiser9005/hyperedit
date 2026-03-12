#!/usr/bin/env python3
"""Re-assemble the 11 tutorial videos that had storyboard recording_path fixes.

Reuses existing narration MP3s (narration text unchanged).
Affected videos: 01, 02, 03, 05, 06, 07, 08, 10, 11, 12, 13
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "services"))
sys.path.insert(0, str(Path(__file__).parent))

from services.fofal_assembler import FofalVideoAssembler

STORYBOARD_DIR = Path(__file__).parent / "templates" / "storyboards" / "erp_tutorials"
OUTPUT_BASE = Path(__file__).parent / "output_videos" / "erp_tutorials"
DOCS_SITE_VIDEOS = Path("/Users/cherylmaevahfodjo/modules-rh-authentification-expert-00-9/docs-site/static/videos")

# Map: storyboard filename → (output dir name, docs-site video filename)
AFFECTED_VIDEOS = {
    "01_premiers_pas.json": ("01_premiers_pas", "video1_premiers_pas.mp4"),
    "02_employes_paie.json": ("02_employes_paie", "video2_employes_paie.mp4"),
    "03_travail_journalier.json": ("03_travail_journalier", "video3_travail_journalier.mp4"),
    "05_analytics_kpis.json": ("05_analytics_kpis", "video5_analytics_kpis.mp4"),
    "06_agriculture.json": ("06_agriculture", "video6_agriculture.mp4"),
    "07_ventes_crm.json": ("07_ventes_crm", "video7_ventes_crm.mp4"),
    "08_stocks_inventaire.json": ("08_stocks_inventaire", "video8_stocks_inventaire.mp4"),
    "10_comptabilite_ohada.json": ("10_comptabilite_ohada", "video10_comptabilite_ohada.mp4"),
    "11_authentification_securite.json": ("11_authentification_securite", "video11_authentification_securite.mp4"),
    "12_finances_transactions.json": ("12_finances_transactions", "video12_finances_transactions.mp4"),
    "13_parametres_configuration.json": ("13_parametres_configuration", "video13_parametres_configuration.mp4"),
}


def build_narration_map(output_dir: Path, storyboard_path: Path) -> dict:
    """Build scene_id → narration path dict from existing narration files."""
    storyboard = json.loads(storyboard_path.read_text())
    narrations = {}
    for scene in storyboard["scenes"]:
        sid = scene["id"]
        narration_file = output_dir / f"scene_{sid:02d}_narration.mp3"
        if narration_file.exists():
            narrations[sid] = narration_file
        else:
            print(f"  WARNING: Missing narration for scene {sid}: {narration_file}")
    return narrations


def main():
    assembler = FofalVideoAssembler()
    results = []

    for storyboard_name, (out_dir_name, docs_video_name) in AFFECTED_VIDEOS.items():
        storyboard_path = STORYBOARD_DIR / storyboard_name
        output_dir = OUTPUT_BASE / out_dir_name

        if not storyboard_path.exists():
            print(f"SKIP: {storyboard_name} not found")
            continue

        print(f"\n{'='*60}")
        print(f"ASSEMBLING: {storyboard_name}")
        print(f"{'='*60}")

        # Build narration map from existing files
        narrations = build_narration_map(output_dir, storyboard_path)
        print(f"  Reusing {len(narrations)} existing narrations")

        # Run assembly
        try:
            result = assembler.assemble(
                storyboard_path=storyboard_path,
                output_dir=output_dir,
                existing_narrations=narrations,
            )
            print(f"  Success: {result.success}")
            print(f"  QA Score: {result.qa_score}/10")
            print(f"  Scenes: {result.scenes_assembled}")
            print(f"  Output: {result.output_path}")
            if result.errors:
                print(f"  Errors: {result.errors}")

            # Copy to docs-site
            if result.success and result.output_path:
                src = Path(result.output_path)
                dst = DOCS_SITE_VIDEOS / docs_video_name
                if src.exists():
                    shutil.copy2(src, dst)
                    print(f"  Copied to: {dst}")
                    print(f"  Size: {dst.stat().st_size / 1024 / 1024:.1f} MB")

            results.append({
                "name": out_dir_name,
                "success": result.success,
                "qa_score": result.qa_score,
                "qa_passed": result.qa_passed,
                "output_path": result.output_path,
                "scenes": result.scenes_assembled,
                "errors": result.errors,
            })

        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "name": out_dir_name,
                "success": False,
                "qa_score": 0,
                "qa_passed": False,
                "output_path": "",
                "scenes": 0,
                "errors": [str(e)],
            })

    # Save results
    results_path = OUTPUT_BASE / "reassembly_results.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\n{'='*60}")
    print(f"RESULTS saved to: {results_path}")
    print(f"Total: {sum(1 for r in results if r['success'])}/{len(results)} succeeded")
    print(f"{'='*60}")

    # Summary
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        print(f"  [{status}] {r['name']}: QA {r['qa_score']}/10, {r['scenes']} scenes")
        if r["errors"]:
            for err in r["errors"]:
                print(f"         ERROR: {err}")


if __name__ == "__main__":
    main()
