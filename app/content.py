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

logger = logging.getLogger(__name__)

class PageMetadata(BaseModel):
    title: str
    date: datetime
    status: str = "public"
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    author_name: Optional[str] = None
    icon: Optional[str] = None
    link: Optional[str] = "/"

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
            return cls(
                metadata=metadata,
                content=post.content,
                path=file_path.stem,
                html=post.content
            )
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise

class FileMonitor:
    """Handles file system monitoring for content files"""
    def __init__(self, content_dir: Path, batch_size: int = 1000):
        self.content_dir = content_dir
        self.batch_size = batch_size
        self.file_hashes: Dict[str, str] = {}
        self._last_mtimes: Dict[str, float] = {}
        self._dir_mtimes: Dict[str, float] = {}
        self.is_monitoring = False

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file content"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _get_directory_mtime(self, dir_path: Path) -> float:
        """Get the latest modification time of a directory and its immediate children"""
        try:
            dir_mtime = dir_path.stat().st_mtime
            return max(
                dir_mtime,
                max((p.stat().st_mtime for p in dir_path.iterdir()), default=dir_mtime)
            )
        except Exception as e:
            logger.error(f"Error getting directory mtime: {e}")
            return 0

    def check_for_changes(self) -> Set[str]:
        """Check for changes using directory-level monitoring and batch processing"""
        changed_files = set()
        try:
            # First check directory-level changes
            current_dir_mtimes = {}
            dirs_to_check = set()
            
            # Check main content directory first
            main_dir_mtime = self._get_directory_mtime(self.content_dir)
            if main_dir_mtime != self._dir_mtimes.get(str(self.content_dir), 0):
                dirs_to_check.add(self.content_dir)
            current_dir_mtimes[str(self.content_dir)] = main_dir_mtime

            # Check subdirectories
            for dir_path in self.content_dir.glob("**/"):
                dir_str = str(dir_path)
                current_mtime = self._get_directory_mtime(dir_path)
                current_dir_mtimes[dir_str] = current_mtime
                
                if current_mtime != self._dir_mtimes.get(dir_str, 0):
                    dirs_to_check.add(dir_path)

            # Only process directories that have changed
            if dirs_to_check:
                # Get all current files in changed directories
                current_files = set()
                for dir_path in dirs_to_check:
                    current_files.update(dir_path.glob("*.md"))
                
                # Process files in batches
                for i in range(0, len(current_files), self.batch_size):
                    batch = list(current_files)[i:i + self.batch_size]
                    for file_path in batch:
                        str_path = str(file_path)
                        try:
                            mtime = file_path.stat().st_mtime
                            
                            if mtime != self._last_mtimes.get(str_path, 0):
                                current_hash = self._get_file_hash(file_path)
                                
                                if current_hash != self.file_hashes.get(str_path):
                                    changed_files.add(str_path)
                                    self.file_hashes[str_path] = current_hash
                                
                                self._last_mtimes[str_path] = mtime
                        
                        except FileNotFoundError:
                            # Handle deleted files
                            if str_path in self.file_hashes:
                                changed_files.add(str_path)
                                del self.file_hashes[str_path]
                                del self._last_mtimes[str_path]

            # Update directory mtimes
            self._dir_mtimes = current_dir_mtimes

        except Exception as e:
            logger.error(f"Error during file monitoring: {str(e)}")
        
        return changed_files

    async def start(self, callback, check_interval: float = 5.0):
        """Start monitoring with adaptive intervals based on scale"""
        self.is_monitoring = True
        
        # Adjust interval based on content size
        file_count = len(list(self.content_dir.glob("**/*.md")))
        if file_count > 10000:
            check_interval = max(check_interval, 10.0)
        elif file_count > 5000:
            check_interval = max(check_interval, 7.0)
        
        # logger.info(f"Starting file monitor with {check_interval}s interval for {file_count} files")
        
        error_count = 0
        while self.is_monitoring:
            try:
                changed_files = self.check_for_changes()
                if changed_files:
                    # logger.info(f"Detected changes in {len(changed_files)} files")
                    await callback(changed_files)
                error_count = 0
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error during file monitoring (attempt {error_count}): {str(e)}")
                await asyncio.sleep(min(check_interval * (2 ** error_count), 60.0))
                continue

            await asyncio.sleep(check_interval)

    def stop(self):
        """Stop monitoring content files"""
        self.is_monitoring = False


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
                # Initialize monitor's hash
                self.monitor.file_hashes[str(file_path)] = self.monitor._get_file_hash(file_path)
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
