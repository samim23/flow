# app/generator.py

import shutil
from pathlib import Path
import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import hashlib
from jinja2 import Environment, FileSystemLoader, FileSystemBytecodeCache
from typing import TYPE_CHECKING, Dict, Any, List, Set
import math
from datetime import datetime
from app.utils import clean_content, Paginator
import logging
import pickle
from dataclasses import dataclass, field
import time
import json

if TYPE_CHECKING:
    from .content import ContentManager, Page

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class BuildMetrics:
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = None
    total_pages: int = 0
    pages_generated: int = 0
    total_static_files: int = 0
    static_files_copied: int = 0
    stage_timings: Dict[str, float] = field(default_factory=dict)
    cached_files: int = 0
    errors: List[str] = field(default_factory=list)
    generated_files: Dict[str, List[str]] = field(default_factory=lambda: {
        "core_pages": [],
        "tag_pages": [],
        "tag_archives": [],
        "detail_pages": [],
        "static_files": []
    })
    
    def add_generated_file(self, category: str, filepath: str):
        """Track a generated file"""
        if category in self.generated_files:
            self.generated_files[category].append(filepath)
            self.increment_pages_generated()  # Increment when we track a file
    
    def increment_pages_generated(self, count: int = 1):
        """Increment the number of pages generated"""
        self.pages_generated += count

    def start_stage(self, stage_name: str) -> float:
        """Start timing a build stage"""
        return time.time()
    
    def end_stage(self, stage_name: str, start_time: float):
        """End timing a build stage"""
        duration = time.time() - start_time
        self.stage_timings[stage_name] = duration
        
    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append(error)
    
    def complete_build(self):
        """Mark build as complete"""
        self.end_time = datetime.now()
    
    def get_report(self) -> Dict:
        """Generate build report"""
        duration = (self.end_time or datetime.now()) - self.start_time
        return {
            "build_duration_seconds": duration.total_seconds(),
            "total_pages": self.total_pages,
            "pages_generated": self.pages_generated,
            "pages_cached": self.cached_files,
            "static_files": {
                "total": self.total_static_files,
                "copied": self.static_files_copied
            },
            "stage_timings": {
                stage: round(timing, 2)
                for stage, timing in self.stage_timings.items()
            },
            "generated_files": self.generated_files,
            "errors": self.errors
        }

    def save_report(self, path: str = "cache/build_report.json"):
        """Save build report to file"""
        report = self.get_report()
        with open(path, 'w') as f:
            json.dump(report, f, indent=2)
        return report

    def log_progress(self, message: str):
        """Log progress message with timing"""
        duration = (datetime.now() - self.start_time).total_seconds()
        print(f"[{duration:.1f}s] {message}")

    def estimate_remaining(self, completed: int, total: int) -> float:
        """Estimate remaining time based on progress"""
        if completed == 0:
            return 0
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return (elapsed / completed) * (total - completed)

class MockRequest:
    def __init__(self, settings):
        self.app = type('MockApp', (), {'state': type('MockState', (), {'settings': settings})()})
        self.base_url = settings.site_url.rstrip('/')  # Remove trailing slash if present

    def url_for(self, name: str, **params) -> str:
        """Mock url_for to generate static URLs"""
        # Handle static files
        if name == "static":
            path = params.get("path", "")
            return f"{self.base_url}/static/{path}"

        # Basic path mapping with base URL
        path_mapping = {
            'index': '/',
            'page': lambda params: f"/p/{params.get('path', '')}/",
            'tag': lambda params: f"/tag/{params.get('tag', '')}/",
            'archive': lambda params: f"/archive/{params.get('num', '0')}.html",
            'archive_tag': lambda params: f"/archive/tag/{params.get('tag', '')}_{params.get('num', '0')}.html",
            'feedrss': '/rss.xml',
            'sitemap': '/sitemap.xml',
            'tags': '/tag/',
            'explore': '/explore/'
        }

        # Handle dynamic paths
        if name in path_mapping:
            path = path_mapping[name]
            if callable(path):
                path = path(params)
            # Add base URL for absolute paths
            return f"{self.base_url}{path}"

        return self.base_url + '/'

