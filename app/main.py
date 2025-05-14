# app/main.py

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import logging
import asyncio
import re

from app.settings import settings
from app.routes import router
from app.content import ContentManager
from app.generator import StaticSiteGenerator
from app.uploader import FTPUploader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Determine root_path for FastAPI based on settings.site_path_prefix
# First, ensure it's a string and sanitize any Windows paths
raw_prefix = str(settings.site_path_prefix)
# Strip Windows path patterns
# 1. Drive letters with paths (C:/Program Files/Git/...)
sanitized_prefix = re.sub(r'^[A-Za-z]:[/\\].*?(?=/|$)', '', raw_prefix)
# 2. Git paths (/Git/...)
sanitized_prefix = re.sub(r'^/Git(/|$)', '/', sanitized_prefix)
# 3. Git without leading slash
sanitized_prefix = re.sub(r'^Git(/|$)', '/', sanitized_prefix)

# Then process normally
cleaned_prefix = sanitized_prefix.strip('/')
root_path_for_fastapi = ('/' + cleaned_prefix) if cleaned_prefix else ''

app = FastAPI(title=settings.site_name, root_path=root_path_for_fastapi)

# Make sure required directories exist
content_path = Path(settings.content_dir)
upload_path = Path(settings.local_upload_path)
build_path = Path(settings.local_build_path)
cache_path = Path("cache")

for path in [content_path, upload_path, build_path, cache_path]:
    if not path.exists():
        logger.warning(f"Directory not found at {path.absolute()}")
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory at {path.absolute()}")

# Initialize core components
content_manager = ContentManager(settings.content_dir)

@app.on_event("startup")
async def startup_event():
    """Start file monitoring on app startup"""
    # Start the file monitoring task
    asyncio.create_task(content_manager.start_monitoring())
    # logger.info("Started content file monitoring")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop file monitoring on app shutdown"""
    content_manager.stop_monitoring()
    # logger.info("Stopped content file monitoring")

static_generator = StaticSiteGenerator(
    "app/templates", 
    "build", 
    content_manager,
    settings=settings
)

ftp_uploader = FTPUploader(settings)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount upload files
upload_path = Path(settings.local_upload_path)
app.mount("/upload", StaticFiles(directory=upload_path), name="upload")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# Make core components available to routes
app.state.content_manager = content_manager
app.state.static_generator = static_generator
app.state.ftp_uploader = ftp_uploader
app.state.templates = templates
app.state.settings = settings

# Include routes
app.include_router(router)

# Register multiple exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions including 401 and 404"""
    if exc.status_code == 401:
        # Handle unauthorized access
        context = {
            "pageTitle": f"{settings.site_name} - Unauthorized",
            "app": settings,
            "freeze": 0,
            "error_message": "Please log in to access this feature"
        }
        return request.app.state.templates.TemplateResponse(
            "401.html",  # Create this template
            {"request": request, **context},
            status_code=401
        )
    elif exc.status_code == 404:
        # Handle not found
        context = {
            "pageTitle": f"{settings.site_name} - 404",
            "app": settings,
            "freeze": 0,
        }
        return request.app.state.templates.TemplateResponse(
            "404.html",
            {"request": request, **context},
            status_code=404
        )
    else:
        # Handle other HTTP errors
        context = {
            "pageTitle": f"{settings.site_name} - Error",
            "app": settings,
            "freeze": 0,
            "status_code": exc.status_code,
            "detail": exc.detail
        }
        return request.app.state.templates.TemplateResponse(
            "error.html",  # Create this template
            {"request": request, **context},
            status_code=exc.status_code
        )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    context = {
        "pageTitle": f"{settings.site_name} - Error",
        "app": settings,
        "freeze": 0,
        "error_message": "An unexpected error occurred"
    }
    return request.app.state.templates.TemplateResponse(
        "500.html",  # Create this template
        {"request": request, **context},
        status_code=500
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=settings.local_server_port,
        reload=settings.local_server_debug
    )