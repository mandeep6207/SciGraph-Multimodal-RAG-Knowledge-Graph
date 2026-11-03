import httpx
import time
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def test_stream():
    print("Testing POST /api/chat/stream (SSE streaming)...")
    t0 = time.time()
    first_token_time = None
    chunks_count = 0
    full_text = []

    with httpx.Client(timeout=30.0) as client:
        with client.stream(
            "POST",
            "http://127.0.0.1:8100/api/chat/stream",
            json={
                "message": "Summarize the concept of attention in 20 words.",
                "model": "openai/gpt-oss-20b"
            }
        ) as response:
            print(f"Connection opened in {time.time() - t0:.2f}s, status: {response.status_code}")
            for line in response.iter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    data = json.loads(line[6:])
                    if data.get("type") == "token":
                        if first_token_time is None:
                            first_token_time = time.time() - t0
                        token = data.get("token", "")
                        full_text.append(token)
                        chunks_count += 1

    total_time = time.time() - t0
    print(f"First token received in: {first_token_time:.2f}s")
    print(f"Total stream duration: {total_time:.2f}s (received {chunks_count} tokens)")
    print("Joined text:", "".join(full_text).strip())

if __name__ == "__main__":
    test_stream()
