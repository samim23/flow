# app/routes.py

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi import UploadFile, File
from werkzeug.utils import secure_filename
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import secrets
import random
import frontmatter
import logging
import ftplib
import json
import os
import hashlib
import hmac

from app.settings import settings
from app.utils import clean_content, extract_first_image, get_image_mime_type, Paginator, convert_to_webp

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Session cookie name
SESSION_COOKIE = "flow_session"

def create_session_token() -> str:
    """Create a signed session token"""
    token = secrets.token_hex(16)
    signature = hmac.new(
        settings.session_secret.encode(),
        token.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    return f"{token}.{signature}"

def verify_session_token(token: str) -> bool:
    """Verify a session token signature"""
    if not token or "." not in token:
        return False
    try:
        token_part, signature = token.rsplit(".", 1)
        expected_sig = hmac.new(
            settings.session_secret.encode(),
            token_part.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(signature, expected_sig)
    except Exception:
        return False

def is_authenticated(request: Request) -> bool:
    """Check if the current request has a valid session"""
    if not settings.admin_password:
        return True  # No password set = always authenticated (dev mode)
    session_token = request.cookies.get(SESSION_COOKIE)
    return verify_session_token(session_token)

def is_live_mode() -> bool:
    """Check if we're in live mode (password protection enabled)"""
    return bool(settings.admin_password)

def get_template_context(request: Request, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get common template context"""
    # Check for freeze parameter in query string
    freeze = request.query_params.get('freeze', '0')
    freeze = int(freeze) if freeze.isdigit() else 0
    
    # In live mode, force freeze=1 for unauthenticated users
    authenticated = is_authenticated(request)
    if is_live_mode() and not authenticated:
        freeze = 1
    
    base_context = {
        "request": request,
        "app": settings,
        "freeze": freeze,
        "is_authenticated": authenticated,
        "is_live_mode": is_live_mode()
    }
    if context:
        base_context.update(context)
    return base_context

# Login/Logout routes
@router.get("/login", name="login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login page"""
    # If not in live mode, redirect to home
    if not is_live_mode():
        return RedirectResponse(url="/", status_code=302)
    
    # If already authenticated, redirect to home
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    
    return request.app.state.templates.TemplateResponse(
        "login.html",
        {"request": request, "app": settings, "error": None}
    )

@router.post("/login", name="login_post")
async def login_submit(request: Request):
    """Handle login form submission"""
    if not is_live_mode():
        return RedirectResponse(url="/", status_code=302)
    
    form = await request.form()
    password = form.get("password", "")
    
    # Verify password
    if secrets.compare_digest(password, settings.admin_password):
        # Create session and redirect
        response = RedirectResponse(url="/", status_code=302)
        session_token = create_session_token()
        response.set_cookie(
            key=SESSION_COOKIE,
            value=session_token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7  # 7 days
        )
        return response
    else:
        # Invalid password
        return request.app.state.templates.TemplateResponse(
            "login.html",
            {"request": request, "app": settings, "error": "Invalid password"},
            status_code=401
        )

@router.get("/logout", name="logout")
async def logout(request: Request):
    """Log out and clear session"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response

# Main routes
@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page"""
    content_manager = request.app.state.content_manager
    pages = content_manager.get_pages_by_status("public")
    paginator = Paginator(pages, settings.site_scroll_amount)
    total_pages = paginator.total_pages - 1
    
    context = {
        "pageTitle": settings.site_name,
        "pages": paginator.get_page(total_pages),  # Get last page to show newest content
        "current_number": total_pages,  # Start from highest page number
        "total_num": total_pages
    }
    
    return request.app.state.templates.TemplateResponse(
        "index.html",
        get_template_context(request, context)
    )

@router.get("/p/{path:path}/", response_class=HTMLResponse)
async def page(request: Request, path: str):
    """Individual page"""
    content_manager = request.app.state.content_manager
    page = content_manager.get_page(path)
    
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    context = {
        "pageTitle": f"{page.metadata.title} - {settings.site_name}",
        "page": page
    }
    
    return request.app.state.templates.TemplateResponse(
        "page.html",
        get_template_context(request, context)
    )

@router.get("/archive/{num}.html", response_class=HTMLResponse)
async def archive(request: Request, num: str):
    """Archive pages"""
    try:
        num = int(num)
        content_manager = request.app.state.content_manager
        
        # Just get the pages - Paginator will handle sorting
        pages = content_manager.get_pages_by_status("public")
        paginator = Paginator(pages, settings.site_scroll_amount)
        
        context = {
            "pageTitle": settings.site_name,
            "pages": paginator.get_page(num),  # No need for page_number calculation
            "current_number": num,
            "total_num": paginator.total_pages - 1,
            "isArchive": True
        }
        
        return request.app.state.templates.TemplateResponse(
            "index.html",
            get_template_context(request, context)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid page number: {num}")

# Tag routes
@router.get("/tag/", name="tags", response_class=HTMLResponse)
async def tags(request: Request):
    """Tags overview page"""
    content_manager = request.app.state.content_manager
    pages = content_manager.get_pages_by_status("public")
    
    # Collect tag statistics
    tag_stats = {}
    for page in pages:
        if page.metadata.tags:
            for tag in page.metadata.tags:
                if tag in tag_stats:
                    tag_stats[tag] += 1
                else:
                    tag_stats[tag] = 1
    
    # Convert to sorted list of tuples
    tags_list = sorted(
        [(tag, count) for tag, count in tag_stats.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    context = {
        "pageTitle": f"{settings.site_name} - Tags",
        "tags": tags_list,
        "postamount": len(pages)
    }
    
    return request.app.state.templates.TemplateResponse(
        "tags.html",
        get_template_context(request, context)
    )

@router.get("/tag/{tag}/", response_class=HTMLResponse)
async def tag(request: Request, tag: str):
    """Individual tag page"""
    content_manager = request.app.state.content_manager
    # Just get the pages - Paginator will handle sorting
    pages = content_manager.get_pages_by_tag(tag)
    paginator = Paginator(pages, settings.site_scroll_amount)
    total_pages = paginator.total_pages - 1  # Convert to 0-based index
    
    context = {
        "pageTitle": f"{settings.site_name} - {tag}",
        "tag": tag,
        "freeze": 0,
        "pages": paginator.get_page(total_pages),  # Get the last page to show newest content
        "current_number": total_pages,  # Start from highest page number
        "total_num": total_pages
    }
    
    return request.app.state.templates.TemplateResponse(
        "tag.html",
        get_template_context(request, context)
    )
    
@router.get("/archive/tag/{tag}_{num}.html", response_class=HTMLResponse)
async def archive_tag(request: Request, tag: str, num: str):
    try:
        num = int(num)
        content_manager = request.app.state.content_manager
        pages = sorted(
            content_manager.get_pages_by_tag(tag),
            key=lambda p: p.metadata.date,
            reverse=True
        )
        paginator = Paginator(pages, settings.site_scroll_amount)
        
        context = {
            "pageTitle": f"{settings.site_name} - {tag}",
            "tag": tag,
            "pages": paginator.get_page(num),
            "current_number": num,
            "total_num": paginator.total_pages - 1
        }
        
        return request.app.state.templates.TemplateResponse(
            "tag.html",
            get_template_context(request, context)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid page number: {num}")

# Search routes
@router.get("/search/", name="search", response_class=HTMLResponse)
async def search(request: Request):
    """Search page"""
    query_raw = request.query_params.get('q', '')
    query = query_raw.lower()
    content_manager = request.app.state.content_manager
    
    if query:
        # Get all public pages and filter
        all_pages = content_manager.get_pages_by_status("public")
        pages = [
            page for page in all_pages 
            if query in page.content.lower() or 
               query in page.metadata.title.lower()
        ]
        # Sort by date descending (newest first) like other routes
        pages.sort(key=lambda p: p.metadata.date, reverse=True)
        
        total_results = len(pages)  # Store total BEFORE pagination
        
        paginator = Paginator(pages, settings.site_scroll_amount)
        total_pages = paginator.total_pages - 1  # Convert to 0-based index
        
        context = {
            "pageTitle": f"{settings.site_name} - Search",
            "query": query_raw,  # Preserve original case for display
            "total_results": total_results,  # Total matching results
            "pages": paginator.get_page(total_pages),  # Get last page to show newest first
            "current_number": total_pages,  # Start from highest page number
            "total_num": total_pages
        }
    else:
        context = {
            "pageTitle": f"{settings.site_name} - Search",
            "query": "",
            "total_results": 0,
            "pages": [],
            "current_number": 0,
            "total_num": 0
        }
    
    return request.app.state.templates.TemplateResponse(
        "search.html",
        get_template_context(request, context)
    )

@router.get("/archive/search/{num}", name="search_archive", response_class=HTMLResponse)
async def search_archive(request: Request, num: int):
    """Search archive pages"""
    query = request.query_params.get('q', '').lower()
    content_manager = request.app.state.content_manager
    
    if query:
        # Get all public pages and filter
        all_pages = content_manager.get_pages_by_status("public")
        pages = [
            page for page in all_pages 
            if query in page.content.lower() or 
               query in page.metadata.title.lower()
        ]
        # Sort by date descending (newest first)
        pages.sort(key=lambda p: p.metadata.date, reverse=True)
        
        paginator = Paginator(pages, settings.site_scroll_amount)
        total_pages = paginator.total_pages - 1
        
        # Ensure num is within valid range
        if num < 0 or num > total_pages:
            raise HTTPException(status_code=404, detail="Page not found")
            
        context = {
            "pageTitle": f"{settings.site_name} - Search Results",
            "query": query,
            "pages": paginator.get_page(num),
            "current_number": num,
            "total_num": total_pages
        }
    else:
        context = {
            "pageTitle": f"{settings.site_name} - Search Results", 
            "query": "",
            "pages": [],
            "current_number": 0,
            "total_num": 0
        }
    
    return request.app.state.templates.TemplateResponse(
        "search.html",
        get_template_context(request, context)
    )

@router.get("/api/related", name="api_related", response_class=HTMLResponse)
async def api_related(request: Request):
    """API endpoint for finding related posts based on keywords and tags.
    Returns rendered HTML fragments for the side panel.
    
    Query params:
    - q: search keywords (space-separated)
    - tags: comma-separated tag names
    - offset: pagination offset (default 0)
    - limit: number of results (default 15)
    """
    query = request.query_params.get('q', '').lower().strip()
    tags_param = request.query_params.get('tags', '').strip()
    offset = int(request.query_params.get('offset', 0))
    limit = int(request.query_params.get('limit', 15))
    
    content_manager = request.app.state.content_manager
    all_pages = content_manager.get_pages_by_status("public")
    
    # Score each page based on keyword and tag matches
    scored_pages = []
    keywords = [k.strip() for k in query.split() if k.strip() and len(k.strip()) > 2]
    tags = [t.strip().lower() for t in tags_param.split(',') if t.strip()]
    
    for page in all_pages:
        score = 0
        
        # Tag matches (high weight)
        if tags and page.metadata.tags:
            page_tags = [t.lower() for t in page.metadata.tags]
            for tag in tags:
                if tag in page_tags:
                    score += 10  # Strong signal
        
        # Keyword matches in content and title
        content_lower = page.content.lower()
        title_lower = page.metadata.title.lower()
        
        for keyword in keywords:
            if keyword in title_lower:
                score += 5  # Title match is strong
            if keyword in content_lower:
                score += 2  # Content match
        
        # Boost recent posts slightly (within last 30 days)
        if page.metadata.date:
            days_old = (datetime.now() - page.metadata.date).days
            if days_old < 30:
                score += 1
        
        if score > 0:
            scored_pages.append((score, page))
    
    # Sort by score descending, then by date descending
    scored_pages.sort(key=lambda x: (-x[0], -x[1].metadata.date.timestamp() if x[1].metadata.date else 0))
    
    # Apply pagination
    pages = [p for (_, p) in scored_pages[offset:offset + limit]]
    has_more = len(scored_pages) > offset + limit
    total_results = len(scored_pages)
    
    # Render the posts using a partial template
    context = {
        "pages": pages,
        "has_more": has_more,
        "total_results": total_results,
        "next_offset": offset + limit,
    }
    
    return request.app.state.templates.TemplateResponse(
        "_related_posts.html",
        get_template_context(request, context)
    )

@router.post("/post")
async def post(request: Request):
    # Require authentication in live mode
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    form = await request.form()
    path = form['path']
    text = form['text']
    unique = form.get('unique', 'false')

    content_manager = request.app.state.content_manager
    
    # Extract frontmatter and content from text
    try:
        post = frontmatter.loads(text)
        metadata = post.metadata
        content = post.content

        affected_tags = set(post.metadata.get('tags', []))
    
        # If updating existing post, get its old tags too
        if path in request.app.state.content_manager.pages:
            old_tags = set(request.app.state.content_manager.pages[path].metadata.tags or [])
            affected_tags.update(old_tags)

    except Exception as e:
        logger.error(f"Error parsing frontmatter: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid frontmatter")

    try:
        # Make filename unique if required
        if unique == 'true':
            # Check if file exists
            while content_manager.get_page(path):
                # Add random suffix
                random_chars = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
                path = f"{path}-{random_chars}"

        # Save the page
        content_manager.save_page(path, content, metadata)

        # Clean up affected files
        request.app.state.ftp_uploader.delete_build_files(path, affected_tags)
        
        return {"status": "OK", "path": path}
    except Exception as e:
        logger.error(f"Error saving page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# RSS feed route
@router.get("/rss.xml", name="feedrss")
async def feedrss(request: Request):
    """Generate RSS feed"""
    content_manager = request.app.state.content_manager
    latest = sorted(
        content_manager.get_pages_by_status("public"),
        reverse=True,
        key=lambda p: p.metadata.date
    )[:settings.site_feed_amount]

    # Create wrappers that include site_url for RSS template
    def clean_content_with_url(html: str) -> str:
        return clean_content(html, settings.site_url)
    
    def get_first_image(html: str) -> str:
        return extract_first_image(html, settings.site_url)
    
    context = {
        "cleanContent": clean_content_with_url,
        "getFirstImage": get_first_image,
        "getImageMimeType": get_image_mime_type,
        "pages": latest,
        "local_timezone": "+0100",
        "pubdate": datetime.now()
    }

    xml = request.app.state.templates.TemplateResponse(
        "xml.html",
        get_template_context(request, context)
    )
    return Response(content=xml.body.decode(), media_type="application/xml")


@router.get("/sitemap.xml", response_class=HTMLResponse)
async def sitemap(request: Request):
    """Generate sitemap XML"""
    content_manager = request.app.state.content_manager
    latest = sorted(
        content_manager.get_pages_by_status("public"),
        reverse=True,
        key=lambda p: p.metadata.date or datetime(1970, 1, 1)  # Handle missing dates
    )
    datenow = datetime.now()

    context = {
        "pages": latest,
        "datenow": datenow,
        "freeze": 0,
        "app": request.app.state.settings  # Ensure `settings` is initialized in app.state
    }

    return request.app.state.templates.TemplateResponse(
        "sitemap.html",
        {"request": request, **context},
        media_type="application/xml"
    )


# Site publishing

def write_to_log(text: str):
    """Write to log file"""
    try:
        log_dir = Path("app/static")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / "log.json"
        log_file.write_text(text)
    except Exception as e:
        logger.error(f"Error writing to log: {str(e)}")

@router.post("/publish")
async def publish_site(request: Request, background_tasks: BackgroundTasks):
    """Generate static site and upload to FTP"""
    # Require authentication in live mode
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    logger.info("Starting site publication")
    write_to_log(json.dumps({"status": "publishing", "text": "Generating Site"}))
    
    async def generate_and_upload():
        try:
            # Generate the site
            await request.app.state.static_generator.generate_site()
            
            # Upload the site using configured method
            if settings.upload_method == "rsync" and settings.rsync_host:
                # Use rsync (faster)
                await request.app.state.rsync_uploader.upload_site(Path("build"))
            elif settings.server_ftp_enabled:
                # Fallback to FTP
                await request.app.state.ftp_uploader.upload_site(Path("build"))
            
            # Write success message to the log file
            write_to_log(json.dumps({"status": "done", "text": "Publishing done!"}))
            
        except Exception as e:
            logger.error(f"Error publishing site: {str(e)}")
            write_to_log(json.dumps({"status": "error", "text": str(e)}))
    
    # Add the background task
    background_tasks.add_task(generate_and_upload)
    
    return {"status": "success", "message": "Site generation and upload started in the background"}

@router.get("/publishing-status")
async def get_publishing_status():
    """Get the current publishing status from the log file"""
    try:
        # Use consistent path with write_to_log
        log_file = Path("app/static/log.json")
        if log_file.exists():
            return json.loads(log_file.read_text())
        return {"status": "idle", "text": "No publishing in progress"}
    except Exception as e:
        logger.error(f"Error reading publishing status: {e}")
        return {"status": "error", "text": str(e)}

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = set(settings.allowed_extensions)
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    """Handle file uploads with automatic WebP conversion for images"""
    # Require authentication in live mode
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Validate file
        if not file or not allowed_file(file.filename):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Sanitize filename
        filename = secure_filename(file.filename)
        
        # Read file content
        content = await file.read()
        
        # Convert images to WebP (except animated GIFs)
        # This reduces file size by ~40-60% with quality 90
        original_ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        if original_ext in {'png', 'jpg', 'jpeg', 'gif'}:
            content, filename = convert_to_webp(content, filename, quality=90)
            logger.info(f"Converted image to WebP: {filename}")
        
        # Make filename unique if needed
        file_path = Path(settings.local_upload_path) / filename
        if file_path.exists():
            random_chars = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
            name, ext = os.path.splitext(filename)
            filename = f"{name}-{random_chars}{ext}"
            file_path = Path(settings.local_upload_path) / filename

        # Ensure upload directory exists
        Path(settings.local_upload_path).mkdir(parents=True, exist_ok=True)
        
        # Save file locally
        file_path.write_bytes(content)
        file_size = file_path.stat().st_size
        
        # Get site path prefix for URL construction
        site_path_prefix = settings.site_path_prefix.rstrip('/')
        if site_path_prefix and not site_path_prefix.startswith('/'):
            site_path_prefix = '/' + site_path_prefix
            
        # Construct URL based on whether site is in a subdirectory
        file_url = f"{site_path_prefix}/upload/{filename}"

        # Upload to FTP if enabled
        if settings.server_ftp_enabled:
            with ftplib.FTP(settings.server_ftp_server, 
                           settings.server_ftp_username,
                           settings.server_ftp_password) as session:
                ftp_path = settings.server_ftp_media_path + filename
                with open(file_path, 'rb') as f:
                    session.storbinary(f'STOR {ftp_path}', f)
                file_url = settings.server_ftp_media_site_path + filename
                logger.info(f"Uploaded to FTP: {file_url}")

        return {
            "files": [{
                "name": filename,
                "size": file_size,
                "url": file_url,
                "thumbnail": ""
            }]
        }

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/delete")
async def delete(request: Request):
    # Require authentication in live mode
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    form = await request.form()
    path = form['path']
    content_manager = request.app.state.content_manager
    file_path = content_manager.content_dir / f"{path}.md"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.unlink()  # Permanently delete the file
        if path in content_manager.pages:
            del content_manager.pages[path]  # Remove from memory
        return {"status": "OK", "path": str(file_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


@router.get("/api/tags", name="api_tags")
async def api_tags(request: Request):
    """Get all tags with their counts for autocomplete"""
    content_manager = request.app.state.content_manager
    pages = content_manager.get_pages_by_status("public")
    
    # Collect tag statistics
    tag_stats = {}
    for page in pages:
        if page.metadata.tags:
            for tag in page.metadata.tags:
                tag_stats[tag] = tag_stats.get(tag, 0) + 1
    
    # Convert to sorted list (most used first)
    tags_list = sorted(
        [{"name": tag, "count": count} for tag, count in tag_stats.items()],
        key=lambda x: x["count"],
        reverse=True
    )
    
    return tags_list


@router.get("/explore/", response_class=HTMLResponse)
async def explore(request: Request):
    content_manager = request.app.state.content_manager
    sorted_pages = sorted(
        content_manager.get_pages_by_status("public"),
        key=lambda p: p.date or datetime(1970, 1, 1)  # Handle missing dates gracefully
    )

    final_stat = {'dates': [], 'posts': [], 'postsamount': []}
    final_pages = []
    post_amount = 0

    for i, page in enumerate(sorted_pages):
        date = page.date or datetime(1970, 1, 1)  # Fallback for missing dates
        current_date = date.strftime("%Y-%m-%d")
        final_pages.append(page.path)
        post_amount += 1

        if i + 1 < len(sorted_pages):
            next_date = sorted_pages[i + 1].date or datetime(1970, 1, 1)
            next_date_str = next_date.strftime("%Y-%m-%d")

            if current_date != next_date_str:
                final_stat['dates'].append(current_date)
                final_stat['postsamount'].append(post_amount)
                final_stat['posts'].append(final_pages)
                post_amount = 0
                final_pages = []
        else:
            # Handle the last page in the sorted list
            final_stat['dates'].append(current_date)
            final_stat['postsamount'].append(post_amount)
            final_stat['posts'].append(final_pages)

    # logger.debug(f"Final statistics for /explore/: {final_stat}")

    context = {
        "stats": final_stat,
        "pageTitle": f"{settings.site_name} - Explore",
    }

    return request.app.state.templates.TemplateResponse(
        "explore.html",
        get_template_context(request, context)
    )
