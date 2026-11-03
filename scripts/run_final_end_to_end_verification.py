import time
import json
import httpx
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE_URL = "http://127.0.0.1:8100"

GLOBAL_TESTS = [
    {
        "id": "G1",
        "title": "Quantum Computing & Decoherence",
        "prompt": "Explain the concept of quantum decoherence and why it presents a challenge for topological qubits in 2 concise sentences.",
        "model": "openai/gpt-oss-20b"
    },
    {
        "id": "G2",
        "title": "Python Graph Neural Network Code",
        "prompt": "Write a clean, minimal PyTorch geometric snippet creating a 2-layer Graph Convolutional Network (GCNConv).",
        "model": "openai/gpt-oss-20b"
    },
    {
        "id": "G3",
        "title": "Transformer Attention Complexity",
        "prompt": "What is the time and space complexity of standard scaled dot-product attention relative to sequence length N and dimension D?",
        "model": "openai/gpt-oss-20b"
    },
    {
        "id": "G4",
        "title": "Deep Reasoning with Grok 120B",
        "prompt": "Analyze the theoretical tradeoffs between Diffusion models and GANs in terms of mode coverage vs sampling speed.",
        "model": "openai/gpt-oss-120b"
    },
    {
        "id": "G5",
        "title": "Local Ollama Qwen2.5 Test",
        "prompt": "State the definition of a Riemannian manifold in differential geometry.",
        "model": "ollama/qwen2.5:3b"
    }
]

RESEARCH_TESTS = [
    {
        "id": "R1",
        "title": "Unit 1 - Latent Space Sampling",
        "prompt": "According to GA-Unit-1.pdf, how is latent space sampling performed and what are real vs synthetic feature overlays?",
        "sources": ["GA-Unit-1.pdf"],
        "model": "openai/gpt-oss-20b"
    },
    {
        "id": "R2",
        "title": "Unit 2 - VAE Latent Distribution & ELBO",
        "prompt": "According to GA-Unit-2.pdf, what is the encoder mapping q(z|x) and how is the Evidence Lower Bound (ELBO) optimized?",
        "sources": ["GA-Unit-2.pdf"],
        "model": "openai/gpt-oss-20b"
    },
    {
        "id": "R3",
        "title": "Unit 3 - Text Generation & Decoding",
        "prompt": "According to GA-Unit-3.pdf, what are the primary text decoding strategies (temperature, top-k, nucleus sampling)?",
        "sources": ["GA-Unit-3.pdf"],
        "model": "openai/gpt-oss-20b"
    },
    {
        "id": "R4",
        "title": "Unit 4 - Diffusion Noise Schedules",
        "prompt": "According to GA-Unit-4.pdf, what is the variance schedule beta_t in the forward Markovian diffusion chain?",
        "sources": ["GA-Unit-4.pdf"],
        "model": "openai/gpt-oss-20b"
    },
    {
        "id": "R5",
        "title": "Multi-Source - Unit 1 & Unit 5 Synthesis",
        "prompt": "Synthesize the relationship between continuous latent space representations in Unit 1 and autoregressive causal masking in Unit 5.",
        "sources": ["GA-Unit-1.pdf", "GA-Unit-5.pdf"],
        "model": "openai/gpt-oss-20b"
    }
]

