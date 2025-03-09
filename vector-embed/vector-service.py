from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import os

app = FastAPI()

# Load embedding model
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# MongoDB Connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://user:pass@mongodb:27017/?directConnection=true')
client = MongoClient(MONGO_URI)
db = client["cms_db"]
collection = db["cms_documents"]

class TextPayload(BaseModel):
    text: str

@app.post("/embed")
async def embed_text(payload: TextPayload):
    """Generate embeddings for the given text."""
    try:
        embedding = model.encode(payload.text).tolist()
        return {"embedding": embedding}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def read_health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/search")
async def search_similar_documents(
    query: str = Query(..., description="Text query for vector search"),
    language: str = Query(..., description="Language filter (e.g., 'en' or 'sk')"),
    limit: int = 5
):
    """Search for the most similar documents using vector search with language filtering."""
    try:
        embedding = model.encode(query).tolist()
        
        # Perform vector search with language filtering
        results = collection.aggregate([
            {
                "$vectorSearch": {
                    "queryVector": embedding,
                    "path": "embedding",
                    "numCandidates": 100,
                    "limit": limit,
                    "index": "default",  # Ensure this matches your MongoDB index name
                    "filter": {"language": language}  # Filter results by language
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "title": 1,
                    "url": 1,
                    "language": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ])

        return {"results": list(results)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
