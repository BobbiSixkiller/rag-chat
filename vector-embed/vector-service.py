from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI()
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

class TextPayload(BaseModel):
    text: str

@app.post("/embed")
async def embed_text(payload: TextPayload):
    try:
        embedding = model.encode(payload.text).tolist()
        return {"embedding": embedding}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/health")
def read_health():
    return {"status": "healthy"}
