import urllib.request
import json

resp = urllib.request.urlopen("http://127.0.0.1:8100/jobs")
jobs = json.loads(resp.read().decode())
print(f"Total jobs: {len(jobs)}")
for j in jobs:
    print(f"{j.get('filename')}: status={j.get('status')}, stage={j.get('stage')}, progress={j.get('progress')}%")