def main():
    print("=" * 80)
    print("SCIGRAPH - MASTER SUITE: 5 GLOBAL + 5 RESEARCH ASSISTANT VERIFICATION")
    print("=" * 80)

    client = httpx.Client(timeout=60.0)
    all_results = {
        "global_tests": [],
        "research_tests": [],
        "stats": None
    }

    # Verify System Stats
    resp_stats = client.get(f"{BASE_URL}/stats")
    stats = resp_stats.json()
    all_results["stats"] = stats
    print(f"System State: docs={stats.get('total_docs')}, nodes={stats.get('total_nodes')}, relations={stats.get('total_relations')}\n")

    # 1. RUN 5 GLOBAL TESTS
    print(">>> PART 1: GLOBAL ASSISTANT TESTS (Unrestricted / Grok Cloud / Local Ollama)")
    for t in GLOBAL_TESTS:
        print(f"\n[Test {t['id']}] {t['title']} (Model: {t['model']})")
        print(f"Prompt: {t['prompt']}")
        t0 = time.time()
        try:
            resp = client.post(
                f"{BASE_URL}/api/chat/global",
                json={
                    "message": t["prompt"],
                    "model": t["model"],
                    "mode": "global"
                }
            )
            elapsed = round(time.time() - t0, 3)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("reply", "")
                snippet = reply[:160].replace("\n", " ")
                print(f"Status: 200 OK | Latency: {elapsed}s (reported: {data.get('latency_ms')}ms)")
                print(f"Snippet: {snippet}...")
                all_results["global_tests"].append({
                    "id": t["id"],
                    "title": t["title"],
                    "model": data.get("model"),
                    "provider": data.get("provider"),
                    "latency_s": elapsed,
                    "reported_ms": data.get("latency_ms"),
                    "status": "PASS",
                    "reply_preview": snippet
                })
            else:
                print(f"Failed {resp.status_code}: {resp.text}")
                all_results["global_tests"].append({
                    "id": t["id"],
                    "title": t["title"],
                    "latency_s": elapsed,
                    "status": f"FAIL ({resp.status_code})",
                    "error": resp.text
                })
        except Exception as e:
            elapsed = round(time.time() - t0, 3)
            print(f"Exception: {e}")
            all_results["global_tests"].append({
                "id": t["id"],
                "title": t["title"],
                "latency_s": elapsed,
                "status": "ERROR",
                "error": str(e)
            })
        time.sleep(1.2)

    # 2. RUN 5 RESEARCH TESTS
    print("\n\n>>> PART 2: SCIGRAPH RESEARCH ASSISTANT TESTS (Document Grounded RAG with Citations)")
    for t in RESEARCH_TESTS:
        print(f"\n[Test {t['id']}] {t['title']} (Sources: {t['sources']})")
        print(f"Prompt: {t['prompt']}")
        t0 = time.time()
        try:
            resp = client.post(
                f"{BASE_URL}/api/chat/global",
                json={
                    "message": t["prompt"],
                    "model": t["model"],
                    "mode": "research",
                    "sources": t["sources"]
                }
            )
            elapsed = round(time.time() - t0, 3)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("reply", "")
                citations = data.get("citations", [])
                snippet = reply[:180].replace("\n", " ")
                print(f"Status: 200 OK | Latency: {elapsed}s (retrieval: {data.get('retrieval_ms')}ms)")
                print(f"Citations count: {len(citations)} | Nodes: {data.get('retrieved_nodes', [])}")
                print(f"Snippet: {snippet}...")
                all_results["research_tests"].append({
                    "id": t["id"],
                    "title": t["title"],
                    "model": data.get("model"),
                    "sources_used": t["sources"],
                    "latency_s": elapsed,
                    "retrieval_ms": data.get("retrieval_ms"),
                    "citations_count": len(citations),
                    "status": "PASS",
                    "reply_preview": snippet
                })
            else:
                print(f"Failed {resp.status_code}: {resp.text}")
                all_results["research_tests"].append({
                    "id": t["id"],
                    "title": t["title"],
                    "latency_s": elapsed,
                    "status": f"FAIL ({resp.status_code})",
                    "error": resp.text
                })
        except Exception as e:
            elapsed = round(time.time() - t0, 3)
            print(f"Exception: {e}")
            all_results["research_tests"].append({
                "id": t["id"],
                "title": t["title"],
                "latency_s": elapsed,
                "status": "ERROR",
                "error": str(e)
            })
        time.sleep(1.2)

    print("\n" + "=" * 80)
    print("FINAL TEST SUMMARY:")
    for r in all_results["global_tests"]:
        print(f" [GLOBAL]   {r['id']} ({r['title']}): {r['status']} in {r['latency_s']}s")
    for r in all_results["research_tests"]:
        print(f" [RESEARCH] {r['id']} ({r['title']}): {r['status']} in {r['latency_s']}s (citations: {r.get('citations_count')})")
    print("=" * 80)

    with open("scripts/final_test_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print("Saved results to scripts/final_test_results.json")

if __name__ == "__main__":
    main()
