"""
test_concurrency.py
─────────────────────────────────────────────
Stress test client for Week 3.
Dispatches 5 concurrent generation requests to the running FastAPI server
and polls their statuses to demonstrate asynchronous Celery execution.
"""
import asyncio
import httpx
import time

API_URL = "http://localhost:8000/api/v1/generate"
STATUS_URL = "http://localhost:8000/api/v1/status"

TEST_BRIEFS = [
    "A glowing futuristic neon cybernetic shoe running in a clean dark alleyway.",
    "Vintage retro polaroid photo of organic specialty coffee beans on wood.",
    "A sleek luxury electric sports car charging under dynamic neon lighting.",
    "Minimalist workspace setup with high-end designer mechanical keyboard.",
    "Premium organic matcha powder whisked inside a traditional ceramic bowl."
]


async def submit_job(client: httpx.AsyncClient, brief: str, index: int) -> str:
    payload = {
        "brief": brief,
        "platforms": ["instagram"],
        "personas": ["witty" if index % 2 == 0 else "professional"],
        "variants_count": 1
    }
    print(f"[Submit] Dispatching job {index}: '{brief[:40]}...'")
    response = await client.post(API_URL, json=payload)
    if response.status_code == 202:
        job_id = response.json()["job_id"]
        print(f"[Submit] Job {index} accepted. Job ID: {job_id}")
        return job_id
    else:
        raise RuntimeError(f"Failed to submit job {index}: {response.text}")


async def poll_job(client: httpx.AsyncClient, job_id: str, index: int) -> dict:
    while True:
        response = await client.get(f"{STATUS_URL}/{job_id}")
        if response.status_code == 200:
            payload = response.json()
            status = payload["status"]
            print(f"[Poll] Job {index} ({job_id[:8]}...): {status}")
            if status in ("SUCCESS", "FAILED"):
                return payload
        else:
            print(f"[Error] Failed to poll status for {job_id}: {response.text}")
        await asyncio.sleep(3)


async def main():
    print("=== Starting Celery Concurrency Stress Test ===")
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Submit all 5 jobs concurrently
        submission_tasks = [
            submit_job(client, brief, i)
            for i, brief in enumerate(TEST_BRIEFS)
        ]
        job_ids = await asyncio.gather(*submission_tasks)
        
        print("\nAll jobs submitted successfully! Beginning polling loop...\n")
        
        # Poll all jobs concurrently until they finish
        polling_tasks = [
            poll_job(client, job_id, i)
            for i, job_id in enumerate(job_ids)
        ]
        results = await asyncio.gather(*polling_tasks)
        
    duration = time.time() - start_time
    print(f"\n=== Stress Test Complete in {duration:.2f} seconds ===")
    
    successes = sum(1 for r in results if r["status"] == "SUCCESS")
    failures = sum(1 for r in results if r["status"] == "FAILED")
    
    print(f"Total Successes: {successes} / 5")
    print(f"Total Failures: {failures} / 5")
    
    for i, r in enumerate(results):
        job_id = r["job_id"]
        status = r["status"]
        if status == "SUCCESS":
            print(f"Job {i} ({job_id[:8]}...): SUCCESS | Image: {r.get('image_url')}")
        else:
            print(f"Job {i} ({job_id[:8]}...): FAILED | Error: {r.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
