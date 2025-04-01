import os
import sys
import time
import atexit
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pymongo.mongo_client import MongoClient
import logging
import re
from typing import TypedDict

# Lock file to prevent multiple instances
LOCK_FILE = "/tmp/scraper.lock"

def remove_lock_file():
    """Ensure lock file is removed on exit."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# Register cleanup function
atexit.register(remove_lock_file)

try:
    lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(lock_fd, "w") as f:
        f.write(str(os.getpid()))
except FileExistsError:
    print("Scraper is already running. Exiting...")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO)

# Environment variables and defaults
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://user:pass@mongodb:27017/?directConnection=true')
EMBED_SERVICE_URL = os.environ.get('EMBED_SERVICE_URL', 'http://vector-embed:8000/embed')
START_URLS = [
    "https://www.flaw.uniba.sk/mapa-stranky/",
    "https://www.flaw.uniba.sk/en/sitemap/"
]
DOMAIN = urlparse(START_URLS[0]).netloc  # Restrict crawling to this domain

# MongoDB setup
try:
    client = MongoClient(MONGO_URI)
    db = client["cms_db"]
    collection = db["cms_docs"]
except Exception as e:
    logging.error("❌ Failed to connect to MongoDB: %s", e)
    sys.exit(1)

def chunk_text(text, chunk_size=500, stride=150):
    words = text.split()
    return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), stride) if words[i:i+chunk_size]]

class ScrapedData(TypedDict):
    title: str
    content: str
    language: str
    url: str
    chunk_id: str
    category_id: str

def scrape_page(url: str) -> list[ScrapedData] | None:
    """Scrapes the page for content and extracts additional links."""
    logging.info("Scraping: %s", url)
    language = "en" if "/en/" in url else "sk"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
    except requests.RequestException as e:
        logging.error("Request failed for %s: %s", url, e)
        return None

    # Extract category from breadcrumbs
    category_id = None
    breadcrumbs = soup.find("div", class_="breadcrumb")
    if breadcrumbs and soup.title:
        breadcrumb_links = breadcrumbs.find_all("a")[:3]
        category_name = " > ".join(link.get_text(strip=True) for link in breadcrumb_links) if breadcrumb_links else soup.title.string
        category_url = f'{DOMAIN}{breadcrumb_links[-1]["href"]}' if breadcrumb_links else url
        category = {"name": category_name, "url": category_url}
        
        db["categories"].update_one({"name": category["name"]}, {"$set": category}, upsert=True)
        category_doc = db["categories"].find_one({"name": category["name"]}, {"_id": 1})
        if category_doc:
            category_id = str(category_doc["_id"])

    # Extract main article and sidebar content
    article_text = " ".join(el.get_text(" ", strip=True) for el in soup.find_all("article"))
    aside_text = " ".join(el.get_text(" ", strip=True) for el in soup.find_all("aside"))
    content = f"{article_text} {aside_text}".strip()
    
    if not content:
        logging.warning("No content extracted from %s", url)
        return None

    content = re.sub(r'\s+', ' ', content).strip()
    chunks = chunk_text(content)

    return [{
        "title": soup.title.string if soup.title else "Untitled",
        "content": chunk,
        "language": language,
        "url": url,
        "chunk_id": f"{url}#{i}",
        "category_id": category_id
    } for i, chunk in enumerate(chunks)]

def update_document(chunks):
    """Upserts content chunks into MongoDB."""
    for chunk in chunks:
        collection.update_one({"chunk_id": chunk["chunk_id"]}, {"$set": chunk}, upsert=True)
        logging.info("Updated document chunk for %s", chunk["chunk_id"])

def update_embedding(document, retries=3, delay=2):
    """Fetches embeddings for the document and updates MongoDB."""
    payload = {"text": document["content"]}

    for attempt in range(retries):
        try:
            response = requests.post(EMBED_SERVICE_URL, json=payload, timeout=10)
            response.raise_for_status()
            embedding = response.json().get("embedding")

            if embedding:
                collection.update_one({"chunk_id": document["chunk_id"]}, {"$set": {"embedding": embedding}})
                logging.info("✅ Embedding updated for %s", document["url"])
                return
            
            logging.warning("Embedding service returned no data. Attempt %d/%d", attempt + 1, retries)
        except requests.RequestException as e:
            logging.error("Embedding service call failed for %s: %s (attempt %d/%d)", document["url"], e, attempt + 1, retries)
        
        time.sleep(delay)

def extract_links(url: str) -> list[str]:
    """Extracts relevant links from a given page."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
    except requests.RequestException as e:
        logging.error("❌ Failed to fetch page %s: %s", url, e)
        return []

    links = [a["href"] for a in soup.select("ul.nav li:not(.back) a") if a.get("href")]
    return [urljoin(url, link) for link in links if is_valid_link(link)]

def is_valid_link(link: str) -> bool:
    """Checks if the link should be followed."""
    exclude_patterns = ["/pics/", "/fileadmin/", "/uploads/", "/mapa-stranky/", "/rss/", "/sitemap/", "/mapa/", "/map/"]
    return urlparse(link).netloc == DOMAIN and not any(pattern in link for pattern in exclude_patterns)

def crawl(urls: list[str], visited: set[str], depth: int, max_depth: int):
    """Recursively scrapes pages and extracts additional links."""
    if depth > max_depth:
        return

    next_urls = set()
    
    for url in urls:
        if url in visited:
            continue

        visited.add(url)
        logging.info("🔍 Crawling URL: %s (depth: %s)", url, depth)

        # Scrape page content
        data_chunks = scrape_page(url)
        if data_chunks:
            update_document(data_chunks)
            for doc in data_chunks:
                update_embedding(doc)

        # Extract new links
        next_urls.update(extract_links(url))

    # Recursively crawl the next set of links
    if next_urls:
        time.sleep(2)  # Avoid excessive requests
        crawl(list(next_urls), visited, depth + 1, max_depth)

def main():
    try:
        logging.info("Scraper is starting...")
        visited = set()
        max_depth = 5

        # Extract initial links from the sitemap
        initial_links = []
        for start_url in START_URLS:
            initial_links.extend(extract_links(start_url))

        # Start recursive crawling from extracted links
        crawl(initial_links, visited, 1, max_depth)
    finally:
        remove_lock_file()

if __name__ == "__main__":
    main()
