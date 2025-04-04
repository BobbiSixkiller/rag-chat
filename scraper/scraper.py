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
from typing import TypedDict, Optional

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
# MongoDB client and collection with error handling
try:
    client = MongoClient(MONGO_URI)
    db = client["cms_db"]
    content_collection = db["cms_docs"]
    
    search_index_def = {
        "name": "cmsVector",
        "definition": {
            "mappings": {
                "dynamic": True,
                "fields": {
                    "embedding": {
                        "type": "knnVector",
                        "dimensions": 768,  # Ensure this matches your embedding model
                        "similarity": "cosine"
                    },
                    "language": {
                        "type": "token"  # Use 'token' instead of 'string'
                    },
                    "category_id": {
                        "type": "string"  # Change from "ObjectId" to "string"
                    }
                }
            }
        }
    }
    # Ensure the collection exists by inserting a dummy document
    try:
        content_collection.insert_one({"_id": "dummy"})
        logging.info("✅ Dummy document inserted to create the collection.")
    except Exception as e:
        logging.error("❌ Failed to insert dummy document: %s", e)

    try:
        vectorIndex = content_collection.create_search_index(search_index_def)
        logging.info("✅ Vector search index created successfully: %s", vectorIndex)
    except Exception as e:
        logging.error("❌ Failed to create search index: %s", e)
    content_collection.delete_one({"_id": "dummy"})
    logging.info("🗑️ Dummy document removed after index creation.")
except Exception as e:
    logging.error("❌ Failed to set up MongoDB: %s", e)
    sys.exit(1)  # Exit if MongoDB is not available

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

def scrape_page(url: str) -> Optional[list[ScrapedData]]:
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
        # Construct the category name: breadcrumb texts followed by the page title
        breadcrumb_text = " > ".join(link.get_text(strip=True) for link in breadcrumb_links)
        
        category_name = f"{breadcrumb_text} > {soup.title.string}" if breadcrumb_text else soup.title.string        
        # category_url = f'{DOMAIN}{breadcrumb_links[-1]["href"]}' if breadcrumb_links else url
        category = {"name": category_name, "url": url}
        
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

    links = [urljoin(f'https://{DOMAIN}', a["href"]) for a in soup.select("ul.nav li:not(.back) a") if a.get("href")]

    logging.info("Extracted links %s", links)
    return [link for link in links if is_valid_link(link)]

def is_valid_link(link: str) -> bool:
    """Checks if the link should be followed."""
    exclude_patterns = ["/pics/", "/fileadmin/", "/uploads/", "/rss/", "/mapa/", "/map/", "/mapa-stranky/", "/site-map/"]
    valid = urlparse(link).netloc == DOMAIN and not any(pattern in link for pattern in exclude_patterns)
    if not valid:
        logging.info(f"Excluded link: {link}")
    return valid

def crawl(urls: list[str], visited: set[str], depth: int, max_depth: int):
    """Recursively scrapes pages and extracts additional links."""
    if depth > max_depth:
        return

    next_urls = set()
    logging.info(f"Current depth: {depth}, URLs to crawl: {len(urls)}")

    for url in urls:
        if url in visited:
            continue

        visited.add(url)
        logging.info(f"🔍 Crawling URL: {url} (depth: {depth})")

        # Scrape page content
        data_chunks = scrape_page(url)
        if data_chunks:
            update_document(data_chunks)
            for doc in data_chunks:
                update_embedding(doc)

        # Extract new links
        new_links = extract_links(url)
        next_urls.update(new_links)
        logging.info(f"Found {len(new_links)} new links from {url}")

    # Recursively crawl the next set of links
    if next_urls:
        logging.info(f"Going to next depth level: {depth + 1}")
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
            
        logging.info("Extracted links: %s", initial_links)


        # Start recursive crawling from extracted links
        crawl(initial_links, visited, 1, max_depth)
    finally:
        remove_lock_file()

if __name__ == "__main__":
    main()
