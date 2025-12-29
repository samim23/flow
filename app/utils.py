# /app/utils.py

import re
import bleach
from typing import List, TypeVar, Generic
from math import ceil

T = TypeVar('T')

def strip_html(html_str: str) -> str:
    """Remove HTML tags from string"""
    tags = []
    attr = {}
    styles = []
    strip = True
    return bleach.clean(html_str, tags=tags, attributes=attr, styles=styles, strip=strip)

def clean_content(html: str, site_url: str = "") -> str:
    """Clean HTML content for rendering
    
    Args:
        html: The HTML content to clean
        site_url: The site URL to use for absolute URLs (optional)
    """
    # Remove iframes, scripts, and other problematic elements
    html = re.sub(r"<.?iframe[^>]*>", "", html)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    
    # Only convert to absolute URLs if site_url is provided
    if site_url:
        site_url = site_url.rstrip('/')
        # Convert relative tag links to absolute
        html = re.sub(r'"/tag/', f'"{site_url}/tag/', html)
        # Convert relative image sources to absolute
        html = re.sub(r'src="/static/', f'src="{site_url}/static/', html)
        html = re.sub(r'src="/upload/', f'src="{site_url}/upload/', html)
        # Handle href for internal links
        html = re.sub(r'href="/p/', f'href="{site_url}/p/', html)
        html = re.sub(r'href="/tag/', f'href="{site_url}/tag/', html)
    
    # Remove inline styles and data attributes (can cause RSS parsing issues)
    html = re.sub(r'style=\"[^\"]*\"', '', html)
    html = re.sub(r'data-[a-z-]+=\"[^\"]*\"', '', html)
    
    return html


def extract_first_image(html: str, site_url: str = "") -> str:
    """Extract the URL of the first image from HTML content
    
    Args:
        html: The HTML content to search
        site_url: The site URL to use for making relative URLs absolute
        
    Returns:
        The absolute URL of the first image, or empty string if none found
    """
    # Find first img src
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    if not match:
        return ""
    
    img_url = match.group(1)
    
    # Skip data URIs (base64 images)
    if img_url.startswith('data:'):
        return ""
    
    # Make relative URLs absolute
    if site_url and not img_url.startswith(('http://', 'https://')):
        site_url = site_url.rstrip('/')
        if img_url.startswith('/'):
            img_url = site_url + img_url
        else:
            img_url = site_url + '/' + img_url
    
    return img_url


def get_image_mime_type(url: str) -> str:
    """Guess the MIME type of an image from its URL
    
    Args:
        url: The image URL
        
    Returns:
        The MIME type string
    """
    url_lower = url.lower()
    if '.png' in url_lower:
        return 'image/png'
    elif '.gif' in url_lower:
        return 'image/gif'
    elif '.webp' in url_lower:
        return 'image/webp'
    else:
        return 'image/jpeg'  # Default to JPEG

class Paginator(Generic[T]):
    """Generic pagination utility"""
    def __init__(self, items: List[T], per_page: int):
        # Ensure items is a concrete list, not a generator
        self.items = list(sorted(items, key=lambda p: p.metadata.date, reverse=False))
        self.per_page = per_page
        self.total_items = len(self.items)
        self.total_pages = ceil(self.total_items / per_page)
        
        # Pre-chunk pages with reversed order like legacy app
        self.chunks = []
        for i in range(0, self.total_items, per_page):
            chunk = self.items[i:i + per_page]
            self.chunks.append(list(reversed(chunk)))  # Reverse each chunk

    def get_page(self, page: int) -> List[T]:
        """Get a specific page"""
        if page < 0 or page >= self.total_pages:
            return []
        return list(self.chunks[page])  # Return a concrete list