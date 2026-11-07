import requests
import json

BASE_URL = "http://localhost:8000"

SCRAPE_BODY = {
    "keywords": "Software Engineer",
    "location": "India",
    "num_pages": 1,
    "filters": {"f_TPR": "r2592000"}
}


def save(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=10)
    print(f"Saved → {filename}")


# 1. /jobs
print("Testing /jobs ")
r = requests.post(f"{BASE_URL}/jobs", json=SCRAPE_BODY)
save("test_all_jobs.json", r.json())

# 2. /jobs/slice?n=3
print("Testing /jobs/slice ")
r = requests.post(f"{BASE_URL}/jobs/slice?n=3", json=SCRAPE_BODY)
save("test_sliced_jobs.json", r.json())

# 3.     /profiles  — feed the sliced jobs back in
print("Testing /profiles ")
with open("test_sliced_jobs.json", "r") as f:
    sliced_jobs = json.load(f)

r = requests.post(f"{BASE_URL}/profiles", json={"jobs": sliced_jobs})
save("test_enriched_profiles.json", r.json())

# 4.  /jobs-with-profiles
print(" Testing /jobs-with-profiles ")
r = requests.post(f"{BASE_URL}/jobs-with-profiles", json={
    "keywords": "Software Engineer",
    "location": "India",
    "num_pages": 1,
    "filters": {"f_TPR": "r2592000"},
    "n": 3
})
save("test_full_pipeline.json", r.json())

print("\nAll are done")