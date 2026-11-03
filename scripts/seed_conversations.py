import json
import time
from pathlib import Path

conv_path = Path("data/rag_storage/conversations.json")
qa_path = Path("scripts/qa_verification_results.json")

if qa_path.exists():
    with open(qa_path, "r", encoding="utf-8") as f:
        qa_data = json.load(f)
    
    messages = []
    for item in qa_data:
        messages.append({
            "role": "user",
            "content": item["question"],
            "timestamp": int(time.time() - 300)
        })
        messages.append({
            "role": "assistant",
            "content": item["full_answer"],
            "timestamp": int(time.time() - 280),
            "mode": item.get("mode", "hybrid"),
            "latency": f"{item.get('latency_s', 10)}s"
        })
    
    conv = {
        "id": "conv-genai-unit-qa",
        "title": "Generative AI Units 1-5 Synthesis",
        "created_at": int(time.time() - 600),
        "updated_at": int(time.time()),
        "messages": messages
    }

    existing = []
    if conv_path.exists():
        try:
            with open(conv_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    # Update or insert
    existing = [c for c in existing if c.get("id") != "conv-genai-unit-qa"]
    existing.insert(0, conv)

    conv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(conv_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(messages)} messages to {conv_path}")
