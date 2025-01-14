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

def clean_content(html: str) -> str:
    """Clean HTML content for rendering"""
    html = re.sub(r"<.?iframe[^>]*>", "", html)
    html = re.sub(r'"/tag/', '"https://samim.io/tag/', html)
    html = re.sub(r'style=\"[^\"]*\"', '', html)
    html = re.sub(r'data-mfp-src=\"[^\"]*\"', '', html)
    return html

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