# app/sidebar_config.py
"""
Sidebar Popular Posts Configuration

Parses the sidebar-popular.txt config file that controls which posts
appear in the homepage sidebar's "Popular" section.

Config format:
```
# Posts that always appear at top (in order)
pin:
2024-my-best-work
2023-featured-piece

# Specific posts to exclude
exclude:
2024-conspiracy-post

# Entire tags to exclude
exclude_tags:
conspiracy
politics
```
"""

import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Set, Optional

logger = logging.getLogger(__name__)

# System pages that are always excluded
SYSTEM_PAGES = {'about', 'contact', 'imprint', 'privacy', 'terms', 'legal'}

# Default number of popular posts to show in sidebar
SIDEBAR_POPULAR_LIMIT = 12

# Pool size for client-side shuffling (generate more, JS picks LIMIT)
SIDEBAR_POPULAR_POOL = 24

# Max tags to include per post in sidebar
SIDEBAR_MAX_TAGS = 2


@dataclass
class SidebarConfig:
    """Configuration for sidebar popular posts"""
    pinned_posts: List[str] = field(default_factory=list)
    excluded_posts: Set[str] = field(default_factory=set)
    excluded_tags: Set[str] = field(default_factory=set)
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> 'SidebarConfig':
        """Load config from file, or return empty config if not found"""
        if config_path is None:
            # Config lives in app/data/, not content folder
            config_path = Path(__file__).parent / 'data' / 'sidebar-popular.txt'
        
        config = cls()
        
        if not config_path.exists():
            logger.debug(f"No sidebar config found at {config_path}")
            return config
        
        try:
            content = config_path.read_text(encoding='utf-8')
            current_section = None
            
            for line in content.splitlines():
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Detect section headers
                if line == 'pin:':
                    current_section = 'pin'
                    continue
                elif line == 'exclude:':
                    current_section = 'exclude'
                    continue
                elif line == 'exclude_tags:':
                    current_section = 'exclude_tags'
                    continue
                
                # Add to appropriate section
                if current_section == 'pin':
                    config.pinned_posts.append(line)
                elif current_section == 'exclude':
                    config.excluded_posts.add(line)
                elif current_section == 'exclude_tags':
                    config.excluded_tags.add(line.lower())
            
            logger.debug(
                f"Loaded sidebar config: {len(config.pinned_posts)} pinned, "
                f"{len(config.excluded_posts)} excluded, "
                f"{len(config.excluded_tags)} excluded tags"
            )
            
        except Exception as e:
            logger.warning(f"Error loading sidebar config: {e}")
        
        return config
    
    def is_excluded(self, path: str, tags: Optional[List[str]] = None) -> bool:
        """Check if a post should be excluded from popular list"""
        # Check explicit exclusion
        if path in self.excluded_posts:
            return True
        
        # Check system pages
        if path.lower() in SYSTEM_PAGES:
            return True
        
        # Check tag-based exclusion
        if tags:
            for tag in tags:
                if tag.lower() in self.excluded_tags:
                    return True
        
        return False
    
    def is_pinned(self, path: str) -> bool:
        """Check if a post is pinned"""
        return path in self.pinned_posts


def filter_popular_posts(
    algo_posts: List[dict],
    content_manager,
    config: Optional[SidebarConfig] = None,
    limit: int = None
) -> List[dict]:
    """
    Filter and order popular posts according to config.
    
    Args:
        algo_posts: List of posts from analytics (dicts with 'path', 'title', 'pageviews')
        content_manager: ContentManager instance to validate paths and get tags
        config: SidebarConfig (loaded if not provided)
        limit: Maximum number of posts to return (defaults to SIDEBAR_POPULAR_LIMIT)
    
    Returns:
        Filtered and ordered list of posts (includes tags for display)
    """
    if config is None:
        config = SidebarConfig.load()
    
    if limit is None:
        limit = SIDEBAR_POPULAR_LIMIT
    
    result = []
    seen_paths = set()
    
    # 1. Add pinned posts first
    for pinned_path in config.pinned_posts:
        if len(result) >= limit:
            break
        
        # Validate the pinned post exists
        page = content_manager.get_page(pinned_path)
        if page and page.metadata.status == 'public':
            tags = page.metadata.tags[:SIDEBAR_MAX_TAGS] if page.metadata.tags else []
            result.append({
                "path": pinned_path,
                "title": page.metadata.title or pinned_path,
                "tags": tags,
                "pageviews": 0,  # Pinned, not algorithmic
                "pinned": True
            })
            seen_paths.add(pinned_path)
        else:
            logger.warning(f"Pinned post not found or not public: {pinned_path}")
    
    # 2. Add algorithmic posts (filtered)
    for post in algo_posts:
        if len(result) >= limit:
            break
        
        path = post.get('path', '')
        
        # Skip if already added (pinned)
        if path in seen_paths:
            continue
        
        # Skip invalid paths
        if not path or not _is_valid_post_path(path):
            continue
        
        # Validate the post exists in content manager
        page = content_manager.get_page(path)
        if not page:
            continue
        
        if page.metadata.status != 'public':
            continue
        
        # Check exclusions (explicit posts and tags)
        all_tags = page.metadata.tags if page.metadata.tags else []
        if config.is_excluded(path, all_tags):
            continue
        
        # Add to result (with limited tags for display)
        display_tags = all_tags[:SIDEBAR_MAX_TAGS] if all_tags else []
        result.append({
            "path": path,
            "title": page.metadata.title or path,
            "tags": display_tags,
            "pageviews": post.get('pageviews', 0),
            "pinned": False
        })
        seen_paths.add(path)
    
    return result


def _is_valid_post_path(path: str) -> bool:
    """Check if path looks like a valid post path"""
    if not path:
        return False
    
    # Reject paths with domain names or weird patterns
    if 'samim.io' in path.lower():
        return False
    if ' - ' in path:  # Matomo's "Others" aggregation
        return False
    if path.startswith('/'):
        return False
    if path.startswith('http'):
        return False
    
    # Reject system pages
    if path.lower() in SYSTEM_PAGES:
        return False
    
    return True

