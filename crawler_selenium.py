import time
import concurrent.futures
import threading
import os
from datetime import datetime
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Thread-safe collections for visited URLs and broken links
visited_lock = threading.Lock()
broken_links_lock = threading.Lock()
file_lock = threading.Lock()

# Global output file
OUTPUT_FILE = "broken_links_selenium.txt"

def is_valid_url(url):
    """Checks if a URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def is_rbo_domain(url):
    """Checks if the URL belongs to the rbo.org.uk domain."""
    try:
        parsed = urlparse(url)
        return 'rbo.org.uk' in parsed.netloc
    except:
        return False

def is_mailto_link(url):
    """Checks if the URL is a mailto link."""
    return url.lower().startswith('mailto:')

def write_broken_link_to_file(origin, broken_link):
    """Write a broken link to the file incrementally."""
    with file_lock:
        with open(OUTPUT_FILE, "a") as f:
            f.write(f"{{{origin} >> {broken_link}}}\n")
        print(f"{{{origin} >> {broken_link}}}")

def create_driver():
    """Create and return a headless Chrome driver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def crawl_url(url, visited, broken_links, origin_url=None, max_workers=10, max_depth=3, current_depth=0):
    """Crawls a single URL and identifies broken links."""
    # Skip if we've reached max depth
    if current_depth > max_depth:
        return
    
    # Skip if already visited
    with visited_lock:
        if url in visited:
            return
        visited.add(url)
    
    # Skip if not from rbo.org.uk domain
    if not is_rbo_domain(url):
        return
    
    print(f"Crawling: {url}")
    
    driver = None
    try:
        driver = create_driver()
        driver.get(url)
        
        # Wait for React to render (adjust timeout as needed)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Give extra time for React to fully render
        time.sleep(2)
        
        # Get all links after React has rendered
        links = driver.find_elements(By.TAG_NAME, "a")
        links_to_crawl = []
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if not href:
                    continue
                
                # Skip mailto links
                if is_mailto_link(href):
                    continue
                    
                absolute_url = urljoin(url, href)

                if is_valid_url(absolute_url):
                    links_to_crawl.append((absolute_url, url))
                else:
                    with broken_links_lock:
                        broken_links.add((url, f"Invalid URL: {absolute_url}"))
                        write_broken_link_to_file(url, f"Invalid URL: {absolute_url}")
                    print(f"Invalid URL: {absolute_url}")
            except Exception as e:
                print(f"Error processing link: {e}")
        
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
                                origin, 
                                max_workers, 
                                max_depth, 
                                current_depth + 1
                            )
                        )
            
            # Wait for all futures to complete
            concurrent.futures.wait(futures)

    except TimeoutException:
        with broken_links_lock:
            broken_links.add((origin_url or url, f"{url} - Error: Page load timeout"))
            write_broken_link_to_file(origin_url or url, f"{url} - Error: Page load timeout")
        print(f"Timeout loading {url}")
    
    except WebDriverException as e:
        with broken_links_lock:
            broken_links.add((origin_url or url, f"{url} - Error: {str(e)}"))
            write_broken_link_to_file(origin_url or url, f"{url} - Error: {str(e)}")
        print(f"Error crawling {url}: {e}")
    
    except Exception as e:
        with broken_links_lock:
            broken_links.add((origin_url or url, f"{url} - Error: {str(e)}"))
            write_broken_link_to_file(origin_url or url, f"{url} - Error: {str(e)}")
        print(f"Error processing {url}: {e}")
    
    finally:
        if driver:
            driver.quit()

    # Small delay to be respectful to the server
    time.sleep(0.5)

def main():
    """Main function to start the crawl."""
    start_url = "https://www.rbo.org.uk/"
    visited_urls = set()
    broken_links = set()
    
    # Configure concurrency parameters
    max_workers = 5  # Reduced for Selenium to avoid overwhelming the system
    max_depth = 3     # Maximum crawl depth
    
    # Clear the output file if it exists
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    
    print(f"Starting crawl with {max_workers} concurrent workers and max depth of {max_depth}")
    print(f"Only crawling URLs from rbo.org.uk domain")
    print(f"Ignoring mailto links")
    print(f"Using Selenium to handle React-rendered content")
    print(f"Broken links will be written to {OUTPUT_FILE}")
    
    # Start the crawl
    crawl_url(start_url, visited_urls, broken_links, max_workers=max_workers, max_depth=max_depth)

    print("\n--- Crawl Summary ---")
    print(f"Total URLs crawled: {len(visited_urls)}")
    print(f"Total broken links found: {len(broken_links)}")
    print(f"Broken links have been written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main() 