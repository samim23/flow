# app/uploader.py

from ftplib import FTP
from pathlib import Path
import hashlib
from typing import List, Tuple
import pickle
import shutil
import os
import logging


logger = logging.getLogger(__name__)

class FTPUploader:
    def __init__(self, settings):
        self.settings = settings
        # Use proper build path from settings
        self.build_dir = Path(settings.local_build_path)
        self.upload_dir = Path(settings.local_upload_path)
        self.cache_dir = Path("cache")
        self.cache_file = self.cache_dir / "filecache.pickle"
        self.cache_dir.mkdir(exist_ok=True)
        self.file_cache = self._load_cache()
        # logger.debug(f"FTP Uploader initialized with build_dir: {self.build_dir}, upload_dir: {self.upload_dir}")

    def _load_cache(self) -> dict:
        """Load file cache from disk"""
        if self.cache_file.exists():
            with open(self.cache_file, "rb") as f:
                return pickle.load(f)
        return {}

    def _save_cache(self):
        """Save file cache to disk"""
        with open(self.cache_file, "wb") as f:
            pickle.dump(self.file_cache, f)

    def _get_file_hash(self, path: Path) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_changed_files(self, local_dir: Path) -> Tuple[List[Path], List[Path]]:
        """Get list of changed files and directories"""
        changed_files = []
        changed_dirs = []

        for path in local_dir.rglob("*"):
            if path.is_file():
                try:
                    file_hash = self._get_file_hash(path)
                    if str(path) not in self.file_cache or self.file_cache[str(path)] != file_hash:
                        changed_files.append(path)
                        self.file_cache[str(path)] = file_hash
                        logger.debug(f"Found changed file: {path}")
                except Exception as e:
                    logger.error(f"Error hashing file {path}: {e}")
            elif path.is_dir():
                if str(path) not in self.file_cache:
                    changed_dirs.append(path)
                    self.file_cache[str(path)] = "dir"
                    logger.debug(f"Found new directory: {path}")

        return changed_files, changed_dirs

    async def upload_site(self, local_dir: Path = None):
        """Upload changed files to FTP server with clean progress output"""
        if not self.settings.server_ftp_enabled:
            logger.info("FTP upload disabled in settings")
            return

        local_dir = local_dir or self.build_dir
        logger.info(f"Starting FTP upload from {local_dir}")
        
        changed_files, changed_dirs = self._get_changed_files(local_dir)
        total_files = len(changed_files)
        uploaded_files = 0
        
        if total_files == 0:
            logger.info("No files need uploading")
            return
            
        logger.info(f"Found {total_files} files to upload")
        
        MAX_RETRIES = 3
        TIMEOUT = 120  # 2 minute timeout
        CHUNK_SIZE = 8192  # 8KB chunks

        def connect_ftp():
            """Create new FTP connection"""
            ftp = FTP(
                self.settings.server_ftp_server,
                self.settings.server_ftp_username,
                self.settings.server_ftp_password,
                timeout=TIMEOUT
            )
            # Disable debug output
            ftp.set_debuglevel(0)
            return ftp

        try:
            ftp = connect_ftp()
            
            # Create directories
            if changed_dirs:
                total_dirs = len(changed_dirs)
                logger.info(f"Creating {total_dirs} directories...")
                for i, dir_path in enumerate(changed_dirs, 1):
                    remote_path = self.settings.server_ftp_path / dir_path.relative_to(local_dir)
                    for attempt in range(MAX_RETRIES):
                        try:
                            logger.info(f"[{i}/{total_dirs}] Creating directory: {remote_path}")
                            ftp.mkd(str(remote_path))
                            break
                        except Exception as e:
                            if "exists" in str(e).lower():
                                logger.info(f"[{i}/{total_dirs}] Directory exists: {remote_path}")
                                break
                            if attempt == MAX_RETRIES - 1:
                                logger.debug(f"[{i}/{total_dirs}] Failed to create directory {remote_path}")
                                break
                            ftp.close()
                            ftp = connect_ftp()

            # Upload files
            logger.info("Starting file uploads...")
            for file_path in changed_files:
                remote_path = self.settings.server_ftp_path / file_path.relative_to(local_dir)
                file_size = os.path.getsize(file_path)
                
                # Show current file being processed
                logger.info(f"[{uploaded_files + 1}/{total_files}] Uploading: {remote_path}")
                
                for attempt in range(MAX_RETRIES):
                    try:
                        with open(file_path, "rb") as f:
                            # Try to delete existing file quietly
                            try:
                                ftp.delete(str(remote_path))
                            except:
                                pass

                            # Upload with minimal progress output
                            bytes_sent = 0
                            def callback(block):
                                nonlocal bytes_sent
                                bytes_sent += len(block)
                                # Only log every 25% progress
                                # if bytes_sent % (file_size // 4) < CHUNK_SIZE:
                                #     percent = (bytes_sent / file_size) * 100
                                #     logger.debug(f"Progress: {percent:.0f}%")

                            ftp.storbinary(f"STOR {remote_path}", f, 
                                        blocksize=CHUNK_SIZE, 
                                        callback=callback)
                            
                            uploaded_files += 1
                            # Show percentage complete every 10% of total files
                            # if uploaded_files % max(1, total_files // 10) == 0:
                            #     percent_complete = (uploaded_files / total_files) * 100
                            #     logger.info(f"Overall progress: {percent_complete:.1f}% ({uploaded_files}/{total_files})")
                            break
                            
                    except Exception as e:
                        if attempt == MAX_RETRIES - 1:
                            logger.error(f"Failed to upload {file_path.name}")
                            raise
                        logger.warning(f"Retrying upload for {file_path.name} (attempt {attempt + 2}/{MAX_RETRIES})")
                        ftp.close()
                        ftp = connect_ftp()

            ftp.close()
            self._save_cache()
            logger.info(f"FTP upload completed successfully: {uploaded_files}/{total_files} files")
                
        except Exception as e:
            logger.error(f"FTP upload failed at {uploaded_files}/{total_files} files: {e}")
            if 'ftp' in locals():
                try:
                    ftp.close()
                except:
                    pass
            raise
    
    def delete_build_files(self, path: str, affected_tags: set = None):
        """Mark files for regeneration without deleting them"""
        # Create build directory reference
        build_path = self.build_dir

        if affected_tags:
            # Just remove from cache so they'll be regenerated
            for tag in affected_tags:
                cache_key = f"tag:{tag}"
                if cache_key in self.file_cache:
                    del self.file_cache[cache_key]
                
                # Remove archive cache entries
                archive_tag_prefix = f"tag_archives:{tag}"
                keys_to_remove = [k for k in self.file_cache if k.startswith(archive_tag_prefix)]
                for key in keys_to_remove:
                    del self.file_cache[key]

        # Remove cache entries for general site files
        general_files = [
            "index.html",
            "sitemap.xml",
            "rss.xml",
            "explore/index.html",
            f"p/{path}/index.html" if path else None
        ]
        
        for file_path in general_files:
            if file_path:
                cache_key = f"page.html:{file_path}"
                if cache_key in self.file_cache:
                    del self.file_cache[cache_key]
                
        # Clear archive cache entries
        archive_prefix = "archive:"
        keys_to_remove = [k for k in self.file_cache if k.startswith(archive_prefix)]
        for key in keys_to_remove:
            del self.file_cache[key]