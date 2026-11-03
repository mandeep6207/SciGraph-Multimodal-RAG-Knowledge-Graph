"""Quick end-to-end upload + query test for SciGraph."""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

BASE = "http://127.0.0.1:8100"
PDF_PATH = str(Path(__file__).resolve().parent / "audit_test.pdf")


def upload_pdf(path):
    boundary = "AuditBoundary1234567890"
    with open(path, "rb") as f:
        pdf_data = f.read()
    body = (
        f"--{boundary}\r\n".encode()
        + b'Content-Disposition: form-data; name="file"; filename="audit_test.pdf"\r\n'
        + b"Content-Type: application/pdf\r\n\r\n"
        + pdf_data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        f"{BASE}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_jobs():
    with urllib.request.urlopen(f"{BASE}/jobs") as resp:
        return json.loads(resp.read())


def query_rag(question):
    payload = json.dumps({"question": question, "query": question}).encode()
    req = urllib.request.Request(
        f"{BASE}/query",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_graph():
    with urllib.request.urlopen(f"{BASE}/graph") as resp:
        return json.loads(resp.read())


def get_stats():
    with urllib.request.urlopen(f"{BASE}/stats") as resp:
        return json.loads(resp.read())


if __name__ == "__main__":
    print("=" * 60)
    print("SCIGRAPH — End-to-End Audit Test")
    print("=" * 60)

    # 1. Health
    with urllib.request.urlopen(f"{BASE}/health") as resp:
        health = json.loads(resp.read())
    print(f"\n[1] Health: {health}")

    # 2. Upload
    print(f"\n[2] Uploading {PDF_PATH} ...")
    upload_result = upload_pdf(PDF_PATH)
    print(f"    Upload response: {json.dumps(upload_result, indent=4)}")
    job_id = upload_result.get("job_id", "")

    # 3. Poll for completion
    print(f"\n[3] Polling job {job_id} ...")
    for i in range(60):
        time.sleep(5)
        jobs = get_jobs()
        job = next((j for j in jobs if j.get("job_id") == job_id or j.get("id") == job_id), None)
        if job:
            status = job.get("status", "?")
            progress = job.get("progress", "?")
            print(f"    [{i*5}s] status={status} progress={progress}")
            if status in ("completed", "done", "failed", "error"):
                print(f"    Final job state: {json.dumps(job, indent=4)}")
                break
        else:
            print(f"    [{i*5}s] job not found in list yet")

    # 4. Stats
    print("\n[4] Stats:")
    try:
        stats = get_stats()
        print(json.dumps(stats, indent=4))
    except Exception as e:
        print(f"    ERROR: {e}")

    # 5. Graph
    print("\n[5] Graph nodes/edges:")
    try:
        graph = get_graph()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", graph.get("links", graph.get("relationships", [])))
        print(f"    Nodes: {len(nodes)}, Edges: {len(edges)}")
        if nodes:
            print(f"    Sample nodes: {[n.get('id') or n.get('label') for n in nodes[:5]]}")
    except Exception as e:
        print(f"    ERROR: {e}")

    # 6. Query
    print("\n[6] Query — 'What is SciGraph and what technology does it use?'")
    try:
        q_resp = query_rag("What is SciGraph and what technology does it use?")
        answer = q_resp.get("answer", q_resp.get("response", str(q_resp)))
        print(f"    Answer: {answer[:500]}")
    except Exception as e:
        print(f"    ERROR: {e}")

    print("\n" + "=" * 60)
    print("Audit test complete.")
    print("=" * 60)
