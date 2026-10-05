import os
import sys
import requests
import concurrent.futures

# --- CONFIGURATION ---
FILE_PATH = "image_ids.txt" # Must be at the root of the repo
TOP_N = 50
THREADS = 20 # Safe concurrency for fetching headers quickly
URL_TEMPLATE = "https://m.media-amazon.com/images/M/{id}@._V1_SX90000_SY90000_AL_US900000_QL100_FMpng_.png"

def get_image_size(image_id):
    """Fetches the file size of an image using an HTTP HEAD request."""
    url = URL_TEMPLATE.format(id=image_id)
    try:
        # A HEAD request fetches headers only, saving massive amounts of bandwidth/time
        response = requests.head(url, timeout=10, allow_redirects=True)
        
        # Fallback: If server rejects HEAD or hides Content-Length, do a streaming GET
        if response.status_code != 200 or 'Content-Length' not in response.headers:
            response = requests.get(url, stream=True, timeout=10)
            
        size_bytes = int(response.headers.get('Content-Length', 0))
        return (image_id, size_bytes)
    except Exception as e:
        # Return 0 if the request fails (timeout, 404, etc.)
        return (image_id, 0)

def main():
    # 1. Load the file from the repo root
    if not os.path.exists(FILE_PATH):
        print(f"Error: Could not find '{FILE_PATH}' in the repository root.")
        sys.exit(1)

    with open(FILE_PATH, 'r') as f:
        image_ids = [line.strip() for line in f if line.strip()]

    if not image_ids:
        print("Error: The image IDs file is empty.")
        sys.exit(1)

    print(f"Loaded {len(image_ids)} image IDs. Assessing file sizes using {THREADS} threads...")

    results = []
    
    # 2. Fetch sizes concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        # Submit all tasks to the executor
        future_to_id = {executor.submit(get_image_size, img_id): img_id for img_id in image_ids}
        
        # As each task completes, append it to our results list
        for future in concurrent.futures.as_completed(future_to_id):
            results.append(future.result())

    # 3. Sort results by size (descending) and grab the top 50
    results.sort(key=lambda x: x[1], reverse=True)
    top_images = results[:TOP_N]

    # 4. Format the output as a Markdown table
    summary_lines = [
        "### Top 50 Largest Images",
        "| Rank | Image ID | Size (MB) | Size (Bytes) |",
        "| :---: | :--- | :---: | :---: |"
    ]
    
    for rank, (img_id, size) in enumerate(top_images, start=1):
        size_mb = size / (1024 * 1024)
        summary_lines.append(f"| {rank} | `{img_id}` | {size_mb:.2f} MB | {size:,} |")

    summary_text = "\n".join(summary_lines)
    
    # Print to console/logs
    print("\n" + summary_text)

    # 5. Write to GitHub Actions Job Summary UI
    step_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_file:
        with open(step_summary_file, "a") as f:
            f.write(summary_text)

if __name__ == "__main__":
    main()
