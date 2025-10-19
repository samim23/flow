# app/content.py

from pathlib import Path
import frontmatter
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, validator
import logging
import hashlib
import asyncio
import time
import markdown2
import re  # Add regex for pattern matching
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import queue
import signal
import sys
import os

logger = logging.getLogger(__name__)

# Helper function to preprocess Markdown content
def preprocess_markdown(content: str) -> str:
    """
    Preprocess Markdown content to ensure certain syntax works correctly.
    This function handles both math expressions and emphasis formatting.
    """
    # First, process math expressions to fix *{A} syntax
    # Find all math expressions (both inline and display)
    math_pattern = r'\\(?:\[|\().*?\\(?:\)|\])'
    
    def fix_math_expression(match):
        math_expr = match.group(0)
        # Replace *{A} with {A} within math expressions
        math_expr = re.sub(r'\*{([^}]+)}', r'{\1}', math_expr)
        return math_expr
    
    # Apply the fix to all math expressions
    content = re.sub(math_pattern, fix_math_expression, content)
    
    # No need to convert _text_ to *text* for italics anymore
    # The markdown2 "code-friendly" extra will handle this by disabling underscore emphasis
    
    # Pattern for __double word__ with underscores (bold)
    double_underscore_pattern = r'(?<!\w)__([^\s_](?:[^_]*[^\s_])?)__(?!\w)'
    
    # Replace __word__ with **word** for bold (where appropriate)
    content = re.sub(double_underscore_pattern, r'**\1**', content)
    
    return content

