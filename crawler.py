import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import concurrent.futures
import threading
import os
from datetime import datetime
import random

# Thread-safe collections for visited URLs and broken links
visited_lock = threading.Lock()
broken_links_lock = threading.Lock()
file_lock = threading.Lock()

# Global output file
OUTPUT_FILE = "broken_links.txt"

# Configuration
MAX_RETRIES = 3
INITIAL_TIMEOUT = 20  # Increased from 10 to 20 seconds
MIN_DELAY = 1.0  # Minimum delay between requests
MAX_DELAY = 3.0  # Maximum delay between requests
MAX_WORKERS = 5  # Reduced from 10 to 5 to be more respectful

def is_valid_url(url):
    """Checks if a URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def is_target_domain(url, target_domain):
    """Checks if the URL belongs to the target domain."""
    try:
        parsed = urlparse(url)
        return target_domain in parsed.netloc
    except:
        return False

def is_mailto_link(url):
    """Checks if the URL is a mailto link."""
    return url.lower().startswith('mailto:')

def is_tel_link(url):
    """Checks if the URL is a tel link."""
    return url.lower().startswith('tel:')

def write_broken_link_to_file(origin, broken_link):
    """Write a broken link to the file incrementally."""
    with file_lock:
        with open(OUTPUT_FILE, "a") as f:
            f.write(f"{{{origin} >> {broken_link}}}\n")
        print(f"{{{origin} >> {broken_link}}}")

def fetch_url_with_retry(url, retries=MAX_RETRIES):
    """Fetch a URL with retry logic and exponential backoff."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(retries):
        try:
            # Add a random delay between requests
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            time.sleep(delay)
            
            # Use a session for better connection reuse
            with requests.Session() as session:
                response = session.get(url, timeout=INITIAL_TIMEOUT, headers=headers)
                response.raise_for_status()
                return response
                
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                # Exponential backoff: wait longer between each retry
                wait_time = 2 ** attempt
                print(f"Timeout for {url}, retrying in {wait_time} seconds... (Attempt {attempt+1}/{retries})")
                time.sleep(wait_time)
            else:
                raise
                
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                print(f"Error for {url}: {str(e)}, retrying in {wait_time} seconds... (Attempt {attempt+1}/{retries})")
                time.sleep(wait_time)
            else:
                raise

def crawl_url(url, visited, broken_links, target_domain, origin_url=None, max_workers=MAX_WORKERS, max_depth=3, current_depth=0):
    """Crawls a single URL and identifies broken links."""
    # Skip if we've reached max depth
    if current_depth > max_depth:
        return
    
    # Skip if already visited
    with visited_lock:
        if url in visited:
            return
        visited.add(url)
    
    # Skip if not from target domain
    if not is_target_domain(url, target_domain):
        return
    
    print(f"Crawling: {url}")
    
    try:
        # Use the retry logic for fetching the URL
        response = fetch_url_with_retry(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            links_to_crawl = []
            
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                
                # Skip mailto links
                if is_mailto_link(href):
                    continue
                    
                # Skip tel links
                if is_tel_link(href):
                    continue
                    
                absolute_url = urljoin(url, href)

                if is_valid_url(absolute_url):
                    links_to_crawl.append((absolute_url, url))
                else:
                    with broken_links_lock:
                        broken_links.add((url, f"Invalid URL: {absolute_url}"))
                        write_broken_link_to_file(url, f"Invalid URL: {absolute_url}")
                    print(f"Invalid URL: {absolute_url}")
            
            # Use ThreadPoolExecutor to crawl links in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for link_url, origin in links_to_crawl:
                    with visited_lock:
                        if link_url not in visited:
                            futures.append(
                                executor.submit(
                                    crawl_url, 
                                    link_url, 
                                    visited, 
                                    broken_links, 
                                    target_domain,
                                    origin, 
                                    max_workers, 
                                    max_depth, 
                                    current_depth + 1
                                )
                            )
                
                # Wait for all futures to complete
                concurrent.futures.wait(futures)

        elif response.status_code >= 400:
            with broken_links_lock:
                broken_links.add((origin_url or url, f"{url} - Status: {response.status_code}"))
                write_broken_link_to_file(origin_url or url, f"{url} - Status: {response.status_code}")
            print(f"Broken link: {url} - Status: {response.status_code}")

    except requests.exceptions.RequestException as e:
        with broken_links_lock:
            broken_links.add((origin_url or url, f"{url} - Error: {str(e)}"))
            write_broken_link_to_file(origin_url or url, f"{url} - Error: {str(e)}")
        print(f"Error crawling {url}: {e}")

    except Exception as e:
        with broken_links_lock:
            broken_links.add((origin_url or url, f"{url} - Error: {str(e)}"))
            write_broken_link_to_file(origin_url or url, f"{url} - Error: {str(e)}")
        print(f"Error processing {url}: {e}")

def main():
    """Main function to start the crawl."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python crawler.py <start_url>")
        print("Example: python crawler.py https://www.example.com/")
        sys.exit(1)
        
    start_url = sys.argv[1]
    
    # Extract domain from start URL
    try:
        parsed_url = urlparse(start_url)
        target_domain = parsed_url.netloc
    except Exception as e:
        print(f"Error parsing URL: {e}")
        sys.exit(1)
    
    visited_urls = set()
    broken_links = set()
    
    # Configure concurrency parameters
    max_depth = 3     # Maximum crawl depth
    
    # Clear the output file if it exists
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    
    print(f"Starting crawl with {MAX_WORKERS} concurrent workers and max depth of {max_depth}")
    print(f"Only crawling URLs from {target_domain} domain")
    print(f"Ignoring mailto and tel links")
    print(f"Broken links will be written to {OUTPUT_FILE}")
    print(f"Using retry logic with {MAX_RETRIES} attempts and {INITIAL_TIMEOUT}s timeout")
    print(f"Adding random delays between {MIN_DELAY}s and {MAX_DELAY}s between requests")
    
    # Start the crawl
    crawl_url(start_url, visited_urls, broken_links, target_domain, max_workers=MAX_WORKERS, max_depth=max_depth)

    print("\n--- Crawl Summary ---")
    print(f"Total URLs crawled: {len(visited_urls)}")
    print(f"Total broken links found: {len(broken_links)}")
    print(f"Broken links have been written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
