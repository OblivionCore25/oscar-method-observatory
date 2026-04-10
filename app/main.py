from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from app.api.reachability_router import router as reachability_router

app = FastAPI(
    title="OSCAR Method Observatory",
    description="Standalone Method Observatory for python packages",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(reachability_router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "method-observatory"}
