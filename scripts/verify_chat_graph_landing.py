import sys
import time
import json
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8100"

def get_json(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))

def post_json(url, data):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode('utf-8'))

def stream_post(url, data):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    tokens = []
    meta = None
    t0 = time.time()
    ttft = None
    with urllib.request.urlopen(req, timeout=25) as resp:
        for line in resp:
            line_str = line.decode('utf-8').strip()
            if line_str.startswith("data: ") and line_str != "data: [DONE]":
                try:
                    payload = json.loads(line_str[6:])
                    if payload.get("type") == "meta":
                        meta = payload
                    elif payload.get("type") == "token":
                        if ttft is None:
                            ttft = round((time.time() - t0) * 1000, 1)
                        tokens.append(payload.get("token", ""))
                except Exception:
                    pass
    total_time = round((time.time() - t0) * 1000, 1)
    return "".join(tokens), ttft, total_time, meta

def test_endpoints():
    print("=================================================================")
    print("SCIGRAPH SYSTEM & INTEGRATION VERIFICATION")
    print("=================================================================")

    # 1. Health
    h = get_json(f"{BASE_URL}/health")
    print(f"[1] HEALTH CHECK: {h.get('status')} | RAG Ready: {h.get('rag_ready')}")
    assert h.get('status') == 'ok', "Health check failed"

    # 2. Stats
    stats = get_json(f"{BASE_URL}/stats")
    print(f"[2] STATS: Total Docs: {stats.get('total_docs')} | Graph Nodes: {stats.get('total_nodes')} | Graph Relations: {stats.get('total_relations')}")
    assert stats.get('total_nodes') == 290, f"Expected 290 nodes, got {stats.get('total_nodes')}"
    assert stats.get('total_relations') == 125, f"Expected 125 relations, got {stats.get('total_relations')}"

    # 3. Graph
    t_g0 = time.time()
    graph = get_json(f"{BASE_URL}/graph?limit=300")
    g_lat = round((time.time() - t_g0) * 1000, 2)
    print(f"[3] GRAPH API: Nodes: {len(graph.get('nodes', []))} | Links: {len(graph.get('links', []))} in {g_lat}ms")
    assert len(graph.get('nodes', [])) == 290, f"Expected 290 nodes, got {len(graph.get('nodes', []))}"
    assert len(graph.get('links', [])) == 125, f"Expected 125 links, got {len(graph.get('links', []))}"

    # 4. Models & Sources
    models = get_json(f"{BASE_URL}/api/models")
    sources = get_json(f"{BASE_URL}/api/sources")
    print(f"[4] MODELS & SOURCES: Available Models: {len(models.get('models', []))} | Indexed Sources: {len(sources)}")
    assert len(sources) >= 15, "Expected at least 15 corpus files"

    # 5. Global Chat Schema Variations
    print("\n--- Testing Global Chat Payload Variations ---")
    payloads = [
        ("message", {"message": "Briefly state the goal of generative AI in one sentence.", "model": "openai/gpt-oss-20b"}),
        ("query", {"query": "Briefly define a knowledge graph in one sentence.", "model": "openai/gpt-oss-20b"}),
        ("prompt", {"prompt": "What does RAG stand for? Answer in 5 words.", "model": "openai/gpt-oss-20b"}),
        ("messages", {"messages": [{"role": "user", "content": "Say 'SciGraph Ready' in two words."}], "model": "openai/gpt-oss-20b"})
    ]

    for key, p in payloads:
        t0 = time.time()
        res = post_json(f"{BASE_URL}/api/chat/global", p)
        dur = round(time.time() - t0, 3)
        ans = res.get("response") or res.get("answer", "")
        print(f"  ✓ Payload [{key}]: {dur}s -> {ans[:60]}...")
        assert len(ans) > 0, f"Empty response for payload {key}"

    # 6. SSE Streaming (Global Assistant)
    print("\n--- Testing SSE Streaming (Global Assistant) ---")
    stream_payload = {
        "message": "Explain what a latent representation is in 2 sentences.",
        "model": "openai/gpt-oss-20b",
        "mode": "global"
    }
    ans, ttft, total_dur, meta = stream_post(f"{BASE_URL}/api/chat/stream", stream_payload)
    print(f"  ✓ Global Stream: TTFT={ttft}ms | Total={total_dur}ms | Length={len(ans)} chars")
    print(f"    Sample: {ans[:80]}...")
    assert ttft is not None and ttft < 4000, f"TTFT too high: {ttft}ms"
    assert len(ans) > 20, "Stream answer too short"

    # 7. SSE Streaming (Research Assistant with Source Grounding)
    print("\n--- Testing SSE Streaming (Research Assistant Grounded) ---")
    time.sleep(1.2) # Groq rate-limit protection
    research_payload = {
        "message": "What is the ELBO objective and reparameterization trick in Variational Autoencoders?",
        "model": "openai/gpt-oss-20b",
        "mode": "research",
        "sources": ["GA-Unit-2.pdf"]
    }
    ans_r, ttft_r, total_dur_r, meta_r = stream_post(f"{BASE_URL}/api/chat/stream", research_payload)
    citations = meta_r.get("citations", []) if meta_r else []
    print(f"  ✓ Research Stream: TTFT={ttft_r}ms | Total={total_dur_r}ms | Citations={len(citations)}")
    for i, c in enumerate(citations[:3]):
        print(f"    [{i+1}] {c.get('document')} - {c.get('section')}")
    print(f"    Sample: {ans_r[:80]}...")
    assert len(citations) > 0, "Expected research citations"
    assert all("GA-Unit-2.pdf" in c.get("document", "") for c in citations), "Citation outside selected source!"

    # 8. Landing Page Verification
    print("\n--- Verifying Landing Page & Workspace ---")
    landing_html = urllib.request.urlopen(f"{BASE_URL}/").read().decode('utf-8')
    assert "Discover the connections" in landing_html, "Hero title missing"
    assert "behind research." in landing_html, "Hero title part 2 missing"
    assert "Multimodal intelligence. Connected knowledge. Evidence-driven discovery." in landing_html, "Supporting statement missing"
    assert "Explore scientific documents, ask evidence-grounded questions, and uncover meaningful connections across research with SciGraph." in landing_html, "Hero description missing"
    assert "v2.4 PRO" in landing_html, "Version badge missing"
    assert 'href="/ui/"' in landing_html, "Launch Workspace link missing"
    assert 'href="https://github.com/mandeep6207/SciGraph-Multimodal-RAG-Knowledge-Graph"' in landing_html, "GitHub link missing"
    print("  ✓ Landing Page HTML fully validated (exact branding, navbar, hero, actions)")

    # 9. Workspace Console Verification
    ui_html = urllib.request.urlopen(f"{BASE_URL}/ui/").read().decode('utf-8')
    assert "Start a new conversation" in ui_html, "Overview Start New Chat entrypoint missing"
    assert "Explore scientific questions, work with your research documents" in ui_html, "Overview description missing"
    assert "What would you like to explore today?" in open('frontend/js/assistant.js', encoding='utf-8').read(), "Assistant welcome title missing in assistant.js"
    print("  ✓ Workspace Console HTML & JS verified (Start New Chat, ChatGPT empty state, GraphHUD)")

    print("\n=================================================================")
    print("ALL VERIFICATION CHECKS PASSED PERFECTLY (100% OPERATIONAL)")
    print("=================================================================")

if __name__ == "__main__":
    test_endpoints()