class PageMetadata(BaseModel):
    title: str
    date: datetime
    status: str = "public"
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    author_name: Optional[str] = None
    icon: Optional[str] = None
    link: Optional[str] = "/"
    render_as_markdown: bool = False
    custom_css_class: Optional[str] = None

    @validator("date", pre=True, always=True)
    def validate_date(cls, value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(f"Invalid date format: {value}")

class Page(BaseModel):
    metadata: PageMetadata
    content: str
    path: str
    html: Optional[str] = None

    @property
    def meta(self) -> PageMetadata:
        """Compatibility property for accessing metadata"""
        return self.metadata

    def __getattr__(self, item):
        """Delegate attribute access to metadata if the attribute is not found"""
        if hasattr(self.metadata, item):
            return getattr(self.metadata, item)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")


    @classmethod
    def from_file(cls, file_path: Path) -> "Page":
        """Create a Page object from a markdown file with frontmatter"""
        # logger.debug(f"Loading file: {file_path}")
        try:
            post = frontmatter.load(file_path)
            # logger.debug(f"Metadata loaded: {post.metadata}")
            metadata = PageMetadata(**post.metadata)

            processed_html: str
            if metadata.render_as_markdown:
                # Preprocess Markdown content to ensure underscores for emphasis work correctly
                preprocessed_content = preprocess_markdown(post.content)
                
                # Parse content as Markdown
                # Configure markdown2 with specific extras for proper handling of Markdown syntax
                md_parser = markdown2.Markdown(
                    extras=[
                        "fenced-code-blocks", 
                        "tables",
                        "markdown-in-html",  # Process Markdown inside HTML
                        "break-on-newline",  # Better handling of line breaks
                        "smarty-pants",      # Smart typography for quotes, dashes, etc.
                        "code-friendly",     # Disable underscore-based emphasis (_text_)
                    ]
                )
                
                # Process the content
                processed_html = md_parser.convert(preprocessed_content)
            else:
                # Treat content as raw HTML
                processed_html = post.content
            
            return cls(
                metadata=metadata,
                content=post.content,
                path=file_path.stem,
                html=processed_html
            )
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise

class ContentFileHandler(FileSystemEventHandler):
    """Handles filesystem events for content files"""
    def __init__(self, callback_queue: queue.Queue):
        self.callback_queue = callback_queue
        self.file_hashes: Dict[str, str] = {}
        self._last_mtimes: Dict[str, float] = {}
        
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file content efficiently"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                # Read in chunks to avoid loading entire file into memory
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file {file_path}: {e}")
            return ""
    
    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed (markdown files only)"""
        return file_path.suffix.lower() == '.md' and file_path.exists()
    
    def _process_file_change(self, file_path: Path, event_type: str):
        """Process a file change event"""
        if not self._should_process_file(file_path):
            return
            
        str_path = str(file_path)
        try:
            if event_type == 'deleted':
                # Handle deleted files
                if str_path in self.file_hashes:
                    del self.file_hashes[str_path]
                    del self._last_mtimes[str_path]
                    self.callback_queue.put(('deleted', str_path))
            else:
                # Handle created/modified files
                current_mtime = file_path.stat().st_mtime
                last_mtime = self._last_mtimes.get(str_path, 0)
                
                # Only process if mtime changed
                if current_mtime != last_mtime:
                    current_hash = self._get_file_hash(file_path)
                    last_hash = self.file_hashes.get(str_path)
                    
                    # Only process if hash changed (content actually changed)
                    if current_hash != last_hash:
                        self.file_hashes[str_path] = current_hash
                        self._last_mtimes[str_path] = current_mtime
                        self.callback_queue.put(('changed', str_path))
                    else:
                        # Update mtime even if hash didn't change
                        self._last_mtimes[str_path] = current_mtime
                        
        except Exception as e:
            logger.error(f"Error processing file change for {file_path}: {e}")
    
    def on_modified(self, event):
        if not event.is_directory:
            self._process_file_change(Path(event.src_path), 'modified')
    
    def on_created(self, event):
        if not event.is_directory:
            self._process_file_change(Path(event.src_path), 'created')
    
    def on_deleted(self, event):
        if not event.is_directory:
            self._process_file_change(Path(event.src_path), 'deleted')
    
    def on_moved(self, event):
        if not event.is_directory:
            # Handle as deletion of old path and creation of new path
            self._process_file_change(Path(event.src_path), 'deleted')
            self._process_file_change(Path(event.dest_path), 'created')

class FileMonitor:
    """Handles file system monitoring for content files using watchdog"""
    def __init__(self, content_dir: Path, batch_size: int = 1000):
        self.content_dir = content_dir
        self.batch_size = batch_size
        self.is_monitoring = False
        self.observer = None
        self.event_handler = None
        self.callback_queue = queue.Queue()
        self.callback = None
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.stop()
            # Force exit if graceful shutdown takes too long
            import threading
            def force_exit():
                import time
                time.sleep(3)
                logger.warning("Force exiting due to hanging shutdown...")
                os._exit(1)
            
            threading.Thread(target=force_exit, daemon=True).start()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _initialize_file_cache(self):
        """Initialize file cache with current file states"""
        logger.info("Initializing file cache...")
        file_count = 0
        for file_path in self.content_dir.glob("**/*.md"):
            try:
                str_path = str(file_path)
                mtime = file_path.stat().st_mtime
                self.event_handler._last_mtimes[str_path] = mtime
                # Don't compute hash during initialization - only when files change
                file_count += 1
            except Exception as e:
                logger.error(f"Error initializing cache for {file_path}: {e}")
        
        logger.info(f"Initialized cache for {file_count} files")

    async def start(self, callback, check_interval: float = 5.0):
        """Start monitoring using watchdog filesystem events"""
        self.is_monitoring = True
        self.callback = callback
        
        # Create event handler
        self.event_handler = ContentFileHandler(self.callback_queue)
        
        # Initialize file cache
        self._initialize_file_cache()
        
        # Create observer
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.content_dir), recursive=True)
        # Make observer thread non-daemon so it can be properly stopped
        self.observer.daemon = False
        
        # Start observer
        self.observer.start()
        logger.info(f"Started watchdog file monitoring for {self.content_dir}")
        
        # Process events from queue
        while self.is_monitoring:
            try:
                # Wait for events with timeout
                try:
                    event_type, file_path = self.callback_queue.get(timeout=1.0)
                    changed_files = {file_path}
                    
                    if event_type == 'deleted':
                        logger.info(f"File deleted: {file_path}")
                    else:
                        logger.info(f"File changed: {file_path}")
                    
                    await callback(changed_files)
                    
                except queue.Empty:
                    # No events, continue
                    continue
                    
            except Exception as e:
                logger.error(f"Error processing file events: {e}")
                await asyncio.sleep(1.0)

    def stop(self):
        """Stop monitoring content files"""
        self.is_monitoring = False
        if self.observer:
            self.observer.stop()
            # Wait for observer to stop with timeout to avoid hanging
            try:
                self.observer.join(timeout=2.0)  # Wait max 2 seconds
            except:
                pass  # Ignore any errors during shutdown
            logger.info("Stopped watchdog file monitoring")


class ContentManager:
    def __init__(self, content_dir: str = "content"):
        self.content_dir = Path(content_dir)
        if not self.content_dir.exists():
            logger.error(f"Content directory does not exist: {self.content_dir}")
            raise FileNotFoundError(f"Content directory not found: {self.content_dir}")
        
        self.pages: Dict[str, Page] = {}
        self.monitor = FileMonitor(self.content_dir)
        self.load_all_pages()

    async def _handle_file_changes(self, changed_files: Set[str]):
        """Handle file system changes detected by monitor"""
        for file_path in changed_files:
            path = Path(file_path)
            try:
                if path.exists():
                    # Update/add file
                    page = Page.from_file(path)
                    self.pages[page.path] = page
                else:
                    # Remove file
                    page_path = path.stem
                    if page_path in self.pages:
                        del self.pages[page_path]
            except Exception as e:
                logger.error(f"Error handling change in {file_path}: {e}")

    async def start_monitoring(self, check_interval: float = 5.0):
        """Start the file monitor"""
        await self.monitor.start(self._handle_file_changes, check_interval)

    def stop_monitoring(self):
        """Stop the file monitor"""
        self.monitor.stop()

    def load_all_pages(self):
        """Load all markdown files from content directory"""
        markdown_files = list(self.content_dir.glob("**/*.md"))
        logger.info(f"Found {len(markdown_files)} files")
        
        for file_path in markdown_files:
            try:
                page = Page.from_file(file_path)
                self.pages[page.path] = page
                # Note: Hash initialization is now handled by ContentFileHandler during monitoring
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {str(e)}")

    def get_page(self, path: str) -> Optional[Page]:
        """Get a specific page by path"""
        return self.pages.get(path)

    def get_pages_by_status(self, status: str, username: Optional[str] = None) -> List[Page]:
        """Get all pages with a specific status"""
        pages = []
        for page in self.pages.values():
            if page.metadata.status != status:
                continue
            if username and page.metadata.author != username:
                continue
            pages.append(page)
        return sorted(pages, key=lambda p: p.metadata.date, reverse=True)

    def get_pages_by_tag(self, tag: str) -> List[Page]:
        """Get all pages with a specific tag"""
        pages = []
        for page in self.get_pages_by_status("public"):
            if page.metadata.tags and tag in page.metadata.tags:
                pages.append(page)
        return sorted(pages, key=lambda p: p.metadata.date, reverse=True)

    def save_page(self, path: str, content: str, metadata: Dict[str, Any]):
        """Save a new page or update an existing one"""
        file_path = self.content_dir / f"{path}.md"

        # Manually format YAML metadata to enforce quotes
        metadata_yaml = "---\n"
        for key, value in metadata.items():
            if key == "title":  # Ensure the title is quoted
                metadata_yaml += f'{key}: "{value}"\n'
            else:
                # For other fields, let YAML handle them naturally
                metadata_yaml += f"{key}: {value}\n"
        metadata_yaml += "---\n"

        # Combine metadata and content
        markdown = f"{metadata_yaml}\n{content}"

        # Save the file
        file_path.write_text(markdown)

        # Reload the saved page
        self.pages[path] = Page.from_file(file_path)
