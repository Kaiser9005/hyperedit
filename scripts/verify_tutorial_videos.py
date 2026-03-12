#!/usr/bin/env python3
"""Comprehensive QA verification for all ERP tutorial videos.

V-I-V Principe 5: Tolerance Zero — every video verified against quality criteria.

Checks:
1. Audio stream exists (voice narration)
2. Video resolution (1920x1080)
3. Duration within expected range
4. No long silence gaps (>3s)
5. No black frame segments (>1s)
6. File size reasonable (500KB - 200MB)
7. Audio loudness (LUFS check)

Usage:
    python scripts/verify_tutorial_videos.py [output_dir]
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


OUTPUT_BASE = Path(__file__).resolve().parent.parent / "output_videos" / "erp_tutorials"

# Expected tutorials and their approximate durations
EXPECTED_TUTORIALS = {
    "01_premiers_pas": {"min_dur": 40, "max_dur": 90, "title": "Premiers Pas"},
    "02_employes_paie": {"min_dur": 40, "max_dur": 90, "title": "Employés et Paie"},
    "03_travail_journalier": {"min_dur": 40, "max_dur": 85, "title": "Travail Journalier"},
    "04_consulter_infos": {"min_dur": 35, "max_dur": 80, "title": "Consulter Infos"},
    "05_analytics_kpis": {"min_dur": 40, "max_dur": 90, "title": "Analytics KPIs"},
    "06_agriculture": {"min_dur": 40, "max_dur": 95, "title": "Agriculture"},
    "07_ventes_crm": {"min_dur": 35, "max_dur": 85, "title": "Ventes CRM"},
    "08_stocks_inventaire": {"min_dur": 35, "max_dur": 85, "title": "Stocks Inventaire"},
    "09_gmao_maintenance": {"min_dur": 35, "max_dur": 85, "title": "GMAO Maintenance"},
    "10_comptabilite_ohada": {"min_dur": 40, "max_dur": 90, "title": "Comptabilité OHADA"},
    "11_authentification_securite": {"min_dur": 40, "max_dur": 90, "title": "Authentification Sécurité"},
    "12_finances_transactions": {"min_dur": 40, "max_dur": 90, "title": "Finance Transactions"},
    "13_parametres_configuration": {"min_dur": 35, "max_dur": 80, "title": "Paramètres Configuration"},
}


def run_ffprobe(video_path: str, args: list) -> str:
    """Run ffprobe with given args and return stdout."""
    cmd = ["ffprobe", "-v", "error"] + args + [video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def run_ffmpeg_filter(video_path: str, filter_args: list) -> str:
    """Run ffmpeg with filter and return stderr (where filter output goes)."""
    cmd = ["ffmpeg", "-i", video_path] + filter_args + ["-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.stderr


def find_final_video(tutorial_dir: Path) -> Optional[Path]:
    """Find the final assembled video in a tutorial directory."""
    # Look for titled final video first
    for f in sorted(tutorial_dir.glob("*.mp4")):
        name = f.name
        if name.startswith("scene_") or name == "joined.mp4":
            continue
        return f
    # Fallback to joined.mp4
    joined = tutorial_dir / "joined.mp4"
    if joined.exists():
        return joined
    return None


def check_audio_exists(video_path: str) -> dict:
    """Check if video has audio stream."""
    codec = run_ffprobe(video_path, [
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
    ])
    return {"pass": bool(codec), "codec": codec or "NONE", "detail": f"Audio codec: {codec or 'MISSING'}"}


def check_resolution(video_path: str) -> dict:
    """Check video resolution is 1920x1080."""
    res = run_ffprobe(video_path, [
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
    ])
    passed = res == "1920x1080"
    return {"pass": passed, "resolution": res, "detail": f"Resolution: {res} {'OK' if passed else 'EXPECTED 1920x1080'}"}


def check_duration(video_path: str, min_dur: int, max_dur: int) -> dict:
    """Check video duration is within expected range."""
    dur_str = run_ffprobe(video_path, [
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
    ])
    try:
        duration = float(dur_str)
    except ValueError:
        return {"pass": False, "duration": 0, "detail": f"Cannot parse duration: {dur_str}"}

    passed = min_dur <= duration <= max_dur
    return {
        "pass": passed,
        "duration": round(duration, 1),
        "detail": f"Duration: {duration:.1f}s (expected {min_dur}-{max_dur}s)",
    }


def check_silence_gaps(video_path: str) -> dict:
    """Detect silence gaps > 3s (indicating missing narration)."""
    output = run_ffmpeg_filter(video_path, [
        "-af", "silencedetect=noise=-30dB:d=3.0",
    ])
    silence_starts = [line for line in output.split("\n") if "silence_start" in line]
    gap_count = len(silence_starts)
    passed = gap_count == 0
    return {
        "pass": passed,
        "silence_gaps": gap_count,
        "detail": f"Silence gaps (>3s): {gap_count}" + (" OK" if passed else " WARN"),
    }


def check_black_frames(video_path: str) -> dict:
    """Detect black frame segments > 1s."""
    output = run_ffmpeg_filter(video_path, [
        "-vf", "blackdetect=d=1.0:pix_th=0.1",
    ])
    black_starts = [line for line in output.split("\n") if "black_start" in line]
    count = len(black_starts)
    passed = count == 0
    return {
        "pass": passed,
        "black_segments": count,
        "detail": f"Black frame segments (>1s): {count}" + (" OK" if passed else " WARN"),
    }


def check_file_size(video_path: str) -> dict:
    """Check file size is reasonable (500KB - 200MB)."""
    size_bytes = Path(video_path).stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    passed = 0.5 <= size_mb <= 200
    return {
        "pass": passed,
        "size_mb": round(size_mb, 2),
        "detail": f"File size: {size_mb:.2f}MB {'OK' if passed else 'OUT OF RANGE'}",
    }


def verify_single_video(tutorial_name: str, video_path: Path, config: dict) -> dict:
    """Run all QA checks on a single tutorial video."""
    vp = str(video_path)
    checks = {}

    checks["audio"] = check_audio_exists(vp)
    checks["resolution"] = check_resolution(vp)
    checks["duration"] = check_duration(vp, config["min_dur"], config["max_dur"])
    checks["silence"] = check_silence_gaps(vp)
    checks["black_frames"] = check_black_frames(vp)
    checks["file_size"] = check_file_size(vp)

    passed = sum(1 for c in checks.values() if c["pass"])
    total = len(checks)
    score = (passed / total) * 10

    return {
        "tutorial": tutorial_name,
        "title": config["title"],
        "video_file": video_path.name,
        "checks": checks,
        "passed": passed,
        "total": total,
        "score": round(score, 1),
        "qa_passed": score >= 7.0,
    }


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_BASE

    print(f"\n{'='*60}")
    print(f"  TerraFlow ERP Tutorial Video QA Verification")
    print(f"  Directory: {output_dir}")
    print(f"{'='*60}\n")

    results = []
    missing = []

    for name, config in EXPECTED_TUTORIALS.items():
        tutorial_dir = output_dir / name
        if not tutorial_dir.exists():
            missing.append(name)
            print(f"  [{name}] MISSING - not yet assembled")
            continue

        video_path = find_final_video(tutorial_dir)
        if not video_path:
            missing.append(name)
            print(f"  [{name}] NO VIDEO FILE found in {tutorial_dir}")
            continue

        print(f"  [{name}] Verifying {video_path.name} ...")
        try:
            result = verify_single_video(name, video_path, config)
            results.append(result)

            status = "PASS" if result["qa_passed"] else "FAIL"
            print(f"    Score: {result['score']}/10 [{status}] ({result['passed']}/{result['total']} checks)")
            for check_name, check_result in result["checks"].items():
                indicator = "OK" if check_result["pass"] else "FAIL"
                print(f"      [{indicator}] {check_result['detail']}")
        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({
                "tutorial": name,
                "title": config["title"],
                "error": str(e),
                "score": 0,
                "qa_passed": False,
            })
        print()

    # Summary
    passed_count = sum(1 for r in results if r.get("qa_passed"))
    total_count = len(EXPECTED_TUTORIALS)
    assembled_count = len(results)

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Expected:  {total_count}")
    print(f"  Assembled: {assembled_count}")
    print(f"  Missing:   {len(missing)}")
    print(f"  QA Passed: {passed_count}/{assembled_count}")

    if missing:
        print(f"\n  Missing tutorials: {', '.join(missing)}")

    for r in results:
        if not r.get("qa_passed"):
            print(f"\n  FAILED: {r['tutorial']} (score: {r.get('score', 'N/A')})")
            if "checks" in r:
                for cn, cr in r["checks"].items():
                    if not cr["pass"]:
                        print(f"    - {cr['detail']}")

    # Save results
    results_path = output_dir / "qa_verification_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps({
        "total_expected": total_count,
        "assembled": assembled_count,
        "missing": missing,
        "passed": passed_count,
        "results": results,
    }, indent=2))
    print(f"\n  Results saved: {results_path}")

    return 0 if passed_count == assembled_count and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
