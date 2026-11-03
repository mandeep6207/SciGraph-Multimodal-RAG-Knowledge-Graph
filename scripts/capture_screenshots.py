import subprocess
import time
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT_DIR = os.path.abspath("docs/screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

targets = [
    ("01_landing_page.png", "http://127.0.0.1:8100/", 4000, "1600,1000"),
    ("02_workspace_overview.png", "http://127.0.0.1:8100/ui/#overview", 4000, "1600,1000"),
    ("03_universal_ai_assistant.png", "http://127.0.0.1:8100/ui/#assistant", 4000, "1600,1000"),
    ("04_knowledge_graph_3d.png", "http://127.0.0.1:8100/ui/#graph", 5000, "1600,1000"),
    ("05_research_library.png", "http://127.0.0.1:8100/ui/#library", 4000, "1600,1000")
]

for filename, url, budget, size in targets:
    out_path = os.path.join(OUT_DIR, filename)
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={size}",
        f"--virtual-time-budget={budget}",
        f"--screenshot={out_path}",
        url
    ]
    print(f"Capturing {filename} from {url}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(out_path):
        size_kb = round(os.path.getsize(out_path) / 1024, 1)
        print(f"  ✓ Saved {filename} ({size_kb} KB)")
    else:
        print(f"  ✕ Failed to capture {filename}: {res.stderr}")

print("All screenshots capture finished.")
