# app/uploader.py

import ftplib
import ssl
from pathlib import Path
import hashlib
from typing import List, Tuple
import os
import subprocess
import logging
from app.cache import get_cache


logger = logging.getLogger(__name__)


class RsyncUploader:
    """Upload site using rsync over SSH - much faster than FTP for incremental updates"""
    
    def __init__(self, settings):
        self.settings = settings
        self.build_dir = Path(settings.local_build_path)
    
    async def upload_site(self, local_dir: Path = None):
        """Upload site using rsync"""
        local_dir = local_dir or self.build_dir
        
        if not self.settings.rsync_host or not self.settings.rsync_user:
            logger.error("rsync_host and rsync_user must be configured in settings")
            raise ValueError("rsync settings not configured")
        
        if not self.settings.rsync_remote_path:
            logger.error("rsync_remote_path must be configured in settings")
            raise ValueError("rsync_remote_path not configured")
        
        # Build rsync command
        source = str(local_dir.resolve()) + "/"
        dest = f"{self.settings.rsync_user}@{self.settings.rsync_host}:{self.settings.rsync_remote_path}"
        
        cmd = [
            "rsync",
            "-avz",           # archive, verbose, compress
            "--progress",     # show progress
            "--stats",        # show summary stats
            "--exclude=static/upload/",  # NEVER delete uploaded media!
            "--exclude=static/upload",   # Both with and without trailing slash
        ]
        
        # Add delete flag if enabled (--delete-after ensures all uploads complete before any deletes)
        if self.settings.rsync_delete:
            cmd.append("--delete-after")
        
        # Add SSH key if specified
        if self.settings.rsync_ssh_key:
            ssh_key = os.path.expanduser(self.settings.rsync_ssh_key)
            cmd.extend(["-e", f"ssh -i {ssh_key}"])
        
        cmd.extend([source, dest])
        
        logger.info(f"Starting rsync upload to {dest}")
        logger.info(f"Command: {' '.join(cmd)}")
        
        try:
            # Run rsync with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output to logger
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"rsync: {line}")
            
            # Wait for completion
            return_code = process.wait()
            
            if return_code == 0:
                logger.info("rsync upload completed successfully")
            else:
                logger.error(f"rsync failed with return code {return_code}")
                raise RuntimeError(f"rsync failed with return code {return_code}")
                
        except FileNotFoundError:
            logger.error("rsync command not found. Please install rsync.")
            raise
        except Exception as e:
            logger.error(f"rsync upload failed: {e}")
            raise

class FTPUploader:
    def __init__(self, settings):
        self.settings = settings
        # Use proper build path from settings
        self.build_dir = Path(settings.local_build_path)
        self.upload_dir = Path(settings.local_upload_path)
        # Use shared SQLite cache
        self.cache = get_cache()
        # logger.debug(f"FTP Uploader initialized with build_dir: {self.build_dir}, upload_dir: {self.upload_dir}")

    def _save_cache(self):
        """No-op: SQLite cache auto-saves on each operation"""
        pass

    def _get_file_fingerprint(self, path: Path) -> str:
        """Fast fingerprint using mtime + size; falls back to MD5 only when those change."""
        stat = path.stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"

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
                    cache_key = str(path)
                    fingerprint = self._get_file_fingerprint(path)
                    cached = self.cache.get(cache_key)
                    # Fast path: mtime+size unchanged → file hasn't changed
                    if cached and cached.startswith(fingerprint + ":"):
                        continue
                    file_hash = self._get_file_hash(path)
                    new_value = f"{fingerprint}:{file_hash}"
                    # Migration: old cache stored bare MD5 — treat matching hash as unchanged
                    if cached == file_hash:
                        self.cache.set(cache_key, new_value)
                        continue
                    if cached != new_value:
                        changed_files.append(path)
                        logger.debug(f"Found changed file: {path}")
                    self.cache.set(cache_key, new_value)
                except Exception as e:
                    logger.error(f"Error hashing file {path}: {e}")
            elif path.is_dir():
                cache_key = str(path)
                if cache_key not in self.cache:
                    changed_dirs.append(path)
                    self.cache.set(cache_key, "dir")
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
            """Create new FTPS connection (TLS, shared-hosting cert ignored)"""
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ftp = ftplib.FTP_TLS(context=ctx)
            ftp.connect(self.settings.server_ftp_server, 21, timeout=TIMEOUT)
            ftp.auth()
            ftp.login(self.settings.server_ftp_username, self.settings.server_ftp_password)
            ftp.prot_p()
            ftp.set_debuglevel(0)
            return ftp

        def ensure_remote_dir(ftp, remote_dir: str):
            """Recursively ensure all components of remote_dir exist."""
            parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
            current = ""
            for part in parts:
                current = current + "/" + part
                try:
                    ftp.mkd(current)
                except ftplib.error_perm as e:
                    if "exist" not in str(e).lower():
                        raise

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
                        ensure_remote_dir(ftp, str(remote_path.parent))
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
        if affected_tags:
            # Just remove from cache so they'll be regenerated
            for tag in affected_tags:
                self.cache.delete(f"tag:{tag}")
                # Remove archive cache entries
                self.cache.delete_prefix(f"tag_archives:{tag}")

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
                self.cache.delete(f"page.html:{file_path}")
                
        # Clear archive cache entries
        self.cache.delete_prefix("archive:")