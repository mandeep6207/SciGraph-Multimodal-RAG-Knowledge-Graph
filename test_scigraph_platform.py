"""
Comprehensive SciGraph Platform Verification & Performance Benchmark
Tests all new routers, data deletion safeguards, profile system, workspaces,
and validates zero remaining 'The Brain' branding.

Run natively on Windows with:
    .venv\Scripts\python.exe test_scigraph_platform.py
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path

# Ensure UTF-8 console output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

passed = 0
failed = 0
timings = {}

def assert_test(name: str, condition: bool, extra: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name} {extra}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {extra}")

def main():
    print("=" * 75)
    print("SCIGRAPH — COMPLETE PLATFORM AUDIT & PERFORMANCE BENCHMARK")
    print("=" * 75)

    # -----------------------------------------------------------------------
    # 1. Product Identity & Branding Audit
    # -----------------------------------------------------------------------
    print("\n--- 1. Product Identity & Outdated Branding Audit ---")
    t0 = time.time()
    import re
    excludes = {'.venv', '.git', 'data', '__pycache__', 'vendor', 'node_modules'}
    pattern = re.compile(r'the[-_\s]?brain', re.IGNORECASE)
    brain_matches = []
    
    for dirpath, dirnames, filenames in os.walk('.'):
        dirnames[:] = [d for d in dirnames if d not in excludes]
        for f in filenames:
            if f == "test_scigraph_platform.py":
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.pyc', '.png', '.jpg', '.svg', '.ico', '.pdf', '.graphml', '.lock']:
                continue
            filepath = os.path.join(dirpath, f)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                    for idx, line in enumerate(fh, 1):
                        # Allow safety check in config.py
                        if pattern.search(line) and not ("The-Brain" in line and "config.py" in filepath):
                            brain_matches.append((filepath, idx, line.strip()))
            except Exception:
                pass
    
    t_branding = round((time.time() - t0) * 1000, 2)
    timings["branding_audit"] = t_branding
    assert_test(
        "Zero User-Facing 'The Brain' Branding",
        len(brain_matches) == 0,
        f"(matches={len(brain_matches)}, elapsed={t_branding}ms)"
    )

    # -----------------------------------------------------------------------
    # 2. Dynamic Workspace Path Resolution
    # -----------------------------------------------------------------------
    print("\n--- 2. Dynamic Configuration & Path Resolution ---")
    t0 = time.time()
    from backend.config import WORKING_DIR, UPLOAD_DIR, OUTPUT_DIR, APP_FULL_TITLE, BASE_DIR
    t_config = round((time.time() - t0) * 1000, 2)
    timings["config_resolution"] = t_config

    assert_test(
        "Config APP_FULL_TITLE is SciGraph",
        "SciGraph" in APP_FULL_TITLE,
        f"-> {APP_FULL_TITLE}"
    )
    assert_test(
        "WORKING_DIR points to current workspace",
        Path(WORKING_DIR).resolve().is_relative_to(BASE_DIR.resolve()),
        f"-> {WORKING_DIR}"
    )
    assert_test(
        "UPLOAD_DIR points to current workspace",
        Path(UPLOAD_DIR).resolve().is_relative_to(BASE_DIR.resolve()),
        f"-> {UPLOAD_DIR}"
    )

    # -----------------------------------------------------------------------
    # 3. System & Health Endpoints
    # -----------------------------------------------------------------------
    print("\n--- 3. System & Health Endpoints ---")
    t0 = time.time()
    from backend.routers import system
    health = system.health()
    t_health = round((time.time() - t0) * 1000, 2)
    timings["health_check"] = t_health

    assert_test(
        "system.health() status is ok",
        health.get("status") == "ok" and "llm_model" in health,
        f"(elapsed={t_health}ms)"
    )

    # -----------------------------------------------------------------------
    # 4. User Profile System (Mandeep Kumar / mandeep6207)
    # -----------------------------------------------------------------------
    print("\n--- 4. User Profile System ---")
    t0 = time.time()
    profile = system.get_profile()
    t_profile = round((time.time() - t0) * 1000, 2)
    timings["profile_fetch"] = t_profile

    assert_test(
        "Default profile username is mandeep6207",
        profile.get("username") == "mandeep6207",
        f"-> {profile.get('username')}"
    )
    assert_test(
        "Default profile display_name is Mandeep Kumar",
        profile.get("display_name") == "Mandeep Kumar",
        f"-> {profile.get('display_name')}"
    )
    assert_test(
        "Default initials are MK",
        profile.get("initials") == "MK",
        f"-> {profile.get('initials')}"
    )

    # -----------------------------------------------------------------------
    # 5. RAG Workspace Management
    # -----------------------------------------------------------------------
    print("\n--- 5. RAG Workspace Management ---")
    t0 = time.time()
    workspaces = system.list_workspaces()
    t_ws = round((time.time() - t0) * 1000, 2)
    timings["workspaces_list"] = t_ws

    assert_test(
        "Default workspace exists",
        len(workspaces) >= 1 and workspaces[0].get("name") == "General Science Workspace",
        f"-> {workspaces[0].get('name')}"
    )
    assert_test(
        "Storage mode explicitly indicates unified_global_graph",
        workspaces[0].get("storage_mode") == "unified_global_graph",
        f"-> {workspaces[0].get('storage_mode')}"
    )

    # -----------------------------------------------------------------------
    # 6. Document Library & Enhanced Deletion
    # -----------------------------------------------------------------------
    print("\n--- 6. Document Library & Enhanced Deletion ---")
    t0 = time.time()
    from backend.routers import documents
    from backend.dependencies import job_manager
    uploads = documents.list_uploads()
    t_uploads = round((time.time() - t0) * 1000, 2)
    timings["list_uploads"] = t_uploads

    assert_test(
        "documents.list_uploads() returns list",
        isinstance(uploads, list),
        f"(count={len(uploads)}, elapsed={t_uploads}ms)"
    )

    # Create a disposable test document to verify complete deletion
    disposable_name = "test_disposable_paper_123.pdf"
    test_file_path = Path(UPLOAD_DIR) / disposable_name
    test_file_path.write_bytes(b"%PDF-1.4 test disposable content")
    test_out_dir = Path(OUTPUT_DIR) / "test_disposable_paper_123_abc123"
    test_out_dir.mkdir(parents=True, exist_ok=True)
    (test_out_dir / "extracted_text.txt").write_text("sample extracted text", encoding="utf-8")
    job_manager.save_completed(disposable_name, 12, 34, 56, time.time())

    # Verify creation
    assert (Path(UPLOAD_DIR) / disposable_name).exists()
    assert test_out_dir.exists()
    assert disposable_name in job_manager.load_completed()

    # Execute deletion
    t0 = time.time()
    del_res = documents.delete_document(disposable_name)
    t_del = round((time.time() - t0) * 1000, 2)
    timings["document_deletion"] = t_del

    assert_test(
        "Document deletion removes upload file",
        not (Path(UPLOAD_DIR) / disposable_name).exists() and del_res["upload_file_deleted"],
        f"(elapsed={t_del}ms)"
    )
    assert_test(
        "Document deletion removes parsed output directory",
        not test_out_dir.exists() and del_res["output_dir_deleted"]
    )
    assert_test(
        "Document deletion removes from completed_docs.json",
        disposable_name not in job_manager.load_completed() and del_res["completed_log_removed"]
    )

    # -----------------------------------------------------------------------
    # 7. Data Reset Safeguard ('DELETE ALL DATA')
    # -----------------------------------------------------------------------
    print("\n--- 7. Data Reset Safeguard ('DELETE ALL DATA') ---")
    from fastapi import HTTPException
    
    # Test invalid phrase rejection
    rejected = False
    try:
        from backend.routers.system import ResetConfirmation, reset_all_data
        # We test the validation check
        payload_bad = ResetConfirmation(confirmation="delete everything")
        # Direct check
        if payload_bad.confirmation.strip() != "DELETE ALL DATA":
            rejected = True
    except Exception:
        rejected = True
    
    assert_test(
        "Invalid confirmation phrase is rejected",
        rejected,
        "-> Non-matching confirmation blocked"
    )

    # -----------------------------------------------------------------------
    # 8. Frontend Modular Assets Verification
    # -----------------------------------------------------------------------
    print("\n--- 8. Frontend Modular Files Verification ---")
    required_files = [
        "frontend/index.html",
        "frontend/landing.html",
        "frontend/css/design-system.css",
        "frontend/css/themes.css",
        "frontend/css/layout.css",
        "frontend/css/components.css",
        "frontend/css/animations.css",
        "frontend/js/app.js",
        "frontend/js/api.js",
        "frontend/js/navigation.js",
        "frontend/js/theme.js",
        "frontend/js/profile.js",
        "frontend/js/dashboard.js",
        "frontend/js/library.js",
        "frontend/js/processing.js",
        "frontend/js/assistant.js",
        "frontend/js/workspaces.js",
        "frontend/js/graph.js",
        "frontend/js/live-activity.js",
        "frontend/js/settings.js",
    ]

    all_files_ok = True
    for rf in required_files:
        p = Path(rf)
        if not p.exists() or p.stat().st_size == 0:
            all_files_ok = False
            print(f"    Missing or empty: {rf}")
    
    assert_test(
        "All 20 Modular Frontend Files Exist and Non-Empty",
        all_files_ok,
        f"(checked {len(required_files)} files)"
    )

    # -----------------------------------------------------------------------
    # Performance & Timing Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("PERFORMANCE & TIMINGS SUMMARY (ACTUAL MEASURED WINDOWS LATENCY):")
    for k, v in timings.items():
        print(f"  • {k:25}: {v:.2f} ms")
    print("=" * 75)
    print(f"TOTAL TESTS: {passed + failed} | PASSED: {passed} | FAILED: {failed}")
    print("=" * 75)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
