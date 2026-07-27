import asyncio
import json
import time
import uuid
import jwt
import httpx
import http.server
import threading
import statistics
import os
import sqlite3
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load env variables from backend/.env relative to this script
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

# Configurations
APP_URL = "http://127.0.0.1:8000"
MOCK_WIKI_PORT = 8085
CONCURRENT_USERS = 100  # Number of concurrent tasks/users
REQUESTS_PER_USER = 5   # Requests each user will submit
SUBMIT_BATCH_SIZE = 10  # Number of articles in each bulk submit request
JWT_SECRET = os.getenv("SESSION_SECRET", "super-secret")
JWT_ALGORITHM = "HS256"

# Mock MediaWiki response handler to intercept requests
class MockWikiHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        # We simulate a successful revisions query
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        
        # Read request body to gather titles
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        # Extract titles from body (or just respond generically)
        response = {
            "query": {
                "pages": {
                    "1001": {
                        "pageid": 1001,
                        "title": "Mock Article",
                        "revisions": [
                            {
                                "user": "TestCreator",
                                "timestamp": "2026-07-20T12:00:00Z"
                            }
                        ]
                    }
                }
            }
        }
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        pass  # Suppress logs for quiet performance

def start_mock_wiki():
    server = http.server.HTTPServer(("127.0.0.1", MOCK_WIKI_PORT), MockWikiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[*] Local Mock Wikipedia API running on http://127.0.0.1:{MOCK_WIKI_PORT}")

# Pre-populate database with benchmark users and test contest to bypass authentication barriers
def precreate_benchmark_users():
    db_path = os.path.join(os.path.dirname(__file__), "app.db")
    if not os.path.exists(db_path):
        print(f"[!] Warning: Database not found at {db_path}. Please start the FastAPI server once to initialize the DB.")
        return False
        
    print(f"[*] Connecting to database at {db_path} to register benchmark users...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Register benchmark users
        for i in range(CONCURRENT_USERS):
            username = f"BenchmarkUser_{i}"
            cursor.execute("INSERT OR IGNORE INTO users (wiki_username, role) VALUES (?, 'participant')", (username,))
            
        # Register test_code contest
        cursor.execute("SELECT id FROM contests WHERE code='test_code'")
        if not cursor.fetchone():
            # SQLite datetimes as ISO strings
            cursor.execute(
                "INSERT INTO contests (code, name, start_date, end_date, rule_must_be_creator) VALUES (?, ?, ?, ?, ?)",
                ("test_code", "Benchmark Test Contest", "2026-07-01 00:00:00", "2026-07-31 23:59:59", 0)
            )
        conn.commit()
        conn.close()
        print("[*] Successfully registered benchmark users and contest in SQLite.")
        return True
    except Exception as e:
        print(f"[!] Error pre-populating database: {repr(e)}")
        return False

# Helper to generate signed JWT cookies for virtual test users
def generate_auth_cookie(username: str) -> dict:
    expire = datetime.utcnow() + timedelta(days=1)
    payload = {"sub": username, "role": "participant", "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"auth_token": token}

async def simulate_user(user_id: int, results: list):
    username = f"BenchmarkUser_{user_id}"
    cookies = generate_auth_cookie(username)
    
    # Randomize startup time slightly to prevent simultaneous connection storm
    await asyncio.sleep(random.uniform(0.0, 1.5))
    
    async with httpx.AsyncClient(cookies=cookies, timeout=60.0) as client:
        # Pre-verify registration
        try:
            me_resp = await client.get(f"{APP_URL}/api/me")
            if me_resp.status_code != 200:
                results.append({"status": "fail", "latency": 0, "error": f"Auth failed (HTTP {me_resp.status_code}): {me_resp.text}"})
                return
        except Exception as e:
            results.append({"status": "fail", "latency": 0, "error": f"Auth connection failed: {repr(e)}"})
            return

        for i in range(REQUESTS_PER_USER):
            # Minor delay between requests to simulate typing/clicking pacing
            await asyncio.sleep(random.uniform(0.1, 0.4))
            
            # Generate random article titles for each request to avoid duplicate checks
            titles = [f"Article_{uuid.uuid4().hex[:12]}" for _ in range(SUBMIT_BATCH_SIZE)]
            payload = {
                "contest_code": "test_code",
                "titles": titles
            }
            
            start_time = time.perf_counter()
            try:
                # Post bulk submit request
                resp = await client.post(f"{APP_URL}/api/submit-bulk", json=payload)
                latency = time.perf_counter() - start_time
                if resp.status_code == 200:
                    results.append({"status": "success", "latency": latency})
                else:
                    results.append({"status": "fail", "latency": latency, "error": f"HTTP {resp.status_code}: {resp.text}"})
            except Exception as e:
                latency = time.perf_counter() - start_time
                results.append({"status": "fail", "latency": latency, "error": repr(e)})

async def main():
    print("====================================================")
    print("        WIKI ARTICLE CONTEST BENCHMARK TOOL        ")
    print("====================================================")
    
    # 1. Precreate benchmark users
    if not precreate_benchmark_users():
        return
        
    # 2. Start Mock API server
    start_mock_wiki()
    
    # 3. Check if main app is running
    async with httpx.AsyncClient() as client:
        try:
            await client.get(APP_URL)
        except Exception:
            print(f"\n[!] Error: The FastAPI server does not seem to be running at {APP_URL}")
            print("    Please start it first: `uvicorn main:app --reload --port 8000`")
            return
            
    print(f"\n[*] Preparing benchmark with:")
    print(f"    - Concurrent users: {CONCURRENT_USERS}")
    print(f"    - Requests per user: {REQUESTS_PER_USER}")
    print(f"    - Submission size per request: {SUBMIT_BATCH_SIZE} articles")
    print(f"    - Total requests to send: {CONCURRENT_USERS * REQUESTS_PER_USER}")
    print(f"    - Total articles to submit: {CONCURRENT_USERS * REQUESTS_PER_USER * SUBMIT_BATCH_SIZE}")
    print("\n[*] Initializing test contest 'test_code'...")
    
    # Create the test contest if it doesn't exist
    owner_cookies = generate_auth_cookie("R1F4T") # Hardcoded owner
    async with httpx.AsyncClient(cookies=owner_cookies) as client:
        # Check if contest exists, otherwise create it
        res = await client.get(f"{APP_URL}/api/contests/test_code")
        if res.status_code != 200:
            contest_data = {
                "name": "Benchmark Test Contest",
                "start_date": "2026-07-01T00:00:00",
                "end_date": "2026-07-31T23:59:59",
                "rule_must_be_creator": False # Disable creator check for easy testing
            }
            # Add manually to DB or mock call
            await client.post(f"{APP_URL}/api/admin/contests", json=contest_data)
            # Create a contest with code 'test_code'
            # Note: create_contest creates random code, but we can verify it created
            print("[*] Created test contest. If code is different, make sure 'test_code' is in database or rename.")
            
    print("\n[!] IMPORTANT: Ensure you start the server with the environment override:")
    print("    Windows:  $env:MEDIAWIKI_API_URL='http://127.0.0.1:8085'; uvicorn main:app --port 8000")
    print("    Linux/Mac: MEDIAWIKI_API_URL='http://127.0.0.1:8085' uvicorn main:app --port 8000")
    
    input("\nPress ENTER when FastAPI server is restarted with the above environment variable...")
    
    print("\n[*] Starting benchmark load test...")
    start_time = time.perf_counter()
    results = []
    
    tasks = [simulate_user(i, results) for i in range(CONCURRENT_USERS)]
    await asyncio.gather(*tasks)
    
    total_time = time.perf_counter() - start_time
    
    # Process results
    success_requests = [r for r in results if r["status"] == "success"]
    failed_requests = [r for r in results if r["status"] == "fail"]
    latencies = [r["latency"] for r in success_requests]
    
    print("\n====================================================")
    print("                BENCHMARK RESULTS                   ")
    print("====================================================")
    print(f"Total Test Duration:  {total_time:.2f} seconds")
    print(f"Total Requests Sent: {len(results)}")
    print(f"Successful Requests: {len(success_requests)} ({len(success_requests)/len(results)*100:.1f}%)")
    print(f"Failed Requests:     {len(failed_requests)} ({len(failed_requests)/len(results)*100:.1f}%)")
    
    if latencies:
        print(f"Throughput:          {len(success_requests) / total_time:.2f} requests/sec (RPS)")
        print(f"Average Latency:     {statistics.mean(latencies)*1000:.1f} ms")
        print(f"Median Latency:      {statistics.median(latencies)*1000:.1f} ms")
        print(f"Min Latency:         {min(latencies)*1000:.1f} ms")
        print(f"Max Latency:         {max(latencies)*1000:.1f} ms")
        print(f"90th Percentile:     {statistics.quantiles(latencies, n=10)[8]*1000:.1f} ms")
        print(f"99th Percentile:     {statistics.quantiles(latencies, n=100)[98]*1000:.1f} ms")
    
    if failed_requests:
        print("\n[*] Errors Sample:")
        errors = {}
        for f in failed_requests:
            err = f.get("error", "Unknown Error")
            errors[err] = errors.get(err, 0) + 1
        for err, count in list(errors.items())[:5]:
            print(f"    - {err}: occurred {count} times")
    print("====================================================")

if __name__ == "__main__":
    asyncio.run(main())
