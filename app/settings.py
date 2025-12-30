# app/settings.py

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List, Set, Optional
import re

class Settings(BaseSettings):
    # Basic app settings
    site_name: str = "samim"
    site_url: str = "https://samim.io"
    site_description: str = "samim.io - blogging, research, projects, ideas"
    site_keywords: List[str] = ["blog", "samim"]
    site_path_prefix: str = "/"
    site_filetype: str = ".md"
    site_showmore_length: int = 500
    site_scroll_amount: int = 20
    site_feed_amount: int = 25

    # Author details
    author: str = "samim"
    author_name: str = "samim"
    author_image: str = "https://samim.io/static/upload/A8SKcX4t_400x400.jpg"
    author_twitter: str = "samim"
    
    # Newsletter (optional - set to enable newsletter badge in nav)
    newsletter_url: str = "https://mailchi.mp/4804acffeb6e/samimio"  # e.g., "https://mailchi.mp/xxx/yourlist"

    # Server settings
    local_server_port: int = 2323
    local_server_debug: bool = True
    enable_file_monitoring: bool = False  # Disabled by default to avoid watchdog issues
    
    # Build settings
    build_search_index: bool = False  # Auto-build Pagefind search index (requires Node.js)

    # Authentication (set admin_password to enable live mode with login)
    admin_password: str = ""  # Leave empty for local dev mode, set for live server
    session_secret: str = "change-this-secret-key-in-production"  # Used to sign session cookies

    # Upload settings
    upload_method: str = "ftp"  # Options: "ftp" or "rsync"
    
    # FTP settings (used when upload_method = "ftp")
    server_ftp_enabled: bool = True
    server_ftp_server: str = "default_ftp_url"
    server_ftp_username: str = "default_user"
    server_ftp_password: str = "default_password"
    server_ftp_path: Path = Path("/public_html/")
    server_ftp_media_path: str = "/public_html/static/upload/"
    server_ftp_media_site_path: str = "https://samim.io/static/upload/"
    
    # rsync settings (used when upload_method = "rsync")
    rsync_host: str = "127.0.0.1"                   # e.g., "samim.io" or IP address
    rsync_user: str = "ssh_username"                # SSH username
    rsync_remote_path: str = "/public_html/"        # path to remote directory, e.g., "/var/www/html/" or "/home/user/public_html/"
    rsync_ssh_key: str = "~/.ssh/id_ed12345"        # path to PRIVATE SSH key
    rsync_delete: bool = False                      # Delete remote files not in local (keeps remote clean)

    # File paths
    local_upload_path: Path = Path("upload/")
    local_build_path: Path = Path("build/")
    allowed_extensions: Set[str] = {"png", "jpg", "jpeg", "gif", "webp"}

    # Asset settings
    content_dir: Path = Path("content/p/")
    templates_dir: Path = Path("app/templates")
    static_dir: Path = Path("app/static")

    class Config:
        env_file = ".env"
        
    def __init__(self, **data):
        super().__init__(**data)
        # Sanitize site_path_prefix to handle Windows paths
        self._sanitize_site_path_prefix()
            
    def _sanitize_site_path_prefix(self):
        """Clean the site_path_prefix to ensure it doesn't contain Windows paths"""
        if not self.site_path_prefix:
            self.site_path_prefix = "/"
            return
            
        # Strip Windows drive letters and paths
        sanitized = re.sub(r'^[A-Za-z]:[/\\].*?(?=/|$)', '', self.site_path_prefix)
        # Remove Git paths
        sanitized = re.sub(r'^/Git(/|$)', '/', sanitized)
        sanitized = re.sub(r'^Git(/|$)', '/', sanitized)
        # Remove Program Files path
        sanitized = re.sub(r'/Program Files(/|$)', '/', sanitized)
        
        # Ensure proper formatting - always has leading slash
        sanitized = '/' + sanitized.strip('/')
        
        # If it was just '/', keep it as '/'
        if sanitized == '//':
            sanitized = '/'
            
        self.site_path_prefix = sanitized

settings = Settings()
