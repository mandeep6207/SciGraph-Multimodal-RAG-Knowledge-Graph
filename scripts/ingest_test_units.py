import os
import sys
import time
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8100"
TEST_DOCS_DIR = Path("test documents")

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    files = sorted([f for f in TEST_DOCS_DIR.glob("GA-Unit-*.pdf")])
    print(f"Found {len(files)} test documents in '{TEST_DOCS_DIR}'.")
    
    client = httpx.Client(timeout=300.0)
    job_ids = []

    for pdf_path in files:
        print(f"Uploading {pdf_path.name} ({pdf_path.stat().st_size} bytes)...")
        with open(pdf_path, "rb") as f:
            resp = client.post(
                f"{BASE_URL}/upload",
                params={"force": "true"},
                files={"file": (pdf_path.name, f, "application/pdf")},
            )
        data = resp.json()
        job_id = data.get("job_id") or data.get("id")
        print(f"  -> Uploaded: job_id={job_id}, status={data.get('status')}")
        job_ids.append((pdf_path.name, job_id))

    print("\nMonitoring ingestion progress...")
    completed_jobs = {}
    start_time = time.time()
    
    while len(completed_jobs) < len(job_ids) and (time.time() - start_time) < 300:
        resp = client.get(f"{BASE_URL}/jobs")
        jobs_data = resp.json()
        job_map = {j["id"]: j for j in jobs_data} if isinstance(jobs_data, list) else jobs_data

        for fname, jid in job_ids:
            if jid in completed_jobs:
                continue
            job_info = job_map.get(jid)
            if job_info:
                st = job_info.get("status")
                prg = job_info.get("progress", 0)
                stage = job_info.get("stage", "unknown")
                print(f"  [{fname}] Status: {st} | Stage: {stage} | Progress: {prg}%")
                if st in ("done", "error", "cancelled"):
                    completed_jobs[jid] = job_info
                    print(f"  ==> {fname} FINISHED with status '{st}' in {job_info.get('duration', 0)}s!")
        time.sleep(3)

    print("\nIngestion Summary:")
    for fname, jid in job_ids:
        info = completed_jobs.get(jid, {})
        print(f" - {fname}: status={info.get('status')}, stage={info.get('stage')}, chunks={info.get('chunks')}, nodes={info.get('nodes')}")

if __name__ == "__main__":
    main()
