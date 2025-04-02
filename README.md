# broken-link-tester
# Broken Link Tester
A tool to identify broken links on a website.

## Features
- Crawls a website to identify broken links
- Supports crawling with Selenium for JavaScript-heavy websites
- Supports crawling with requests for static websites
- Identifies links that are invalid, return a 400+ status code, or throw an error
- Outputs broken links to a file for easy review

## Usage
To use the broken link tester, simply run the script with the URL of the website you want to test as an argument. For example:
```
python crawler.py https://www.example.com/
```
This will start the crawl from the specified URL and identify broken links up to a maximum depth of 3.

## Configuration
The script can be configured by modifying the following variables at the top of the script:
- `MAX_RETRIES`: The maximum number of times to retry a request if it fails
- `INITIAL_TIMEOUT`: The initial timeout for requests
- `MIN_DELAY` and `MAX_DELAY`: The minimum and maximum delay between requests to avoid overwhelming the server
- `MAX_WORKERS`: The maximum number of concurrent requests to make
- `MAX_DEPTH`: The maximum depth to crawl from the starting URL

## Output
The script outputs broken links to a file named `broken_links.txt` or `broken_links_selenium.txt` depending on the crawler used. Each line in the file represents a broken link, including the origin URL and the broken link URL or error message.

## Requirements
- Python 3.x
- Selenium (for Selenium crawler)
- ChromeDriver (for Selenium crawler)
- requests
- BeautifulSoup
- urllib.parse
- threading
- concurrent.futures
- os
- datetime
- random
