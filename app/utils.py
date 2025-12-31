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


def extract_all_images(html: str, site_url: str = "") -> list:
    """Extract all image URLs from HTML content
    
    Args:
        html: The HTML content to search
        site_url: The site URL to use for making relative URLs absolute
        
    Returns:
        List of absolute image URLs
    """
    images = []
    # Find all img src attributes
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html):
        img_url = match.group(1)
        
        # Skip data URIs (base64 images)
        if img_url.startswith('data:'):
            continue
        
        # Make relative URLs absolute
        if site_url and not img_url.startswith(('http://', 'https://')):
            site_url_clean = site_url.rstrip('/')
            if img_url.startswith('/'):
                img_url = site_url_clean + img_url
            else:
                img_url = site_url_clean + '/' + img_url
        
        if img_url and img_url not in images:
            images.append(img_url)
    
    return images


def get_content_stats(html: str) -> dict:
    """Get statistics about content (text length, image count) for SEO decisions
    
    Args:
        html: The HTML content to analyze
        
    Returns:
        Dict with text_length and image_count
    """
    # Strip HTML to get text
    text = strip_html(html)
    text_length = len(text.strip())
    
    # Count images
    image_count = len(re.findall(r'<img[^>]+>', html, re.IGNORECASE))
    
    return {
        'text_length': text_length,
        'image_count': image_count,
        'is_image_focused': image_count > 0 and text_length < 200
    }

def is_animated_gif(image_bytes: bytes) -> bool:
    """Check if a GIF image is animated (has multiple frames)
    
    Args:
        image_bytes: Raw bytes of the image file
        
    Returns:
        True if the GIF is animated, False otherwise
    """
    try:
        from PIL import Image
        import io
        
        img = Image.open(io.BytesIO(image_bytes))
        if img.format != 'GIF':
            return False
        
        # Use Pillow's built-in animation detection
        # n_frames > 1 means animated, is_animated is also available in newer Pillow
        n_frames = getattr(img, 'n_frames', 1)
        is_animated = getattr(img, 'is_animated', n_frames > 1)
        return is_animated or n_frames > 1
    except Exception:
        return False


def convert_to_webp(image_bytes: bytes, original_filename: str, quality: int = 90) -> tuple:
    """Convert an image to WebP format
    
    Args:
        image_bytes: Raw bytes of the original image
        original_filename: Original filename to determine format and generate new name
        quality: WebP quality (1-100), default 90 for good balance
        
    Returns:
        Tuple of (converted_bytes, new_filename)
        Returns original bytes and filename if conversion not needed/possible
    """
    from PIL import Image
    import io
    
    # Get file extension
    ext = original_filename.lower().rsplit('.', 1)[-1] if '.' in original_filename else ''
    
    # Skip if already WebP
    if ext == 'webp':
        return image_bytes, original_filename
    
    # Skip animated GIFs - keep as-is
    if ext == 'gif' and is_animated_gif(image_bytes):
        return image_bytes, original_filename
    
    try:
        # Open image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Handle different modes
        if img.mode in ('RGBA', 'LA', 'P'):
            # Keep alpha channel for transparency
            if img.mode == 'P':
                img = img.convert('RGBA')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Convert to WebP
        output = io.BytesIO()
        
        # Use lossless for images with transparency, lossy otherwise
        if img.mode == 'RGBA':
            # Check if image actually uses transparency
            if img.getchannel('A').getextrema()[0] < 255:
                # Has transparency - use lossless for quality
                img.save(output, format='WEBP', lossless=True)
            else:
                # No actual transparency - convert to RGB and use lossy
                img = img.convert('RGB')
                img.save(output, format='WEBP', quality=quality, method=6)
        else:
            img.save(output, format='WEBP', quality=quality, method=6)
        
        # Generate new filename
        name_without_ext = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
        new_filename = f"{name_without_ext}.webp"
        
        return output.getvalue(), new_filename
        
    except Exception as e:
        # If conversion fails, return original
        import logging
        logging.getLogger(__name__).warning(f"WebP conversion failed for {original_filename}: {e}")
        return image_bytes, original_filename


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