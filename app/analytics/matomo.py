# app/analytics/matomo.py
"""
Matomo Reporting API Client

Handles all communication with the Matomo analytics server.
Implements caching to avoid excessive API calls.

Matomo API Reference: https://developer.matomo.org/api-reference/reporting-api
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import json
import hashlib
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


@dataclass
class PageMetrics:
    """Metrics for a single page/post"""
    url: str
    path: str  # Extracted path like "2025-12-31-my-post"
    label: str  # Page title or URL label
    visits: int = 0
    unique_visitors: int = 0
    pageviews: int = 0
    avg_time_on_page: float = 0.0  # seconds
    bounce_rate: float = 0.0  # percentage
    exit_rate: float = 0.0  # percentage


@dataclass  
class CountryMetrics:
    """Metrics by country"""
    country_code: str
    country_name: str
    visits: int = 0
    unique_visitors: int = 0
    pageviews: int = 0


@dataclass
class ReferrerMetrics:
    """Metrics by referrer source"""
    referrer_type: str  # 'search', 'social', 'website', 'direct', 'campaign'
    label: str
    visits: int = 0


@dataclass
class AnalyticsSummary:
    """Summary analytics for a time period"""
    period_start: datetime
    period_end: datetime
    total_visits: int = 0
    unique_visitors: int = 0
    total_pageviews: int = 0
    avg_visit_duration: float = 0.0  # seconds
    bounce_rate: float = 0.0
    pages_per_visit: float = 0.0
    top_pages: List[PageMetrics] = field(default_factory=list)
    top_countries: List[CountryMetrics] = field(default_factory=list)
    top_referrers: List[ReferrerMetrics] = field(default_factory=list)


class MatomoClient:
    """
    Client for Matomo Reporting API
    
    Fetches analytics data with intelligent caching to minimize API calls.
    """
    
    # Cache duration in seconds
    CACHE_DURATION = 3600  # 1 hour
    
    def __init__(self):
        from app.settings import settings
        from app.cache import get_cache
        
        self.base_url = getattr(settings, 'matomo_url', '')
        self.site_id = getattr(settings, 'matomo_site_id', 1)
        self.token = getattr(settings, 'matomo_token', '')
        self.cache = get_cache()
        
        # Normalize base URL
        if self.base_url and not self.base_url.endswith('/'):
            self.base_url += '/'
            
        if not self.base_url or not self.token:
            logger.warning("Matomo not configured - analytics features will be limited")
    
    @property
    def is_configured(self) -> bool:
        """Check if Matomo is properly configured"""
        return bool(self.base_url and self.token)
    
    def _get_cache_key(self, method: str, params: Dict) -> str:
        """Generate cache key for API request"""
        param_str = json.dumps(params, sort_keys=True)
        hash_str = hashlib.md5(f"{method}:{param_str}".encode()).hexdigest()[:12]
        return f"matomo:{method}:{hash_str}"
    
    def _api_request(self, method: str, extra_params: Dict = None, use_cache: bool = True) -> Optional[Any]:
        """
        Make API request to Matomo
        
        Args:
            method: Matomo API method (e.g., 'Actions.getPageUrls')
            extra_params: Additional parameters for the request
            use_cache: Whether to use cached results
            
        Returns:
            JSON response data or None on error
        """
        if not self.is_configured:
            logger.debug("Matomo not configured, skipping API request")
            return None
            
        params = {
            "module": "API",
            "method": method,
            "idSite": self.site_id,
            "format": "JSON",
            "token_auth": self.token,
        }
        
        if extra_params:
            params.update(extra_params)
        
        # Check cache first
        cache_key = self._get_cache_key(method, params)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                try:
                    # Handle both string (from SQLite cache) and dict (if somehow passed directly)
                    if isinstance(cached, str):
                        cache_data = json.loads(cached)
                    elif isinstance(cached, dict):
                        cache_data = cached
                    else:
                        cache_data = None
                    
                    if cache_data:
                        cache_time = cache_data.get('_cache_time', 0)
                        if datetime.now().timestamp() - cache_time < self.CACHE_DURATION:
                            logger.debug(f"Using cached Matomo data for {method}")
                            return cache_data.get('data')
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.debug(f"Cache parse error for {cache_key}: {e}")
                    pass
        
        try:
            url = urljoin(self.base_url, "index.php")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle Matomo error responses
            if isinstance(data, dict) and data.get('result') == 'error':
                logger.error(f"Matomo API error: {data.get('message')}")
                return None
            
            # Cache the result
            cache_data = {
                '_cache_time': datetime.now().timestamp(),
                'data': data
            }
            self.cache.set(cache_key, json.dumps(cache_data))
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Matomo API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from Matomo: {e}")
            return None
    
    def _extract_post_path(self, url: str) -> Optional[str]:
        """Extract post path from URL (e.g., '/p/my-post/' -> 'my-post')"""
        if '/p/' in url:
            parts = url.split('/p/')
            if len(parts) > 1:
                path = parts[1].strip('/')
                # Remove any trailing index.html
                if path.endswith('/index.html'):
                    path = path[:-11]
                return path if path else None
        return None
    
    def get_top_pages(
        self, 
        period: str = "month", 
        date: str = "today",
        limit: int = 50,
        filter_pattern: str = "/p/"
    ) -> List[PageMetrics]:
        """
        Get top pages by pageviews
        
        Args:
            period: 'day', 'week', 'month', 'year', or 'range'
            date: Date string like 'today', 'yesterday', '2025-01-01', or range
            limit: Maximum number of results (-1 for all)
            filter_pattern: Only include URLs matching this pattern
            
        Returns:
            List of PageMetrics sorted by pageviews descending
        """
        # For large fetches, use -1 to get all, otherwise double the limit
        api_limit = -1 if limit > 1000 else limit * 2
        
        data = self._api_request(
            "Actions.getPageUrls",
            {
                "period": period,
                "date": date,
                "flat": 1,
                "filter_limit": api_limit,
                "showColumns": "nb_visits,nb_uniq_visitors,nb_hits,avg_time_on_page,bounce_rate,exit_rate"
            },
            use_cache=limit <= 100  # Don't cache large fetches
        )
        
        if not data:
            return []
        
        pages = []
        for item in data:
            url = item.get('url', '') or item.get('label', '')
            
            # Filter by pattern if specified
            if filter_pattern and filter_pattern not in url:
                continue
                
            path = self._extract_post_path(url)
            
            # Parse percentage fields that may come as "76%" strings
            def parse_percent(val):
                if isinstance(val, str):
                    return float(val.replace('%', '').strip() or 0)
                return float(val or 0)
            
            pages.append(PageMetrics(
                url=url,
                path=path or url,
                label=item.get('label', url),
                visits=item.get('nb_visits', 0),
                unique_visitors=item.get('nb_uniq_visitors', 0),
                pageviews=item.get('nb_hits', 0),
                avg_time_on_page=parse_percent(item.get('avg_time_on_page', 0)),
                bounce_rate=parse_percent(item.get('bounce_rate', 0)),
                exit_rate=parse_percent(item.get('exit_rate', 0))
            ))
        
        # Sort by pageviews and limit
        pages.sort(key=lambda p: p.pageviews, reverse=True)
        return pages[:limit]
    
    def get_page_stats(self, page_path: str, period: str = "month", date: str = "today") -> Optional[PageMetrics]:
        """
        Get stats for a specific page
        
        Args:
            page_path: The post path (e.g., '2025-01-01-my-post')
            period: Time period
            date: Date string
            
        Returns:
            PageMetrics for the page or None if not found
        """
        data = self._api_request(
            "Actions.getPageUrl",
            {
                "period": period,
                "date": date,
                "pageUrl": f"/p/{page_path}/",
                "showColumns": "nb_visits,nb_uniq_visitors,nb_hits,avg_time_on_page,bounce_rate,exit_rate"
            }
        )
        
        if not data or (isinstance(data, list) and len(data) == 0):
            return None
            
        # Handle both single result and array response
        item = data[0] if isinstance(data, list) else data
        
        return PageMetrics(
            url=f"/p/{page_path}/",
            path=page_path,
            label=item.get('label', page_path),
            visits=item.get('nb_visits', 0),
            unique_visitors=item.get('nb_uniq_visitors', 0),
            pageviews=item.get('nb_hits', 0),
            avg_time_on_page=float(item.get('avg_time_on_page', 0)),
            bounce_rate=float(item.get('bounce_rate', 0)),
            exit_rate=float(item.get('exit_rate', 0))
        )
    
    def get_countries(self, period: str = "month", date: str = "today", limit: int = 20) -> List[CountryMetrics]:
        """Get visitor breakdown by country"""
        data = self._api_request(
            "UserCountry.getCountry",
            {
                "period": period,
                "date": date,
                "filter_limit": limit
            }
        )
        
        if not data:
            return []
        
        countries = []
        for item in data:
            countries.append(CountryMetrics(
                country_code=item.get('code', 'xx'),
                country_name=item.get('label', 'Unknown'),
                visits=item.get('nb_visits', 0),
                unique_visitors=item.get('nb_uniq_visitors', 0),
                pageviews=item.get('nb_actions', 0)
            ))
        
        return countries
    
    def get_referrers(self, period: str = "month", date: str = "today", limit: int = 20) -> List[ReferrerMetrics]:
        """Get top referrer sources"""
        data = self._api_request(
            "Referrers.getAll",
            {
                "period": period,
                "date": date,
                "filter_limit": limit
            }
        )
        
        if not data:
            return []
        
        referrers = []
        for item in data:
            referrers.append(ReferrerMetrics(
                referrer_type=item.get('referrer_type', 'unknown'),
                label=item.get('label', 'Unknown'),
                visits=item.get('nb_visits', 0)
            ))
        
        return referrers
    
    def get_summary(self, period: str = "month", date: str = "today", days: int = 30) -> AnalyticsSummary:
        """
        Get comprehensive analytics summary for a period
        
        Combines multiple API calls into a single summary object.
        
        For proper "last N days" data, use period="range" which will calculate
        the date range automatically based on the `days` parameter.
        """
        # Calculate date range for "last N days" queries
        end_date = datetime.now()
        if period == "range" or period == "last30":
            # Use a proper date range for last N days
            start_date = end_date - timedelta(days=days)
            api_period = "range"
            api_date = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        else:
            # Use the provided period/date as-is
            api_period = period
            api_date = date
            
            # Parse dates for display
            if date == "today":
                end_date = datetime.now()
            elif date == "yesterday":
                end_date = datetime.now() - timedelta(days=1)
            else:
                try:
                    end_date = datetime.strptime(date.split(',')[0], "%Y-%m-%d")
                except ValueError:
                    end_date = datetime.now()
            
            if period == "day":
                start_date = end_date
            elif period == "week":
                start_date = end_date - timedelta(days=7)
            elif period == "month":
                # Note: Matomo's "month" means current calendar month, not last 30 days
                start_date = end_date.replace(day=1)
            elif period == "year":
                start_date = end_date.replace(month=1, day=1)
            else:
                start_date = end_date
        
        # Get visit summary
        summary_data = self._api_request(
            "VisitsSummary.get",
            {"period": api_period, "date": api_date}
        ) or {}
        
        # Parse bounce rate - Matomo may return it as "76%" or as a number
        bounce_rate_raw = summary_data.get('bounce_rate', 0)
        if isinstance(bounce_rate_raw, str):
            bounce_rate = float(bounce_rate_raw.replace('%', '').strip() or 0)
        else:
            bounce_rate = float(bounce_rate_raw or 0)
        
        # Parse pages per visit
        pages_per_visit_raw = summary_data.get('nb_actions_per_visit', 0)
        if isinstance(pages_per_visit_raw, str):
            pages_per_visit = float(pages_per_visit_raw.replace('%', '').strip() or 0)
        else:
            pages_per_visit = float(pages_per_visit_raw or 0)
        
        # Note: nb_uniq_visitors may not be available for range queries in Matomo
        # Fall back to nb_visits if unique visitors is 0 or not available
        unique_visitors = summary_data.get('nb_uniq_visitors') or summary_data.get('nb_users') or 0
        total_visits = summary_data.get('nb_visits', 0)
        
        # If we're using a range and unique visitors is 0 but we have visits,
        # make a separate call to get unique visitors for the date range
        if api_period == "range" and unique_visitors == 0 and total_visits > 0:
            # Try VisitsSummary.getUniqueVisitors for the range
            try:
                uv_data = self._api_request(
                    "VisitsSummary.getUniqueVisitors",
                    {"period": api_period, "date": api_date}
                )
                if uv_data and isinstance(uv_data, (int, float)):
                    unique_visitors = int(uv_data)
                elif isinstance(uv_data, dict):
                    unique_visitors = uv_data.get('value', 0) or sum(uv_data.values()) if uv_data else 0
            except Exception:
                # If that fails, just use visits as an approximation
                pass
        
        return AnalyticsSummary(
            period_start=start_date,
            period_end=end_date,
            total_visits=total_visits,
            unique_visitors=unique_visitors,
            total_pageviews=summary_data.get('nb_actions', 0),
            avg_visit_duration=float(summary_data.get('avg_time_on_site', 0) or 0),
            bounce_rate=bounce_rate,
            pages_per_visit=pages_per_visit,
            top_pages=self.get_top_pages(api_period, api_date, limit=20),
            top_countries=self.get_countries(api_period, api_date, limit=10),
            top_referrers=self.get_referrers(api_period, api_date, limit=10)
        )
    
    def get_realtime_visitors(self, last_minutes: int = 30) -> int:
        """Get count of visitors in the last N minutes"""
        data = self._api_request(
            "Live.getCounters",
            {"lastMinutes": last_minutes},
            use_cache=False  # Don't cache realtime data
        )
        
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get('visits', 0)
        return 0
    
    def get_page_trends(
        self, 
        page_path: str, 
        period: str = "day",
        date: str = "last30"
    ) -> List[Dict[str, Any]]:
        """
        Get historical trend data for a specific page
        
        Returns daily/weekly data points for charting.
        """
        data = self._api_request(
            "Actions.getPageUrl",
            {
                "period": period,
                "date": date,
                "pageUrl": f"/p/{page_path}/"
            }
        )
        
        if not data or not isinstance(data, dict):
            return []
        
        trends = []
        for date_str, metrics in data.items():
            if isinstance(metrics, dict):
                trends.append({
                    "date": date_str,
                    "pageviews": metrics.get('nb_hits', 0),
                    "visitors": metrics.get('nb_uniq_visitors', 0)
                })
        
        return sorted(trends, key=lambda x: x['date'])
    
    def get_search_keywords(self, period: str = "range", date: str = None, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get search keywords that brought traffic to the site
        
        Critical for understanding what people are searching for.
        """
        if date is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            date = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        data = self._api_request(
            "Referrers.getKeywords",
            {
                "period": period,
                "date": date,
                "filter_limit": limit
            }
        )
        
        if not data or not isinstance(data, list):
            return []
        
        keywords = []
        for item in data:
            keywords.append({
                "keyword": item.get('label', ''),
                "visits": item.get('nb_visits', 0),
                "pageviews": item.get('nb_actions', 0),
                "bounce_rate": item.get('bounce_rate', 0)
            })
        
        return keywords
    
    def get_week_over_week_comparison(self) -> Dict[str, Any]:
        """
        Compare this week vs last week for trend analysis
        
        Returns percentage changes for key metrics.
        """
        # Current week (last 7 days)
        end_date = datetime.now()
        start_current = end_date - timedelta(days=7)
        current_range = f"{start_current.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        # Previous week (7-14 days ago)
        start_previous = end_date - timedelta(days=14)
        end_previous = end_date - timedelta(days=7)
        previous_range = f"{start_previous.strftime('%Y-%m-%d')},{end_previous.strftime('%Y-%m-%d')}"
        
        current = self._api_request("VisitsSummary.get", {"period": "range", "date": current_range}) or {}
        previous = self._api_request("VisitsSummary.get", {"period": "range", "date": previous_range}) or {}
        
        def calc_change(current_val, previous_val):
            if previous_val == 0:
                return 100.0 if current_val > 0 else 0.0
            return ((current_val - previous_val) / previous_val) * 100
        
        current_visits = current.get('nb_visits', 0)
        previous_visits = previous.get('nb_visits', 0)
        current_pageviews = current.get('nb_actions', 0)
        previous_pageviews = previous.get('nb_actions', 0)
        
        return {
            "current_week": {
                "visits": current_visits,
                "pageviews": current_pageviews,
                "bounce_rate": current.get('bounce_rate', 0),
                "avg_duration": current.get('avg_time_on_site', 0)
            },
            "previous_week": {
                "visits": previous_visits,
                "pageviews": previous_pageviews,
                "bounce_rate": previous.get('bounce_rate', 0),
                "avg_duration": previous.get('avg_time_on_site', 0)
            },
            "changes": {
                "visits": calc_change(current_visits, previous_visits),
                "pageviews": calc_change(current_pageviews, previous_pageviews),
                "direction": "up" if current_visits > previous_visits else "down" if current_visits < previous_visits else "stable"
            }
        }
    
    def get_trending_content(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get content that's trending UP compared to previous period
        
        Useful for identifying what's gaining momentum.
        """
        # Get this week's top pages
        end_date = datetime.now()
        start_current = end_date - timedelta(days=7)
        current_range = f"{start_current.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        # Previous week
        start_previous = end_date - timedelta(days=14)
        end_previous = end_date - timedelta(days=7)
        previous_range = f"{start_previous.strftime('%Y-%m-%d')},{end_previous.strftime('%Y-%m-%d')}"
        
        current_pages = self.get_top_pages("range", current_range, limit=50)
        previous_pages = self.get_top_pages("range", previous_range, limit=50)
        
        # Build lookup for previous period
        prev_lookup = {p.path: p.pageviews for p in previous_pages}
        
        trending = []
        for page in current_pages:
            prev_views = prev_lookup.get(page.path, 0)
            if prev_views > 0:
                change = ((page.pageviews - prev_views) / prev_views) * 100
            else:
                change = 100.0 if page.pageviews > 0 else 0.0
            
            # Only include pages with significant traffic and positive trend
            if page.pageviews >= 10 and change > 10:
                trending.append({
                    "path": page.path,
                    "label": page.label,
                    "current_views": page.pageviews,
                    "previous_views": prev_views,
                    "change_percent": round(change, 1),
                    "momentum": "🔥" if change > 50 else "📈" if change > 20 else "↗️"
                })
        
        # Sort by change percentage
        trending.sort(key=lambda x: x['change_percent'], reverse=True)
        return trending[:limit]
    
    # =====================================================
    # REFERRAL & SOCIAL SOURCE TRACKING
    # =====================================================
    
    def get_referrer_types(self, days: int = 30) -> Dict[str, Any]:
        """
        Get breakdown of traffic by referrer type
        
        Types: direct, search, website, social, campaign
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        date_range = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        data = self._api_request(
            "Referrers.getReferrerType",
            {"period": "range", "date": date_range}
        )
        
        if not data or not isinstance(data, list):
            return {}
        
        result = {}
        total = sum(item.get('nb_visits', 0) for item in data)
        
        for item in data:
            ref_type = item.get('label', 'unknown')
            visits = item.get('nb_visits', 0)
            result[ref_type] = {
                "visits": visits,
                "percentage": round((visits / total * 100) if total > 0 else 0, 1),
                "pageviews": item.get('nb_actions', 0),
                "bounce_rate": item.get('bounce_rate', 0)
            }
        
        return result
    
    def get_social_networks(self, days: int = 30, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Get traffic from social networks
        
        Shows which social platforms drive traffic.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        date_range = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        data = self._api_request(
            "Referrers.getSocials",
            {"period": "range", "date": date_range, "filter_limit": limit}
        )
        
        if not data or not isinstance(data, list):
            return []
        
        socials = []
        for item in data:
            socials.append({
                "network": item.get('label', 'Unknown'),
                "visits": item.get('nb_visits', 0),
                "pageviews": item.get('nb_actions', 0),
                "avg_time": item.get('avg_time_on_site', 0),
                "bounce_rate": item.get('bounce_rate', 0)
            })
        
        return socials
    
    def get_referring_websites(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get traffic from external websites
        
        Shows which sites link to and drive traffic.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        date_range = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        data = self._api_request(
            "Referrers.getWebsites",
            {"period": "range", "date": date_range, "filter_limit": limit}
        )
        
        if not data or not isinstance(data, list):
            return []
        
        websites = []
        for item in data:
            websites.append({
                "website": item.get('label', 'Unknown'),
                "visits": item.get('nb_visits', 0),
                "pageviews": item.get('nb_actions', 0),
                "avg_time": item.get('avg_time_on_site', 0),
                "bounce_rate": item.get('bounce_rate', 0)
            })
        
        return websites
    
    # =====================================================
    # HISTORICAL TIME-SERIES DATA
    # =====================================================
    
    def get_monthly_trends(self, months: int = 12) -> List[Dict[str, Any]]:
        """
        Get monthly traffic trends for the past N months
        
        Essential for understanding long-term patterns.
        """
        data = self._api_request(
            "VisitsSummary.get",
            {"period": "month", "date": f"last{months}"}
        )
        
        if not data or not isinstance(data, dict):
            return []
        
        trends = []
        for date_str, metrics in sorted(data.items()):
            if isinstance(metrics, dict):
                trends.append({
                    "month": date_str,
                    "visits": metrics.get('nb_visits', 0),
                    "pageviews": metrics.get('nb_actions', 0),
                    "avg_duration": metrics.get('avg_time_on_site', 0),
                    "bounce_rate": metrics.get('bounce_rate', 0)
                })
        
        return trends
    
    def get_tag_trends_over_time(self, tag: str, months: int = 6) -> List[Dict[str, Any]]:
        """
        Get performance trends for a specific tag over time
        
        Answers: "Is ML content growing over time?"
        """
        # This requires correlating page data with tag data
        # For now, return monthly page data which can be filtered
        data = self._api_request(
            "Actions.getPageUrls",
            {"period": "month", "date": f"last{months}", "filter_limit": 100}
        )
        
        # This would need additional processing to filter by tag
        # Returning structure for now
        return []  # TODO: Implement tag-specific trends
    
    def get_content_performance_history(self, path: str, months: int = 6) -> List[Dict[str, Any]]:
        """
        Get historical performance for a specific post
        
        Shows content lifecycle: launch → peak → decay
        """
        data = self._api_request(
            "Actions.getPageUrl",
            {
                "period": "month", 
                "date": f"last{months}",
                "pageUrl": f"/p/{path}/"
            }
        )
        
        if not data or not isinstance(data, dict):
            return []
        
        history = []
        for date_str, metrics in sorted(data.items()):
            if isinstance(metrics, dict):
                history.append({
                    "month": date_str,
                    "pageviews": metrics.get('nb_hits', 0),
                    "visitors": metrics.get('nb_visits', 0),
                    "avg_time": metrics.get('avg_time_on_page', 0)
                })
            elif isinstance(metrics, list) and len(metrics) > 0:
                m = metrics[0]
                history.append({
                    "month": date_str,
                    "pageviews": m.get('nb_hits', 0),
                    "visitors": m.get('nb_visits', 0),
                    "avg_time": m.get('avg_time_on_page', 0)
                })
        
        return history

