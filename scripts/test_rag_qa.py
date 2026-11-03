import sys
import json
import time
import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8100"

QUESTIONS = [
    {
        "unit": "Unit 1 - Foundations & Latent Spaces",
        "question": "What are the core concepts of Generative Artificial Intelligence and latent space representations?",
        "mode": "hybrid"
    },
    {
        "unit": "Unit 2 - Variational Autoencoders (VAEs)",
        "question": "Explain the architecture of Variational Autoencoders and the reparameterization trick.",
        "mode": "hybrid"
    },
    {
        "unit": "Unit 3 - Generative Adversarial Networks (GANs)",
        "question": "Describe Generative Adversarial Networks (GANs), the min-max objective, and generator vs discriminator roles.",
        "mode": "hybrid"
    },
    {
        "unit": "Unit 4 - Diffusion Models",
        "question": "What is the forward diffusion process, reverse denoising process, and score matching in Diffusion Models?",
        "mode": "hybrid"
    },
    {
        "unit": "Unit 5 - Transformers & LLMs",
        "question": "Explain the self-attention mechanism and autoregressive generation in Transformer models.",
        "mode": "hybrid"
    }
]

def main():
    print("=" * 80)
    print("SCIGRAPH - END-TO-END RAG RETRIEVAL & KNOWLEDGE GRAPH QA VERIFICATION")
    print("=" * 80)

    client = httpx.Client(timeout=180.0)
    results = []

    for idx, item in enumerate(QUESTIONS, 1):
        print(f"\n[Test {idx}/5] {item['unit']}")
        print(f"Question: {item['question']}")
        print(f"Mode: {item['mode']}")
        t0 = time.time()
        
        try:
            resp = client.post(
                f"{BASE_URL}/query",
                json={
                    "query": item["question"],
                    "mode": item["mode"],
                    "return_nodes": True
                }
            )
            elapsed = round(time.time() - t0, 2)
            if resp.status_code == 200:
                data = resp.json()
                ans = data.get("answer", "")
                nodes = data.get("retrieved_nodes", [])
                print(f"Status: 200 OK ({elapsed}s)")
                print(f"Retrieved Nodes ({len(nodes)}): {nodes[:5]}")
                print("-" * 40)
                # Print first 350 chars of answer
                snippet = ans[:350].replace("\n", " ")
                print(f"Answer snippet: {snippet}...")
                print("-" * 40)
                results.append({
                    "test": idx,
                    "unit": item["unit"],
                    "question": item["question"],
                    "status": "PASS",
                    "latency_s": elapsed,
                    "retrieved_nodes": len(nodes),
                    "full_answer": ans
                })
            else:
                print(f"Error {resp.status_code}: {resp.text}")
                results.append({
                    "test": idx,
                    "unit": item["unit"],
                    "question": item["question"],
                    "status": f"FAIL ({resp.status_code})",
                    "latency_s": elapsed,
                    "error": resp.text
                })
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"Exception: {e}")
            results.append({
                "test": idx,
                "unit": item["unit"],
                "question": item["question"],
                "status": "ERROR",
                "latency_s": elapsed,
                "error": str(e)
            })

    print("\n" + "=" * 80)
    print("SUMMARY OF QA RETRIEVAL VERIFICATION:")
    for r in results:
        print(f" - Test {r['test']} [{r['unit']}]: {r['status']} ({r['latency_s']}s)")
    print("=" * 80)

    with open("scripts/qa_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Results saved to scripts/qa_verification_results.json")

if __name__ == "__main__":
    main()
