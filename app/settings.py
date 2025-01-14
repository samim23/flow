# app/settings.py

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List, Set

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

    # Server settings
    local_server_port: int = 2323
    local_server_debug: bool = True

    # Authentication
    local_server_auth: bool = False
    local_server_auth_name: str = ""
    local_server_auth_pass: str = ""

    # FTP settings
    server_ftp_enabled: bool = True
    server_ftp_server: str = "default_ftp_url"
    server_ftp_username: str = "default_user"
    server_ftp_password: str = "default_password"
    server_ftp_path: Path = Path("/public_html/")
    server_ftp_media_path: str = "/public_html/static/upload/"
    server_ftp_media_site_path: str = "https://samim.io/static/upload/"

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

settings = Settings()
