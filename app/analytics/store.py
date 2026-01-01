# app/analytics/store.py
"""
Analytics Data Store

Persists analytics data locally for historical analysis,
trend detection, and offline access to metrics.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PostAnalytics:
    """Stored analytics for a single post"""
    path: str
    title: str
    tags: List[str]
    date_published: Optional[datetime]
    
    # Aggregated metrics
    total_pageviews: int = 0
    total_visitors: int = 0
    avg_time_on_page: float = 0.0
    
    # Time-series snapshots (date -> metrics)
    daily_views: Dict[str, int] = None  # {"2025-01-01": 123, ...}
    
    # Computed fields
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.daily_views is None:
            self.daily_views = {}
        if self.last_updated is None:
            self.last_updated = datetime.now()


@dataclass
class TagAnalytics:
    """Aggregated analytics for a tag"""
    tag: str
    total_pageviews: int = 0
    total_visitors: int = 0
    post_count: int = 0
    daily_views: Dict[str, int] = None
    
    def __post_init__(self):
        if self.daily_views is None:
            self.daily_views = {}


class AnalyticsStore:
    """
    Local storage for analytics data
    
    Uses SQLite (via the existing cache system) to store:
    - Historical metrics snapshots
    - Per-post analytics
    - Tag-level aggregations
    """
    
    def __init__(self):
        from app.cache import get_cache
        self.cache = get_cache()
        self._post_analytics: Dict[str, PostAnalytics] = {}
        self._tag_analytics: Dict[str, TagAnalytics] = {}
        self._load_stored_data()
    
    def _load_stored_data(self):
        """Load previously stored analytics from cache"""
        try:
            # Load post analytics
            post_data = self.cache.get("analytics:posts")
            if post_data:
                # Handle both string (from SQLite) and dict (if passed directly)
                if isinstance(post_data, str):
                    data = json.loads(post_data)
                elif isinstance(post_data, dict):
                    data = post_data
                else:
                    data = {}
                
                for path, post_dict in data.items():
                    # Convert date strings back to datetime
                    if post_dict.get('date_published'):
                        try:
                            post_dict['date_published'] = datetime.fromisoformat(post_dict['date_published'])
                        except (ValueError, TypeError):
                            post_dict['date_published'] = None
                    if post_dict.get('last_updated'):
                        try:
                            post_dict['last_updated'] = datetime.fromisoformat(post_dict['last_updated'])
                        except (ValueError, TypeError):
                            post_dict['last_updated'] = None
                    self._post_analytics[path] = PostAnalytics(**post_dict)
            
            # Load tag analytics
            tag_data = self.cache.get("analytics:tags")
            if tag_data:
                # Handle both string and dict
                if isinstance(tag_data, str):
                    data = json.loads(tag_data)
                elif isinstance(tag_data, dict):
                    data = tag_data
                else:
                    data = {}
                    
                for tag, tag_dict in data.items():
                    self._tag_analytics[tag] = TagAnalytics(**tag_dict)
                    
            logger.debug(f"Loaded analytics for {len(self._post_analytics)} posts, {len(self._tag_analytics)} tags")
            
        except Exception as e:
            logger.error(f"Failed to load stored analytics: {e}")
    
    def _save_data(self):
        """Persist analytics to cache"""
        try:
            # Serialize post analytics
            post_data = {}
            for path, post in self._post_analytics.items():
                post_dict = asdict(post)
                # Convert datetime to string
                if post_dict.get('date_published'):
                    post_dict['date_published'] = post_dict['date_published'].isoformat()
                if post_dict.get('last_updated'):
                    post_dict['last_updated'] = post_dict['last_updated'].isoformat()
                post_data[path] = post_dict
            
            self.cache.set("analytics:posts", json.dumps(post_data))
            
            # Serialize tag analytics
            tag_data = {tag: asdict(t) for tag, t in self._tag_analytics.items()}
            self.cache.set("analytics:tags", json.dumps(tag_data))
            
        except Exception as e:
            logger.error(f"Failed to save analytics data: {e}")
    
    def update_post_analytics(
        self, 
        path: str, 
        title: str,
        tags: List[str],
        date_published: Optional[datetime],
        pageviews: int,
        visitors: int,
        avg_time: float,
        snapshot_date: str = None
    ):
        """
        Update or create analytics record for a post
        
        Args:
            path: Post path (e.g., '2025-01-01-my-post')
            title: Post title
            tags: List of tags
            date_published: Publication date
            pageviews: Total pageviews
            visitors: Unique visitors
            avg_time: Average time on page
            snapshot_date: Date for daily snapshot (YYYY-MM-DD)
        """
        if snapshot_date is None:
            snapshot_date = datetime.now().strftime("%Y-%m-%d")
        
        if path in self._post_analytics:
            post = self._post_analytics[path]
            post.title = title
            post.tags = tags
            post.total_pageviews = pageviews
            post.total_visitors = visitors
            post.avg_time_on_page = avg_time
            post.daily_views[snapshot_date] = pageviews
            post.last_updated = datetime.now()
        else:
            self._post_analytics[path] = PostAnalytics(
                path=path,
                title=title,
                tags=tags,
                date_published=date_published,
                total_pageviews=pageviews,
                total_visitors=visitors,
                avg_time_on_page=avg_time,
                daily_views={snapshot_date: pageviews},
                last_updated=datetime.now()
            )
        
        self._save_data()
    
    def get_post_analytics(self, path: str) -> Optional[PostAnalytics]:
        """Get stored analytics for a post"""
        return self._post_analytics.get(path)
    
    def get_all_post_analytics(self) -> Dict[str, PostAnalytics]:
        """Get all stored post analytics"""
        return self._post_analytics.copy()
    
    def get_top_posts(self, limit: int = 20) -> List[PostAnalytics]:
        """Get top posts by total pageviews"""
        posts = list(self._post_analytics.values())
        posts.sort(key=lambda p: p.total_pageviews, reverse=True)
        return posts[:limit]
    
    def get_posts_by_tag(self, tag: str) -> List[PostAnalytics]:
        """Get all posts with a specific tag"""
        return [p for p in self._post_analytics.values() if tag in p.tags]
    
    def aggregate_tag_analytics(self):
        """Recompute tag-level aggregations from post data"""
        self._tag_analytics = {}
        
        for post in self._post_analytics.values():
            for tag in post.tags:
                if tag not in self._tag_analytics:
                    self._tag_analytics[tag] = TagAnalytics(
                        tag=tag,
                        total_pageviews=0,
                        total_visitors=0,
                        post_count=0,
                        daily_views={}
                    )
                
                tag_analytics = self._tag_analytics[tag]
                tag_analytics.total_pageviews += post.total_pageviews
                tag_analytics.total_visitors += post.total_visitors
                tag_analytics.post_count += 1
                
                # Merge daily views
                for date, views in post.daily_views.items():
                    tag_analytics.daily_views[date] = tag_analytics.daily_views.get(date, 0) + views
        
        self._save_data()
    
    def get_tag_analytics(self, tag: str) -> Optional[TagAnalytics]:
        """Get analytics for a specific tag"""
        return self._tag_analytics.get(tag)
    
    def get_top_tags(self, limit: int = 20) -> List[TagAnalytics]:
        """Get top tags by total pageviews"""
        tags = list(self._tag_analytics.values())
        tags.sort(key=lambda t: t.total_pageviews, reverse=True)
        return tags[:limit]
    
    def get_declining_posts(self, days: int = 30, threshold: float = 0.3) -> List[Dict]:
        """
        Find posts with declining traffic
        
        Args:
            days: Look at last N days
            threshold: Minimum decline ratio to flag (0.3 = 30% decline)
            
        Returns:
            List of posts with decline info
        """
        declining = []
        cutoff = datetime.now() - timedelta(days=days)
        midpoint = datetime.now() - timedelta(days=days // 2)
        
        for post in self._post_analytics.values():
            if not post.daily_views:
                continue
            
            # Split views into first half and second half of period
            first_half_views = 0
            second_half_views = 0
            
            for date_str, views in post.daily_views.items():
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    if date < cutoff:
                        continue
                    if date < midpoint:
                        first_half_views += views
                    else:
                        second_half_views += views
                except ValueError:
                    continue
            
            if first_half_views > 10:  # Only consider posts with meaningful traffic
                decline = (first_half_views - second_half_views) / first_half_views
                if decline >= threshold:
                    declining.append({
                        "post": post,
                        "decline_ratio": decline,
                        "first_half": first_half_views,
                        "second_half": second_half_views
                    })
        
        declining.sort(key=lambda x: x['decline_ratio'], reverse=True)
        return declining
    
    def sync_from_matomo(self, content_manager=None, days: int = 90):
        """
        Sync analytics data from Matomo
        
        Fetches latest data and updates local store.
        
        Args:
            content_manager: Optional ContentManager for post metadata
            days: Number of days to fetch (default 90)
        """
        from . import get_matomo_client
        from datetime import datetime, timedelta
        
        client = get_matomo_client()
        if not client.is_configured:
            logger.warning("Cannot sync - Matomo not configured")
            return
        
        logger.info(f"Syncing analytics from Matomo (last {days} days)...")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        date_range = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        # Get ALL pages with pageviews - no arbitrary limit!
        # Use period="range" to get cumulative data for the entire period
        top_pages = client.get_top_pages(
            period="range", 
            date=date_range, 
            limit=10000  # Get up to 10k pages - should cover most blogs
        )
        
        # Get content manager for post metadata
        if content_manager is None:
            try:
                from app.content import ContentManager
                from app.settings import settings
                content_manager = ContentManager(settings.content_dir)
            except Exception as e:
                logger.warning(f"Could not load content manager: {e}")
        
        updated_count = 0
        for page in top_pages:
            path = page.path
            if not path or path.startswith('/'):
                continue
            
            # Try to get post metadata
            title = page.label
            tags = []
            date_published = None
            
            if content_manager:
                post = content_manager.get_page(path)
                if post:
                    title = post.metadata.title or title
                    tags = post.metadata.tags or []
                    date_published = post.metadata.date
            
            self.update_post_analytics(
                path=path,
                title=title,
                tags=tags,
                date_published=date_published,
                pageviews=page.pageviews,
                visitors=page.unique_visitors,
                avg_time=page.avg_time_on_page
            )
            updated_count += 1
        
        # Recompute tag aggregations
        self.aggregate_tag_analytics()
        
        logger.info(f"Synced analytics for {updated_count} posts")
        return updated_count
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary statistics about stored data"""
        total_pageviews = sum(p.total_pageviews for p in self._post_analytics.values())
        total_visitors = sum(p.total_visitors for p in self._post_analytics.values())
        
        return {
            "posts_tracked": len(self._post_analytics),
            "tags_tracked": len(self._tag_analytics),
            "total_pageviews": total_pageviews,
            "total_visitors": total_visitors,
            "last_sync": max(
                (p.last_updated for p in self._post_analytics.values()),
                default=None
            )
        }

