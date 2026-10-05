import time
import random
import threading
import requests
import sys

# --- CONFIGURATION ---
FILE_PATH = "image_ids.txt" # Change this to your text file name
CONCURRENCY = 150            # Number of simultaneous threads
RUNTIME_SECONDS = 6 * 3600  # 3 hours in seconds
URL_TEMPLATE = "https://m.media-amazon.com/images/M/{id}@._V1_SX90000_SY90000_AL_US900000_QL100_FMpng_.png"

def load_ids(filepath):
    """Loads image IDs from the text file into memory."""
    try:
        with open(filepath, 'r') as f:
            # Read lines, strip whitespace, and ignore empty lines
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Could not find the file '{filepath}'.")
        sys.exit(1)

def load_test_worker(worker_id, image_ids, end_time, results_dict):
    """
    The worker function executed by each thread.
    Runs continuously until the end_time is reached.
    """
    # Using a Session per thread optimizes performance by reusing TCP/SSL connections
    session = requests.Session()
    
    # Optional: Configure connection pool size for this specific session
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1)
    session.mount('https://', adapter)

    req_count = 0
    success_count = 0
    failed_count = 0
    total_bytes = 0

    # Run as fast as computationally possible until 3 hours pass
    while time.time() < end_time:
        image_id = random.choice(image_ids)
        url = URL_TEMPLATE.format(id=image_id)
        
        try:
            response = session.get(url, timeout=15)
            req_count += 1
            total_bytes += len(response.content)

            if response.status_code == 200:
                success_count += 1
            else:
                failed_count += 1
                # Log the non-200 status code immediately
                print(f"[Worker {worker_id}] Warning: Received status {response.status_code} for image '{image_id}'", flush=True)
                
        except requests.exceptions.RequestException as e:
            req_count += 1
            failed_count += 1
            # Log timeouts or connection drops
            print(f"[Worker {worker_id}] Error: {type(e).__name__} for image '{image_id}'", flush=True)

        # Push live stats to the shared dictionary every 50 requests
        if req_count % 50 == 0:
            results_dict[worker_id] = {
                "requests": req_count, "success": success_count,
                "failed": failed_count, "bytes": total_bytes
            }

    # Final update when loop naturally finishes
    results_dict[worker_id] = {
        "requests": req_count, "success": success_count,
        "failed": failed_count, "bytes": total_bytes
    }

def main():
    print("Initializing Load Test...")
    image_ids = load_ids(FILE_PATH)
    
    if not image_ids:
        print("Error: The image IDs file is empty.")
        sys.exit(1)
        
    print(f"Successfully loaded {len(image_ids)} image IDs.")
    
    # Setup timing and threading structures
    end_time = time.time() + RUNTIME_SECONDS
    threads = []
    results_dict = {i: {"requests": 0, "success": 0, "failed": 0, "bytes": 0} for i in range(CONCURRENCY)}

    print(f"\nStarting {CONCURRENCY} concurrent threads...")
    print(f"Test will run for exactly {RUNTIME_SECONDS / 3600} hours. Please wait...\n")

    start_time = time.time()

    # Spawn the threads
    for i in range(CONCURRENCY):
        t = threading.Thread(target=load_test_worker, args=(i, image_ids, end_time, results_dict))
        threads.append(t)
        t.start()
    print("\nBeginning load test (printing live progress every 60 seconds)...", flush=True)
    # Monitor progress while threads are running
    while any(t.is_alive() for t in threads):
        # Sleep in 1-second chunks to break out cleanly if threads finish early
        for _ in range(60):
            if not any(t.is_alive() for t in threads):
                break
            time.sleep(1)
            
        if any(t.is_alive() for t in threads):
            elapsed = time.time() - start_time
            current_reqs = sum(res["requests"] for res in results_dict.values())
            print(f"Progress: {elapsed/60:.1f} / {RUNTIME_SECONDS/60:.1f} mins elapsed | Live Requests: {current_reqs:,}...", flush=True)

    # Clean up at the very end
    for t in threads:
        t.join()
    actual_duration = time.time() - start_time

    # Aggregate results from all 10 threads
    total_requests = sum(res["requests"] for res in results_dict.values())
    total_success = sum(res["success"] for res in results_dict.values())
    total_failed = sum(res["failed"] for res in results_dict.values())
    total_bytes = sum(res["bytes"] for res in results_dict.values())

    # Convert bytes to Gigabytes (1 GB = 1024^3 bytes) for easier cost calculation
    total_gb = total_bytes / (1024 ** 3)
    requests_per_second = total_requests / actual_duration

    # --- REPORTING ---
    print("="*40)
    print("         LOAD TEST COMPLETED")
    print("="*40)
    print(f"Total Runtime:       {actual_duration:.2f} seconds")
    print(f"Total Requests:      {total_requests:,}")
    print(f"Successful (200):    {total_success:,}")
    print(f"Failed/Errors:       {total_failed:,}")
    print(f"Average Rate:        {requests_per_second:.2f} requests/sec")
    print("-" * 40)
    print(f"Total Data Transfer: {total_gb:.4f} GB")
    print("="*40)
    
    print("\nNext steps: Multiply the 'Total Data Transfer' by your cloud/CDN provider's price per GB to find your load test cost.")

if __name__ == "__main__":
    main()
