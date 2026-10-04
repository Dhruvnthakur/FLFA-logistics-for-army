"""Wake a sleeping Render API and warm its caches before a demo (stdlib only).

    python simulator/warmup.py [--api https://forward-supply-api.onrender.com]
"""
import argparse
import os
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
base = p.parse_args().api.rstrip("/")

# /health wakes the dyno; /stock fills the demand cache; /dispatch-plan and /routes warm the planner and graph
for path in ("/health", "/stock", "/dispatch-plan", "/routes"):
    for attempt in range(1, 9):
        t = time.time()
        try:
            with urllib.request.urlopen(base + path, timeout=180) as r:
                print(f"{path}: {r.status} in {time.time() - t:.1f}s")
            break
        except Exception as e:
            print(f"{path}: attempt {attempt} failed ({e}); retrying in 10s")
            time.sleep(10)
    else:
        raise SystemExit(f"{path} never came up")
print("warm")
