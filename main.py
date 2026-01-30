from fastapi import FastAPI
from portal import router as portal_router

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(portal_router)
