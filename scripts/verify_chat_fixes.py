import time
import json
import httpx
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE_URL = "http://127.0.0.1:8100"

def test():
    client = httpx.Client(timeout=30.0)

    print("--- 1. Testing GET /api/models ---")
    resp = client.get(f"{BASE_URL}/api/models")
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Default model: {data.get('default')}")
    print(f"Available models count: {len(data.get('models', []))}")
    for m in data.get('models', []):
        print(f" - [{m.get('provider')}] {m.get('id')}: {m.get('name')}")

    print("\n--- 2. Testing GET /api/sources ---")
    resp_src = client.get(f"{BASE_URL}/api/sources")
    print(f"Status: {resp_src.status_code}")
    sources = resp_src.json()
    print(f"Indexed sources count: {len(sources)}")
    print(f"Sample source: {sources[0]['filename'] if sources else None}")

    print("\n--- 3. Testing POST /api/chat/global with OpenAI messages format (Fix 422) ---")
    t0 = time.time()
    resp_chat = client.post(
        f"{BASE_URL}/api/chat/global",
        json={
            "messages": [{"role": "user", "content": "What is SciGraph in one sentence?"}],
            "model": "openai/gpt-oss-20b"
        }
    )
    print(f"Status: {resp_chat.status_code} in {time.time() - t0:.2f}s")
    if resp_chat.status_code == 200:
        cdata = resp_chat.json()
        print(f"Model used: {cdata.get('model')}")
        print(f"Latency reported: {cdata.get('latency_ms')}ms")
        print(f"Reply: {cdata.get('reply')[:140]}...")
    else:
        print(f"Error: {resp_chat.text}")

    print("\n--- 4. Testing POST /api/chat/global with Research Mode & Sources filter ---")
    t0 = time.time()
    resp_res = client.post(
        f"{BASE_URL}/api/chat/global",
        json={
            "message": "What is the role of the discriminator in a GAN according to GA-Unit-3?",
            "mode": "research",
            "sources": ["GA-Unit-3.pdf"],
            "model": "openai/gpt-oss-20b"
        }
    )
    print(f"Status: {resp_res.status_code} in {time.time() - t0:.2f}s")
    if resp_res.status_code == 200:
        rdata = resp_res.json()
        print(f"Model: {rdata.get('model')}")
        print(f"Latency: {rdata.get('latency_ms')}ms (retrieval: {rdata.get('retrieval_ms')}ms)")
        print(f"Citations: {rdata.get('citations')}")
        print(f"Answer: {rdata.get('reply')[:180]}...")
    else:
        print(f"Error: {resp_res.text}")

if __name__ == "__main__":
    test()
