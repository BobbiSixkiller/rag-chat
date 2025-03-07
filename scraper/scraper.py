import os
import sys
import time
import atexit
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pymongo import MongoClient
import logging

LOCK_FILE = "/tmp/scraper.lock"

def remove_lock_file():
    """Ensure lock file is removed on exit."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# Register cleanup function
atexit.register(remove_lock_file)

# Atomically create the lock file to prevent race conditions
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
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://mongodb:27017')
EMBED_SERVICE_URL = os.environ.get('EMBED_SERVICE_URL', 'http://vector-embed:8000/embed')
START_URL = os.environ.get('START_URL', 'https://flaw.uniba.sk')
DOMAIN = urlparse(START_URL).netloc  # restrict crawling to this domain

# MongoDB client and collection with error handling and index setup
try:
    client = MongoClient(MONGO_URI)
    db = client["cms_db"]
    collection = db["cms_documents"]

    collection.create_index(
        [("embedding", "vector")],  # Define as a vector index
        name="embedding_vector_index",
        options={"dimension": 384, "similarity": "cosine"}  # Adjust `dimension` based on embeddings
    )
    print("✅ Embedding index ensured.")
except Exception as e:
    logging.error("Failed to connect to MongoDB: %s", e)
    sys.exit(1)  # Exit if MongoDB is not available

def scrape_page(url):
    """Scrapes headers, paragraphs, and alt texts from an HTML page."""
    language = "en" if "/en/" in url else "sk"

    if url.lower().endswith(".pdf"):
        logging.info("Skipping PDF for embedding: %s", url)
        title = os.path.basename(url)
        content = f"PDF file available at: {url}"
        return {"title": title, "content": content, "language": language, "url": url}

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise error for HTTP failures
    except requests.RequestException as e:
        logging.error("Request failed for %s: %s", url, e)
        return None

    soup = BeautifulSoup(response.content, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"

    headers = [header.get_text(strip=True) for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    image_alts = [img.get("alt") for img in soup.find_all("img") if img.get("alt")]

    content = "\n".join(headers + paragraphs + image_alts)

    return {"title": title, "content": content, "language": language, "url": url}

def update_document(data):
    """Upserts a document in MongoDB based on its URL."""
    collection.update_one({"url": data["url"]}, {"$set": data}, upsert=True)
    logging.info("Updated document for %s", data["url"])
    return collection.find_one({"url": data["url"]})

def update_embedding(document):
    """Calls the embed service to compute embeddings and updates the MongoDB document."""
    payload = {"text": document["content"]}
    try:
        response = requests.post(EMBED_SERVICE_URL, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error("Embedding service call failed for %s: %s", document["url"], e)
        return

    embedding = response.json().get("embedding")
    collection.update_one({"url": document["url"]}, {"$set": {"embedding": embedding}})
    logging.info("Embedding updated for %s", document["url"])

def crawl(url, visited, depth, max_depth):
    """Recursively crawls pages starting from 'url'."""
    if depth > max_depth or url in visited:
        return

    visited.add(url)
    logging.info("Crawling URL: %s (depth: %s)", url, depth)

    data = scrape_page(url)
    if data:
        doc = update_document(data)
        update_embedding(doc)
    else:
        logging.info("No data scraped from %s", url)
        return

    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
    except requests.RequestException as e:
        logging.error("Failed to re-fetch page for link extraction %s: %s", url, e)
        return

    links = soup.find_all("a", href=True)
    for link in links:
        next_url = urljoin(url, link["href"])
        if urlparse(next_url).netloc == DOMAIN:
            time.sleep(1)  # Prevent overloading CMS
            crawl(next_url, visited, depth + 1, max_depth)

def main():
    try:
        logging.info("Scraper is starting...")

        visited = set()
        max_depth = 5
        crawl(START_URL, visited, 0, max_depth)
    finally:
        remove_lock_file()

if __name__ == "__main__":
    main()
