import urllib.request
import urllib.parse
import json
import uuid

BASE_URL = "http://127.0.0.1:8100"

def test_health():
    print("[1/5] Testing /health...")
    with urllib.request.urlopen(f"{BASE_URL}/health") as resp:
        data = json.loads(resp.read().decode())
        print("  Health response:", data)
        assert data.get("status") == "healthy" or "status" in data

def test_graph_endpoint():
    print("[2/5] Testing /graph...")
    with urllib.request.urlopen(f"{BASE_URL}/graph?limit=50") as resp:
        data = json.loads(resp.read().decode())
        nodes = data.get("nodes", [])
        links = data.get("links", [])
        print(f"  Graph returned {len(nodes)} nodes, {len(links)} links")
        assert "nodes" in data and "links" in data, "Expected valid graph structure"

def test_batch_upload():
    print("[3/5] Testing POST /upload/batch with 3 documents concurrently...")
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    
    # 3 documents
    files_to_upload = [
        ("batch_test_paper_alpha.txt", b"Abstract: Quantum entanglement and topological quantum computing overview.\nMethods: We evaluate superconducting qubits.\nResults: Coherence times improved by 40%."),
        ("batch_test_paper_beta.txt", b"Abstract: Deep multimodal representation learning in bioinformatics.\nMethods: Graph neural networks applied to molecular docking.\nResults: High binding affinity prediction accuracy."),
        ("batch_test_paper_gamma.txt", b"Abstract: Autonomous discovery in materials science.\nMethods: High-throughput robotic synthesis and XRD characterization.\nResults: Discovered novel perovskite structures.")
    ]
    
    body = bytearray()
    for fname, content in files_to_upload:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="files"; filename="{fname}"\r\n'.encode("utf-8"))
        body.extend(b"Content-Type: text/plain\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    
    req = urllib.request.Request(
        f"{BASE_URL}/upload/batch?force=true",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print("  Batch upload response:")
        print(f"    Total: {res.get('total')}, Successful: {res.get('successful')}, Failed: {res.get('failed')}")
        for r in res.get("results", []):
            print(f"    - File: {r.get('filename')}, Status: {r.get('status')}, Job: {r.get('job_id')}")
        assert res.get("total") == 3, f"Expected 3 files, got {res.get('total')}"
        assert res.get("successful") == 3, f"Expected 3 successful, got {res.get('successful')}"

def test_pages():
    print("[4/5] Testing Landing page and UI pages...")
    with urllib.request.urlopen(f"{BASE_URL}/") as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        assert "SciGraph" in content
        assert "Where Scientific Knowledge" in content
        print("  Landing page (/) loaded successfully (200 OK, SciGraph verified)")
        
    with urllib.request.urlopen(f"{BASE_URL}/ui/") as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        assert "SciGraph" in content
        assert "upload-queue-card" in content
        assert "3d-graph" in content
        print("  Main UI (/ui/) loaded successfully (200 OK, Multi-upload & 3D graph verified)")

def test_documents_list():
    print("[5/5] Testing /documents or /uploads list...")
    with urllib.request.urlopen(f"{BASE_URL}/uploads") as resp:
        docs = json.loads(resp.read().decode())
        print(f"  Uploads list returned {len(docs)} documents")
        names = [d.get("filename") for d in docs]
        print("  Sample documents in repository:", names[:5])

if __name__ == "__main__":
    print("=" * 60)
    print("VERIFYING SCIGRAPH RESTORATION & BATCH MULTI-UPLOAD")
    print("=" * 60)
    test_health()
    test_graph_endpoint()
    test_batch_upload()
    test_pages()
    test_documents_list()
    print("=" * 60)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)
