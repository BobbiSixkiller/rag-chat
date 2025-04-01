from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import os
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://chat:3000"],  # You can restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],  # Or specify methods like ["GET", "POST"]
    allow_headers=["*"],  # Or specify headers like ["Content-Type"]
)


# Load embedding model
model = SentenceTransformer('sentence-transformers/LaBSE')

# MongoDB Connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://user:pass@mongodb:27017/?directConnection=true')
client = MongoClient(MONGO_URI)
db = client["cms_db"]
collection = db["cms_docs"]

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
        # Generate the embedding for the query
        embedding = model.encode(query).tolist()
        
        # Perform vector search with language filtering
        results = collection.aggregate([
            {
                "$vectorSearch": {
                    "queryVector": embedding,
                    "path": "embedding",
                    "numCandidates": 1000,
                    "limit": limit,
                    "index": "cmsVector",  # Ensure this matches your MongoDB index name
                    "filter": {"language": language}  # Filter results by language
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "id": { "$toString": "$_id"},
                    "title": 1,
                    "content":1,
                    "url": 1,
                    "language": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }, 
            # {
            #     "$match": { "score": { "$gt": 0.8 } }
            # }
        ])

        # # Build a prompt for the Ollama model using the query and the search results
        # prompt = f"Query: {query}\nLanguage: {language}\n\nDocuments:\n"
        # if results:
        #     for doc in results:
        #         title = doc.get("title", "No title")
        #         content = doc.get("content", "No content")
        #         prompt += f"- {title} ({content})\n"
        # else:
        #     prompt += "No documents found.\n"
        # prompt += "\nUsing the above documents, generate a concise and helpful response to user query in provided language."

        # # Call the Ollama API to generate a response
        # ollama_url = "http://ollama:11434/api/generate"
        # ollama_payload = {"prompt": prompt, "model": "llama3"}
        # ollama_resp = requests.post(ollama_url, json=ollama_payload, stream=True)
        
        # if ollama_resp.status_code != 200:
        #     raise HTTPException(status_code=ollama_resp.status_code, detail="Ollama API error")
        
        # # Stream the response from Ollama to the client
        # def generate_stream():
        #     # Stream each chunk as it comes
        #     for chunk in ollama_resp.iter_content(chunk_size=1024):
        #         yield chunk  # Yield each chunk of data
            
        #     # End the response stream
        #     yield b''

        # # Return the streaming response
        # return StreamingResponse(generate_stream(), media_type="text/plain")

        return list(results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
