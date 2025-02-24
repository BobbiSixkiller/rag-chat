# recursive_scraper.py
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pymongo import MongoClient
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Environment variables and defaults
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://mongodb:27017')
EMBED_SERVICE_URL = os.environ.get('EMBED_SERVICE_URL', 'http://vector-embed:8000/embed')
START_URL = os.environ.get('START_URL', 'https://flaw.uniba.sk')
DOMAIN = urlparse(START_URL).netloc  # restrict crawling to this domain

# MongoDB client and collection
client = MongoClient(MONGO_URI)
db = client["cms_db"]
collection = db["cms_documents"]

def scrape_page(url):
    """
    Scrapes headers, paragraphs, and alt texts from an HTML page.
    If the URL is a PDF, skip embedding and just record the URL.
    Returns a dict with title, content, language, and the URL.
    """
    if url.lower().endswith(".pdf"):
        logging.info("Skipping PDF for embedding: %s", url)
        # Instead of extracting PDF text, just create a minimal record.
        title = os.path.basename(url)
        content = f"PDF file available at: {url}"
        language = "sk"  # Adjust as needed
        return {"title": title, "content": content, "language": language, "url": url}

    try:
        response = requests.get(url, timeout=10)
    except Exception as e:
        logging.error("Request failed for %s: %s", url, e)
        return None

    if response.status_code != 200:
        logging.error("Failed to fetch %s (status code: %s)", url, response.status_code)
        return None

    soup = BeautifulSoup(response.content, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"

    headers = [header.get_text(strip=True) for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    image_alts = [img.get("alt") for img in soup.find_all("img") if img.get("alt")]

    content = "\n".join(headers + paragraphs + image_alts)
    language = "sk"  # Adjust as needed

    return {"title": title, "content": content, "language": language, "url": url}

def update_document(data):
    """
    Upserts a document in MongoDB based on its URL.
    """
    collection.update_one({"url": data["url"]}, {"$set": data}, upsert=True)
    logging.info("Updated document for %s", data["url"])
    return collection.find_one({"url": data["url"]})

def update_embedding(document):
    """
    Calls the embed service to compute embeddings and updates the MongoDB document.
    """
    payload = {"text": document["content"]}
    try:
        response = requests.post(EMBED_SERVICE_URL, json=payload, timeout=10)
    except Exception as e:
        logging.error("Embedding service call failed for %s: %s", document["url"], e)
        return

    if response.status_code != 200:
        logging.error("Embedding service returned error for %s: %s", document["url"], response.text)
        return

    embedding = response.json().get("embedding")
    collection.update_one({"url": document["url"]}, {"$set": {"embedding": embedding}})
    logging.info("Embedding updated for %s", document["url"])

def crawl(url, visited, depth, max_depth):
    """
    Recursively crawls pages starting from 'url', following only links within the target domain.
    Uses a visited set to avoid re-crawling and limits recursion by max_depth.
    """
    if depth > max_depth:
        return
    if url in visited:
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

    # Parse the page again for links to follow
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
    except Exception as e:
        logging.error("Failed to re-fetch page for link extraction %s: %s", url, e)
        return

    links = soup.find_all("a", href=True)
    for link in links:
        href = link["href"]
        next_url = urljoin(url, href)
        # Only follow links within the same domain
        if urlparse(next_url).netloc == DOMAIN:
            time.sleep(1)  # Delay between requests to avoid overloading the CMS
            crawl(next_url, visited, depth + 1, max_depth)

def main():
    visited = set()
    max_depth = 5  # Adjust the recursion depth as needed
    crawl(START_URL, visited, 0, max_depth)

if __name__ == "__main__":
    main()
