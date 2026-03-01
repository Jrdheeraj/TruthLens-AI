from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import os
from app.api.verify import router as verify_router

app = FastAPI(
    title="TruthLens AI",
    description="Multimodal Fake News & Misinformation Detection",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"CRITICAL ERROR: {exc}")
    traceback.print_exc()
    show_traceback = os.getenv("DEBUG_TRACEBACK", "").lower() in {"1", "true", "yes"}
    content = {"detail": "Internal server error"}
    if show_traceback:
        content["traceback"] = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content=content,
    )

app.include_router(verify_router, prefix="/api")

@app.get("/")
def health():
    return {
        "status": "OK",
        "service": "TruthLens AI Backend"
    }
