import asyncio
from fastapi.testclient import TestClient
from app.main import app

def run_test():
    print("Initializing TestClient (this will trigger background tasks synchronously)...")
    with TestClient(app) as client:
        payload = {
            "brief": "A sleek modern smart watch for fitness enthusiasts",
            "platforms": ["instagram"],
            "personas": ["professional"],
            "variants_count": 1
        }
        
        print("Submitting POST /api/v1/generate")
        response = client.post("/api/v1/generate", json=payload)
        print("Response status:", response.status_code)
        
        if response.status_code != 202:
            print("Failed to submit job:", response.json())
            return
            
        data = response.json()
        job_id = data["job_id"]
        print("Job ID:", job_id)
        
        print("Fetching GET /api/v1/status/" + job_id)
        status_resp = client.get(f"/api/v1/status/{job_id}")
        status_data = status_resp.json()
        print("Final Status:", status_data["status"])
        if status_data["status"] == "success":
            print("SUCCESS! Result payload:")
            print(status_data.get("result"))
        else:
            print("FAILED! Status payload:")
            print(status_data)

if __name__ == "__main__":
    run_test()
