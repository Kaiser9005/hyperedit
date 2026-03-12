#!/usr/bin/env python3
"""Batch assembly of 10 ERP tutorial videos using FofalVideoAssembler.

V-I-V Principe 2: No workarounds — uses real pipeline.
V-I-V Principe 5: Tolerance Zero — QA score >= 7.0/10 for each video.
"""

import json
import sys
import time
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Add services to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services"))

from fofal_assembler import FofalVideoAssembler


STORYBOARD_DIR = Path(__file__).resolve().parent.parent / "templates" / "storyboards" / "erp_tutorials"
OUTPUT_BASE = Path(__file__).resolve().parent.parent / "output_videos" / "erp_tutorials"


def main():
    assembler = FofalVideoAssembler()

    storyboards = sorted(STORYBOARD_DIR.glob("*.json"))
    print(f"\n=== ERP Tutorial Video Assembly ===")
    print(f"Found {len(storyboards)} storyboards\n")

    skip_existing = "--skip-existing" in sys.argv

    results = []
    for i, sb_path in enumerate(storyboards, 1):
        name = sb_path.stem
        output_dir = OUTPUT_BASE / name

        # Skip if output directory has a final video (not scene_ files)
        if skip_existing and output_dir.exists():
            finals = [f for f in output_dir.glob("*.mp4") if not f.name.startswith("scene_") and f.name != "joined.mp4"]
            if finals:
                print(f"[{i}/{len(storyboards)}] SKIP (exists): {name} -> {finals[0].name}")
                print()
                continue

        print(f"[{i}/{len(storyboards)}] Assembling: {name}")
        print(f"  Storyboard: {sb_path.name}")
        print(f"  Output dir: {output_dir}")

        start = time.time()
        try:
            result = assembler.assemble(
                storyboard_path=sb_path,
                output_dir=output_dir,
            )
            elapsed = time.time() - start

            status = "PASS" if result.qa_passed else "FAIL"
            qa = f"{result.qa_score:.1f}/10" if result.qa_score else "N/A"
            print(f"  Result: {status} | QA: {qa} | Scenes: {result.scenes_assembled} | Time: {elapsed:.1f}s")
            if result.errors:
                for err in result.errors:
                    print(f"  ERROR: {err}")

            results.append({
                "name": name,
                "success": result.success,
                "qa_score": result.qa_score,
                "qa_passed": result.qa_passed,
                "output_path": result.output_path,
                "scenes": result.scenes_assembled,
                "errors": result.errors,
            })
        except Exception as e:
            elapsed = time.time() - start
            print(f"  EXCEPTION: {e} ({elapsed:.1f}s)")
            results.append({
                "name": name,
                "success": False,
                "qa_score": None,
                "qa_passed": False,
                "output_path": "",
                "scenes": 0,
                "errors": [str(e)],
            })

        print()

    # Summary
    passed = sum(1 for r in results if r["qa_passed"])
    print(f"\n=== SUMMARY ===")
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {len(results) - passed}")
    for r in results:
        status = "PASS" if r["qa_passed"] else "FAIL"
        qa = f"{r['qa_score']:.1f}" if r["qa_score"] else "N/A"
        print(f"  [{status}] {r['name']}: QA={qa}/10, scenes={r['scenes']}")

    # Save results
    results_path = OUTPUT_BASE / "assembly_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {results_path}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
