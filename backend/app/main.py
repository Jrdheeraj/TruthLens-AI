from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import os
import logging
import uuid
from app.api.verify import router as verify_router

# Setup logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# ============================================================================
# PART 4: STARTUP VALIDATION - Check critical dependencies
# ============================================================================

def validate_dependencies():
    """Validate critical dependencies at startup"""
    dependency_status = {
        "numpy": False,
        "cv2": False,
        "mediapipe": False,
        "torch": False,
        "timm": False
    }
    
    try:
        import numpy
        dependency_status["numpy"] = True
        logger.info(f"✓ NumPy {numpy.__version__} available")
    except ImportError as e:
        logger.warning(f"⚠️ NumPy not available: {e}")
    
    try:
        import cv2
        dependency_status["cv2"] = True
        logger.info(f"✓ OpenCV {cv2.__version__} available")
    except ImportError as e:
        logger.warning(f"⚠️ OpenCV not available: {e}")
    
    try:
        import mediapipe
        dependency_status["mediapipe"] = True
        logger.info(f"✓ MediaPipe available")
    except ImportError as e:
        logger.warning(f"⚠️ MediaPipe not available: {e}")
    
    try:
        import torch
        dependency_status["torch"] = True
        logger.info(f"✓ PyTorch {torch.__version__} available")
    except ImportError as e:
        logger.warning(f"⚠️ PyTorch not available: {e}")
    
    try:
        import timm
        dependency_status["timm"] = True
        logger.info(f"✓ timm available")
    except ImportError as e:
        logger.warning(f"⚠️ timm not available (will use heuristic deepfake detection): {e}")
    
    # Log summary
    available = sum(1 for v in dependency_status.values() if v)
    logger.info(f"Dependency Status: {available}/{len(dependency_status)} critical modules available")
    
    # System will continue with fallbacks if some deps missing
    if not dependency_status["cv2"]:
        logger.error("CRITICAL: OpenCV required - media analysis will fail")
    
    return dependency_status

# Run validation at module load
_dep_status = validate_dependencies()

app = FastAPI(
    title="TruthLens AI",
    description="Multimodal Fake News & Misinformation Detection",
    version="1.0.0"
)

# STARTUP EVENT - Log dependency status
@app.on_event("startup")
async def on_startup():
    logger.info("=" * 60)
    logger.info("TruthLens AI Starting Up")
    logger.info("=" * 60)
    logger.info(f"Dependency Status: {_dep_status}")
    if not _dep_status.get("cv2"):
        logger.error("CRITICAL: Media analysis will be degraded - OpenCV missing")
    if not _dep_status.get("torch") or not _dep_status.get("timm"):
        logger.warning("Deepfake detection using heuristics - neural model unavailable")
    logger.info("=" * 60)

# FIX 1: CORS - restrict to specific origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    max_age=3600,
)

# FIX 9: Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

# FIX 3: Debug traceback exposure - secure exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())
    
    # Log full traceback server-side only
    logger.error(
        f"Unhandled exception: {error_id}",
        exc_info=True,
        extra={
            "error_id": error_id,
            "endpoint": request.url.path,
            "method": request.method,
        }
    )
    
    # Return generic error to client - NEVER expose traceback
    content = {
        "detail": "Internal server error",
        "error_id": error_id,
    }
    
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