class StaticSiteGenerator:
    def __init__(self, templates_dir: str, output_dir: str, content_manager: "ContentManager", settings=None):
        self.templates_dir = Path(settings.templates_dir) if settings else Path(templates_dir)
        self.output_dir = Path(settings.local_build_path) if settings else Path(output_dir)
        self.static_dir = Path(settings.static_dir) if settings else Path("app/static")
        self.content_manager = content_manager
        self.settings = settings

        # Initialize cache directories
        self.cache_dir = Path("cache")
        self.cache_templates_dir = self.cache_dir / "templates"
        self.cache_file = self.cache_dir / "filecache.pickle"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize template environment with caching
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            cache_size=1000,
            auto_reload=False,
            bytecode_cache=FileSystemBytecodeCache(directory=str(self.cache_templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        self.mock_request = MockRequest(settings) if settings else None
        self._template_cache = {}
        self._rendered_content = {}  # Cache for rendered content

        # Load file change cache (shared with FTP uploader)
        self.file_cache = self._load_cache()
        self.metrics = BuildMetrics()
    
    def _load_cache(self) -> dict:
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "rb") as f:
                    try:
                        cache = pickle.load(f)
                        return cache
                    except (pickle.PickleError, EOFError):
                        logger.warning("Cache file corrupted, starting fresh")
                        return {}
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
        return {}

    def _save_cache(self):
        """Save file cache"""
        try:
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.file_cache, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def clear_cache_selectively(self, clear_tags=False, clear_archives=False, clear_tag_archives=False, clear_posts=False):
        """Selectively clear parts of the cache to force regeneration of specific content types"""
        keys_to_remove = set()
        
        if clear_tags:
            # Clear main tag pages and tag index
            tag_keys = {k for k in self.file_cache if k.startswith('tag:')}
            tag_index_keys = {k for k in self.file_cache if 'tag/index.html' in k}
            keys_to_remove.update(tag_keys, tag_index_keys)
            logger.info(f"Clearing {len(tag_keys)} tag page cache entries")
            
        if clear_archives:
            # Clear main archive pages
            archive_keys = {k for k in self.file_cache if k.startswith('archive:') or '/archive/' in k}
            keys_to_remove.update(archive_keys)
            logger.info(f"Clearing {len(archive_keys)} archive page cache entries")
            
        if clear_tag_archives:
            # Clear tag archive pages
            tag_archive_keys = {k for k in self.file_cache if k.startswith('tag_archives:') or '/archive/tag/' in k}
            keys_to_remove.update(tag_archive_keys)
            logger.info(f"Clearing {len(tag_archive_keys)} tag archive cache entries")
            
        if clear_posts:
            # Clear individual post pages
            post_keys = {k for k in self.file_cache if k.startswith('build/p/')}
            keys_to_remove.update(post_keys)
            logger.info(f"Clearing {len(post_keys)} post page cache entries")
        
        # Remove the selected keys from cache
        for key in keys_to_remove:
            self.file_cache.pop(key, None)
        
        logger.info(f"Cleared {len(keys_to_remove)} total cache entries")
        self._save_cache()  # Save the updated cache
        
        return len(keys_to_remove)

    def _get_file_hash(self, path: Path) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @lru_cache(maxsize=1000)
    def _get_template(self, template_name: str):
        """Get template with caching"""
        return self.env.get_template(template_name)

    def log_memory_usage(self):
        """Log current memory usage"""
        import psutil
        process = psutil.Process()
        mem = process.memory_info().rss / 1024 / 1024  # Convert to MB
        self.metrics.log_progress(f"Memory usage: {mem:.1f}MB")

    def _datetime_handler(self, x):
        """Handle datetime serialization for JSON"""
        if isinstance(x, datetime):
            return x.isoformat()
        raise TypeError(f"Object of type {type(x)} is not JSON serializable")
        
    def get_template_context(self, additional_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get base template context"""
        context = {
            "request": self.mock_request,
            "app": self.settings,
            "freeze": 1
        }
        
        if additional_context:
            processed = {}
            for key, value in additional_context.items():
                if key == "page":
                    processed[key] = value
                elif key == "pages":
                    if isinstance(value, list):
                        processed[key] = value
                    else:
                        processed[key] = list(value)
                    
                    per_page = self.settings.site_scroll_amount
                    total_pages = math.ceil(len(processed[key]) / per_page)
                    processed.update({
                        "current_number": additional_context.get("current_number", 0),
                        "total_num": max(0, total_pages - 1),
                        "per_page": per_page
                    })
                else:
                    processed[key] = value
                    
            context.update(processed)
            
        return context

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render template with caching"""
        template = self._get_template(template_name)
        return template.render(**context)

    async def write_file(self, path: Path, content: str):
        """Write file asynchronously"""
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content)

    async def generate_page(self, template_name: str, output_path: Path, context: Dict[str, Any]):
        """Generate a single page with caching"""
        try:
            cache_key = f"{template_name}:{output_path}"
            
            # Check if content has changed
            content_hash = hashlib.md5(str(context).encode()).hexdigest()
            if cache_key in self.file_cache and self.file_cache[cache_key] == content_hash:
                self.metrics.cached_files += 1
                return
            
            stage_start = self.metrics.start_stage(f"page_{template_name}")
            template_context = self.get_template_context(context)
            output = await asyncio.to_thread(self.render_template, template_name, template_context)
            await self.write_file(output_path, output)
            
            # Update cache
            self.file_cache[cache_key] = content_hash
            self.metrics.end_stage(f"page_{template_name}", stage_start)
            
        except Exception as e:
            error_msg = f"Error generating page {output_path}: {e}"
            self.metrics.add_error(error_msg)
            logger.error(error_msg)
            raise

    async def _copy_static_files(self):
        """Copy static files in parallel with improved caching."""
        static_files_copied = []
        try:
            if not self.static_dir.exists():
                return static_files_copied

            stage_start = self.metrics.start_stage("static_files")
            static_files = []
            for src_path in self.static_dir.rglob("*"):
                if src_path.is_file():
                    self.metrics.total_static_files += 1
                    rel_path = src_path.relative_to(self.static_dir)
                    dst_path = self.output_dir / "static" / rel_path
                    
                    file_hash = self._get_file_hash(src_path)
                    cache_key = f"static:{rel_path}"
                    # Skip if file content hasn't changed
                    if cache_key in self.file_cache and self.file_cache[cache_key] == file_hash:
                        continue

                    static_files.append((src_path, dst_path))
                    self.file_cache[cache_key] = file_hash
                    static_files_copied.append(str(rel_path))
                    self.metrics.static_files_copied += 1

            if static_files:
                self.metrics.log_progress(f"Copying {len(static_files)} static files...")
                with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
                    await asyncio.get_event_loop().run_in_executor(
                        executor,
                        self._parallel_copy_files,
                        static_files
                    )
            
            self.metrics.end_stage("static_files", stage_start)
            return static_files_copied
        
        except Exception as e:
            error_msg = f"Error copying static files: {e}"
            self.metrics.add_error(error_msg)
            logger.error(error_msg)
            raise


    @staticmethod
    def _parallel_copy_files(files):
        """Copy files in parallel"""
        for src_path, dst_path in files:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)

    async def generate_detail_page(self, page: "Page"):
        """Generate detail page with caching and existence check."""
        try:
            output_dir = self.output_dir / "p" / page.path
            output_file = output_dir / "index.html"
            
            # Cache validation
            cache_key = f"page.html:p/{page.path}/index.html"
            content_hash = hashlib.md5(json.dumps({
                "path": page.path,
                "title": page.metadata.title,
                "content": page.content,
                "metadata": page.metadata.dict()
            }, sort_keys=True, default=self._datetime_handler).encode()).hexdigest()
            
            if cache_key in self.file_cache and self.file_cache[cache_key] == content_hash:
                if output_file.exists():  # File exists and matches cache
                    self.metrics.cached_files += 1
                    return

            # Generate page if cache invalid or file missing
            context = {
                "page": page,
                "pageTitle": f"{page.metadata.title} - {self.settings.site_name}"
            }
            await self.generate_page("page.html", output_file, context)

            # Update cache
            self.file_cache[cache_key] = content_hash
            self.metrics.pages_generated += 1
            
        except Exception as e:
            logger.error(f"Error generating detail page for {page.path}: {e}")
            raise


    def _get_tag_cache_key(self, tag: str, page_number: int = None) -> str:
        """Generate cache key for tag pages"""
        if page_number is not None:
            return f"tag:{tag}:archive:{page_number}"
        return f"tag:{tag}:index"

    def _get_tag_content_hash(self, tag: str, pages: List["Page"]) -> str:
        """Generate stable content hash for tag pages"""
        try:
            # Create a stable representation of pages
            page_data = []
            for page in sorted(pages, key=lambda p: p.path):  # Sort for stability
                page_data.append({
                    'path': page.path,
                    'title': page.metadata.title,
                    'date': page.metadata.date.isoformat() if page.metadata.date else None,
                    'tags': sorted(page.metadata.tags) if page.metadata.tags else [],  # Sort tags
                    'status': page.metadata.status,
                })
            
            # Create stable content representation
            content = {
                'tag': tag,
                'page_count': len(pages),
                'pages': page_data,
                'site_scroll_amount': self.settings.site_scroll_amount,  # Include pagination settings
            }
            
            # Convert to stable string and hash
            content_str = json.dumps(content, sort_keys=True)
            return hashlib.md5(content_str.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating tag hash for {tag}: {e}")
            return None

    async def generate_tag_page(self, tag: str) -> bool:
        """Generate tag page with improved caching"""
        try:
            pages = list(self.content_manager.get_pages_by_tag(tag))
            if not pages:
                return False

            # Generate content hash
            content_hash = self._get_tag_content_hash(tag, pages)
            cache_key = f"tag:{tag}"
            tag_file = self.output_dir / "tag" / tag / "index.html"
            relative_path = f"tag/{tag}/index.html"

            # Check if regeneration is needed
            if (content_hash == self.file_cache.get(cache_key) and 
                tag_file.exists()):
                return False

            # Generate tag page
            paginator = Paginator(pages, self.settings.site_scroll_amount)
            total_pages = paginator.total_pages - 1  # Convert to 0-based index

            # Always show newest content first, so start from highest page number
            context = self.get_template_context({
                "tag": tag,
                "pages": list(paginator.get_page(total_pages)),
                "current_number": total_pages,
                "total_num": total_pages,
                "pageTitle": f"{self.settings.site_name} - {tag}"
            })

            await self.generate_page("tag.html", tag_file, context)
            
            # Only track if we actually generated
            self.metrics.add_generated_file("tag_pages", relative_path)
            
            # Update cache
            self.file_cache[cache_key] = content_hash
            return True

        except Exception as e:
            logger.error(f"Error generating tag page for {tag}: {e}")
            raise

    async def generate_tag_archives(self, tag: str) -> int:
        """Generate tag archive pages with improved caching"""
        try:
            pages = list(self.content_manager.get_pages_by_tag(tag))
            if not pages:
                return 0

            # Sort pages in reverse chronological order 
            pages.sort(key=lambda p: p.metadata.date, reverse=True)
            paginator = Paginator(pages, self.settings.site_scroll_amount)
            archive_dir = self.output_dir / "archive" / "tag"  # Changed from build_dir to output_dir

            # Create content hash from pages data
            content_hash = self._get_tag_content_hash(tag, pages)
            cache_key = f"tag_archives:{tag}"
            
            # Get previous state
            prev_hash = self.file_cache.get(cache_key)
            prev_pages = self.file_cache.get(f"{cache_key}:pages", [])

            if prev_hash == content_hash:
                return 0

            # Find changed pages
            changed_pages = []
            current_pages_data = [(p.path, p.metadata.date.isoformat()) for p in pages]
            
            for i, (path, date) in enumerate(current_pages_data):
                if i >= len(prev_pages) or path != prev_pages[i][0]:
                    changed_pages.append(i)

            # Calculate which archive pages need regeneration
            pages_to_regenerate = {i // self.settings.site_scroll_amount for i in changed_pages}
            
            if pages_to_regenerate:
                # Generate only affected archive pages
                archive_tasks = []
                for page_num in sorted(pages_to_regenerate):
                    if page_num >= paginator.total_pages:
                        continue
                        
                    archive_path = f"archive/tag/{tag}_{page_num}.html"
                    context = self.get_template_context({
                        "tag": tag,
                        "pages": list(paginator.get_page(page_num)),
                        "current_number": page_num,
                        "total_num": paginator.total_pages - 1,
                        "isArchive": True,
                        "pageTitle": f"{self.settings.site_name} - {tag} (Archive)"
                    })
                    
                    archive_tasks.append(
                        self.generate_page(
                            "tag.html", 
                            archive_dir / f"{tag}_{page_num}.html", 
                            context
                        )
                    )
                    self.metrics.add_generated_file("tag_archives", archive_path)

                await asyncio.gather(*archive_tasks)
                
                # Update cache with new state
                self.file_cache[cache_key] = content_hash
                self.file_cache[f"{cache_key}:pages"] = current_pages_data
                
                return len(archive_tasks)

            return 0

        except Exception as e:
            logger.error(f"Error generating tag archives for {tag}: {e}")
            raise

    async def generate_index(self):
        """Generate index page"""
        try:
            pages = list(self.content_manager.get_pages_by_status("public"))
            paginator = Paginator(pages, self.settings.site_scroll_amount)
            first_page = list(paginator.get_page(paginator.total_pages - 1))
            
            context = self.get_template_context({
                "pages": first_page,
                "current_number": paginator.total_pages - 1,
                "total_num": paginator.total_pages - 1,
                "freeze": 1,
                "pageTitle": self.settings.site_name
            })
            
            await self.generate_page("index.html", self.output_dir / "index.html", context)

        except Exception as e:
            logger.error(f"Error generating index: {e}")
            raise

    async def generate_archives(self):
        """Generate archives with smart chronological caching"""
        try:
            pages = list(self.content_manager.get_pages_by_status("public"))
            paginator = Paginator(pages, self.settings.site_scroll_amount)
            archive_dir = self.output_dir / "archive"

            # Create a unique hash for the entire archive content
            archive_content_hash = hashlib.md5(json.dumps({
                'total_pages': len(pages),
                'first_page_path': pages[0].path if pages else None,
                'last_page_path': pages[-1].path if pages else None,
            }, default=self._datetime_handler).encode()).hexdigest()

            # Unique cache key for archives
            archive_cache_key = "site_archives"

            # Check if archives need full regeneration
            if archive_cache_key in self.file_cache and self.file_cache[archive_cache_key] == archive_content_hash:
                # Check if all archive files exist
                if all((archive_dir / f"{page_num}.html").exists() for page_num in range(paginator.total_pages)):
                    self.metrics.log_progress("All archive pages up to date")
                    return

            # Determine which pages have actually changed
            pages_to_regenerate = set()
            for i, page in enumerate(reversed(pages)):  # Start from newest pages
                cache_key = f"page.html:p/{page.path}/index.html"
                content_hash = hashlib.md5(json.dumps({
                    "path": page.path,
                    "title": page.metadata.title,
                    "content": page.content,
                    "metadata": page.metadata.dict()
                }, sort_keys=True, default=self._datetime_handler).encode()).hexdigest()
                
                if cache_key not in self.file_cache or self.file_cache[cache_key] != content_hash:
                    # Determine which archive pages contain this page
                    affected_archive_pages = set(
                        range(
                            (len(pages) - i - 1) // self.settings.site_scroll_amount, 
                            paginator.total_pages
                        )
                    )
                    pages_to_regenerate.update(affected_archive_pages)

            # If no specific pages to regenerate, but some archive files are missing
            if not pages_to_regenerate:
                missing_archives = [
                    page_num for page_num in range(paginator.total_pages) 
                    if not (archive_dir / f"{page_num}.html").exists()
                ]
                pages_to_regenerate.update(missing_archives)

            # If still no pages to regenerate, return
            if not pages_to_regenerate:
                self.metrics.log_progress("All archive pages up to date")
                return

            # self.metrics.log_progress(f"Regenerating archive pages: {sorted(pages_to_regenerate)}")

            # Generate only affected archive pages in parallel
            archive_tasks = []
            for page_num in sorted(pages_to_regenerate):
                context = self.get_template_context({
                    "pages": list(paginator.get_page(page_num)),
                    "current_number": page_num,
                    "total_num": paginator.total_pages - 1,
                    "isArchive": True,
                    "pageTitle": f"{self.settings.site_name} - Archive {page_num + 1}"
                })
                
                archive_tasks.append(
                    self.generate_page(
                        "index.html",
                        archive_dir / f"{page_num}.html",
                        context
                    )
                )
            
            if archive_tasks:
                await asyncio.gather(*archive_tasks)
                
            # Update cache
            self.file_cache[archive_cache_key] = archive_content_hash

        except Exception as e:
            logger.error(f"Error generating archives: {e}")
            raise

    async def generate_rss(self):
        """Generate RSS feed"""
        try:
            # Get latest pages and ensure they're a list
            public_pages = list(self.content_manager.get_pages_by_status("public"))[:self.settings.site_feed_amount]
            
            context = self.get_template_context({
                "pages": public_pages,
                "pubdate": datetime.now(),
                "cleanContent": clean_content,
                "local_timezone": "+0100"
            })
            
            await self.generate_page(
                "xml.html", 
                self.output_dir / "rss.xml", 
                context
            )
            logger.debug("Generated RSS feed")
            
        except Exception as e:
            logger.error(f"Error generating RSS: {e}")
            raise

    async def generate_sitemap(self):
        """Generate sitemap"""
        try:
            # Get all public pages and ensure they're a list
            public_pages = list(self.content_manager.get_pages_by_status("public"))
            
            context = self.get_template_context({
                "pages": public_pages,
                "datenow": datetime.now()
            })
            
            await self.generate_page(
                "sitemap.html", 
                self.output_dir / "sitemap.xml", 
                context
            )
            logger.debug("Generated sitemap")
            
        except Exception as e:
            logger.error(f"Error generating sitemap: {e}")
            raise

    async def generate_explore(self):
        """Generate explore page"""
        try:
            # Get and sort pages
            sorted_pages = sorted(
                list(self.content_manager.get_pages_by_status("public")),
                key=lambda p: p.metadata.date or datetime(1970, 1, 1)
            )

            final_stat = {'dates': [], 'posts': [], 'postsamount': []}
            final_pages = []
            post_amount = 0

            for i, page in enumerate(sorted_pages):
                date = page.metadata.date or datetime(1970, 1, 1)
                current_date = date.strftime("%Y-%m-%d")
                final_pages.append(page.path)
                post_amount += 1

                if i + 1 < len(sorted_pages):
                    next_date = sorted_pages[i + 1].metadata.date or datetime(1970, 1, 1)
                    next_date_str = next_date.strftime("%Y-%m-%d")

                    if current_date != next_date_str:
                        final_stat['dates'].append(current_date)
                        final_stat['postsamount'].append(post_amount)
                        final_stat['posts'].append(list(final_pages))  # Convert to list
                        post_amount = 0
                        final_pages = []
                else:
                    final_stat['dates'].append(current_date)
                    final_stat['postsamount'].append(post_amount)
                    final_stat['posts'].append(list(final_pages))  # Convert to list

            context = self.get_template_context({
                "stats": final_stat,
                "pageTitle": f"{self.settings.site_name} - Explore"
            })

            await self.generate_page(
                "explore.html", 
                self.output_dir / "explore" / "index.html", 
                context
            )
            logger.debug("Generated explore page")
            
        except Exception as e:
            logger.error(f"Error generating explore page: {e}")
            raise

    async def generate_tags_overview(self):
        """Generate tags overview page"""
        try:
            # Get pages and ensure they're a list
            pages = list(self.content_manager.get_pages_by_status("public"))
            
            # Collect tag statistics
            tag_stats = {}
            for page in pages:
                if page.metadata.tags:
                    for tag in page.metadata.tags:
                        tag_stats[tag] = tag_stats.get(tag, 0) + 1
            
            # Convert to sorted list of tuples
            tags_list = sorted(
                [(tag, count) for tag, count in tag_stats.items()],
                key=lambda x: x[1],
                reverse=True
            )
            
            context = self.get_template_context({
                "tags": tags_list,
                "postamount": len(pages),
                "pageTitle": f"{self.settings.site_name} - Tags"
            })
            
            await self.generate_page(
                "tags.html", 
                self.output_dir / "tag" / "index.html", 
                context
            )
            logger.debug("Generated tags overview")
            
        except Exception as e:
            logger.error(f"Error generating tags overview: {e}")
            raise

    async def generate_site(self):
        """Generate complete static site with optimizations"""
        try:
            self.metrics = BuildMetrics()
            self.metrics.log_progress("Starting site generation...")
            self.log_memory_usage()

            # Create output directory
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Copy static files in parallel
            stage_start = self.metrics.start_stage("setup")
            static_files_copied = await self._copy_static_files()
            
            # Get public pages and tags
            public_pages = list(self.content_manager.get_pages_by_status("public"))
            self.metrics.total_pages = len(public_pages)
            
            all_tags = set()
            for page in public_pages:
                if page.metadata.tags:
                    all_tags.update(page.metadata.tags)
            self.metrics.end_stage("setup", stage_start)

            # Generate core pages in parallel
            self.metrics.log_progress("Generating core pages...")
            stage_start = self.metrics.start_stage("core_pages")
            core_tasks = [
                self.generate_index(),
                self.generate_rss(),
                self.generate_sitemap(),
                self.generate_tags_overview(),
                self.generate_explore(),
                self.generate_archives()
            ]
            await asyncio.gather(*core_tasks)
            
            # Track core pages that were actually generated
            self.metrics.add_generated_file("core_pages", "index.html")
            self.metrics.add_generated_file("core_pages", "rss.xml")
            self.metrics.add_generated_file("core_pages", "sitemap.xml")
            self.metrics.add_generated_file("core_pages", "tag/index.html")
            self.metrics.add_generated_file("core_pages", "explore/index.html")
            
            self.metrics.end_stage("core_pages", stage_start)

            # Generate detail pages in parallel chunks
            stage_start = self.metrics.start_stage("detail_pages")
            
            # Check which pages need to be generated
            pages_to_generate = []
            for page in public_pages:
                cache_key = f"page.html:p/{page.path}/index.html"
                content_hash = hashlib.md5(json.dumps({
                    "path": page.path,
                    "title": page.metadata.title,
                    "content": page.content,
                    "metadata": page.metadata.dict()
                }, sort_keys=True, default=self._datetime_handler).encode()).hexdigest()
                
                if cache_key not in self.file_cache or self.file_cache[cache_key] != content_hash:
                    pages_to_generate.append(page)

            if pages_to_generate:
                self.metrics.log_progress(f"Generating {len(pages_to_generate)} detail pages...")
                chunk_size = max(10, len(pages_to_generate) // (multiprocessing.cpu_count() * 2))
                
                for i in range(0, len(pages_to_generate), chunk_size):
                    chunk = pages_to_generate[i:i + chunk_size]
                    tasks = [self.generate_detail_page(page) for page in chunk]
                    await asyncio.gather(*tasks)
                    
                    # Track generated detail pages
                    for page in chunk:
                        self.metrics.add_generated_file("detail_pages", f"p/{page.path}")
            else:
                self.metrics.log_progress("All detail pages up to date")
            
            self.metrics.end_stage("detail_pages", stage_start)

            # Generate tag pages
            stage_start = self.metrics.start_stage("tag_pages")
            if all_tags:
                self.metrics.log_progress(f"Generating {len(all_tags)} tag pages...")
                
                # Generate tag pages (files are tracked inside generate_tag_page)
                index_tasks = [self.generate_tag_page(tag) for tag in all_tags]
                await asyncio.gather(*index_tasks)
                
                # Generate archives (files are tracked inside generate_tag_archives) 
                self.metrics.log_progress("Generating tag archive pages...")
                archive_tasks = [self.generate_tag_archives(tag) for tag in all_tags]
                await asyncio.gather(*archive_tasks)

            self.metrics.end_stage("tag_pages", stage_start)

            # Save cache and complete build
            self._save_cache()
            self.metrics.complete_build()
            report = self.metrics.save_report()
            
            # Log final statistics
            stats_message = (
                f"Site generation completed in {report['build_duration_seconds']:.1f}s\n"
                f"\nPages: {report['pages_generated']} generated, {report['pages_cached']} cached\n"
                f"Static files: {report['static_files']['copied']} copied, "
                f"{report['static_files']['total'] - report['static_files']['copied']} unchanged\n"
                f"\nGenerated Files:\n"
            )
            
            # Add generated file details to the stats message
            for category, files in self.metrics.generated_files.items():
                if files:
                    stats_message += f"\n{category.replace('_', ' ').title()} ({len(files)}):\n"
                    for file in files:
                        stats_message += f"  - {file}\n"
            
            self.metrics.log_progress(stats_message)
            
            self.log_memory_usage()
            logger.info("Site generation completed successfully")
            
        except Exception as e:
            error_msg = f"Error generating site: {e}"
            self.metrics.add_error(error_msg)
            logger.error(error_msg)
            raise