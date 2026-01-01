# app/analytics/insights.py
"""
Analytics Insights Engine

Derives actionable insights from raw analytics data:
- Content performance patterns
- Trend detection
- Recommendations for content strategy
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import re

logger = logging.getLogger(__name__)


@dataclass
class ContentPattern:
    """Identified pattern in successful content"""
    name: str
    description: str
    examples: List[str]
    impact_score: float  # 0-1, higher = stronger correlation with success


@dataclass
class ContentGap:
    """Identified gap in content coverage"""
    topic: str
    reason: str
    last_post_date: Optional[datetime]
    potential_value: str  # 'high', 'medium', 'low'


@dataclass
class TrendInfo:
    """Trend information for a topic/tag"""
    name: str
    direction: str  # 'rising', 'falling', 'stable'
    change_percent: float
    current_views: int
    previous_views: int


class InsightsEngine:
    """
    Generates insights from analytics data
    
    Analyzes patterns, identifies trends, and provides
    actionable recommendations for content strategy.
    """
    
    def __init__(self):
        from . import get_analytics_store, get_matomo_client
        self.store = get_analytics_store()
        self.matomo = get_matomo_client()
        self._content_manager = None  # Cached to avoid rescanning files
    
    def _get_content_manager(self):
        """Get cached content manager to avoid rescanning 14k+ files on each call"""
        if self._content_manager is None:
            try:
                from app.content import ContentManager
                from app.settings import settings
                self._content_manager = ContentManager(settings.content_dir)
            except Exception as e:
                logger.warning(f"Could not initialize ContentManager: {e}")
        return self._content_manager
    
    def analyze_title_patterns(self) -> List[ContentPattern]:
        """
        Analyze what makes titles successful
        
        Looks for patterns in high-performing post titles.
        """
        patterns = []
        top_posts = self.store.get_top_posts(limit=20)
        
        if len(top_posts) < 5:
            return patterns
        
        titles = [p.title for p in top_posts if p.title]
        
        # Pattern: Numbers in titles
        with_numbers = [t for t in titles if re.search(r'\d+', t)]
        if len(with_numbers) >= len(titles) * 0.3:
            patterns.append(ContentPattern(
                name="numbers_in_title",
                description="Titles with numbers tend to perform better",
                examples=with_numbers[:3],
                impact_score=len(with_numbers) / len(titles)
            ))
        
        # Pattern: Question titles
        questions = [t for t in titles if '?' in t]
        if len(questions) >= len(titles) * 0.2:
            patterns.append(ContentPattern(
                name="question_title",
                description="Question-based titles engage readers",
                examples=questions[:3],
                impact_score=len(questions) / len(titles)
            ))
        
        # Pattern: "How to" titles
        how_to = [t for t in titles if t.lower().startswith('how to') or 'guide' in t.lower()]
        if len(how_to) >= len(titles) * 0.2:
            patterns.append(ContentPattern(
                name="how_to_guide",
                description="Tutorial and guide content performs well",
                examples=how_to[:3],
                impact_score=len(how_to) / len(titles)
            ))
        
        # Pattern: Title length
        avg_length = sum(len(t) for t in titles) / len(titles)
        if 40 <= avg_length <= 70:
            patterns.append(ContentPattern(
                name="optimal_title_length",
                description=f"Successful titles average {int(avg_length)} characters",
                examples=[],
                impact_score=0.5
            ))
        
        # Pattern: Year in title (evergreen vs dated)
        with_year = [t for t in titles if re.search(r'20\d{2}', t)]
        if len(with_year) >= len(titles) * 0.25:
            patterns.append(ContentPattern(
                name="year_in_title",
                description="Dated content ('Year in Review', '2025 Guide') attracts traffic",
                examples=with_year[:3],
                impact_score=len(with_year) / len(titles)
            ))
        
        return patterns
    
    def analyze_tag_trends(self, days: int = 30) -> List[TrendInfo]:
        """
        Analyze which tags are trending up or down
        
        Compares recent period to previous period.
        """
        tag_analytics = self.store.get_top_tags(limit=50)
        trends = []
        
        midpoint = (datetime.now() - timedelta(days=days // 2)).strftime("%Y-%m-%d")
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        for tag in tag_analytics:
            first_half = 0
            second_half = 0
            
            for date_str, views in tag.daily_views.items():
                if date_str < cutoff:
                    continue
                if date_str < midpoint:
                    first_half += views
                else:
                    second_half += views
            
            if first_half > 0:
                change = ((second_half - first_half) / first_half) * 100
            else:
                change = 100 if second_half > 0 else 0
            
            if abs(change) >= 10:  # Only include significant changes
                direction = "rising" if change > 0 else "falling" if change < 0 else "stable"
                trends.append(TrendInfo(
                    name=tag.tag,
                    direction=direction,
                    change_percent=round(change, 1),
                    current_views=second_half,
                    previous_views=first_half
                ))
        
        # Sort by absolute change
        trends.sort(key=lambda t: abs(t.change_percent), reverse=True)
        return trends
    
    def identify_content_gaps(self, content_manager=None) -> List[ContentGap]:
        """
        Identify topics that might benefit from new content
        
        Looks for:
        - Popular tags with no recent posts
        - Declining topics that could use refreshers
        - Emerging trends not yet covered
        """
        gaps = []
        
        # Use cached content manager to avoid rescanning 14k+ files
        if content_manager is None:
            content_manager = self._get_content_manager()
        
        # Find popular tags with stale content
        top_tags = self.store.get_top_tags(limit=20)
        for tag in top_tags:
            posts = self.store.get_posts_by_tag(tag.tag)
            if not posts:
                continue
            
            # Find most recent post date
            recent_date = None
            for post in posts:
                if post.date_published:
                    if recent_date is None or post.date_published > recent_date:
                        recent_date = post.date_published
            
            if recent_date:
                days_since = (datetime.now() - recent_date).days
                if days_since > 90 and tag.total_pageviews > 100:
                    gaps.append(ContentGap(
                        topic=tag.tag,
                        reason=f"Popular tag with no posts in {days_since} days",
                        last_post_date=recent_date,
                        potential_value="high" if tag.total_pageviews > 500 else "medium"
                    ))
        
        # Find declining topics that could use refreshers
        declining = self.store.get_declining_posts(days=30, threshold=0.3)
        for item in declining[:5]:
            post = item['post']
            if post.total_pageviews > 100:
                gaps.append(ContentGap(
                    topic=post.title,
                    reason=f"Traffic declining {int(item['decline_ratio'] * 100)}% - consider update",
                    last_post_date=post.date_published,
                    potential_value="medium"
                ))
        
        return gaps
    
    def get_optimal_posting_times(self) -> Dict[str, Any]:
        """
        Analyze when content performs best
        
        Returns insights about:
        - Best day of week to publish
        - Optimal post timing patterns
        """
        posts = list(self.store.get_all_post_analytics().values())
        
        if len(posts) < 10:
            return {"insufficient_data": True}
        
        # Analyze by day of week
        day_performance = {i: [] for i in range(7)}
        
        for post in posts:
            if post.date_published and post.total_pageviews > 0:
                weekday = post.date_published.weekday()
                day_performance[weekday].append(post.total_pageviews)
        
        # Calculate average performance by day
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_averages = {}
        
        for day, views in day_performance.items():
            if views:
                day_averages[day_names[day]] = {
                    'avg_views': sum(views) / len(views),
                    'post_count': len(views)
                }
        
        # Find best day
        best_day = max(day_averages.items(), key=lambda x: x[1]['avg_views'])[0] if day_averages else None
        
        return {
            "by_weekday": day_averages,
            "best_day": best_day,
            "recommendation": f"Consider publishing on {best_day}" if best_day else None
        }
    
    def get_performance_benchmarks(self) -> Dict[str, Any]:
        """
        Calculate performance benchmarks for content
        
        Helps understand what "good" looks like for this blog.
        """
        posts = list(self.store.get_all_post_analytics().values())
        
        if len(posts) < 5:
            return {"insufficient_data": True}
        
        pageviews = [p.total_pageviews for p in posts if p.total_pageviews > 0]
        times = [p.avg_time_on_page for p in posts if p.avg_time_on_page > 0]
        
        if not pageviews:
            return {"insufficient_data": True}
        
        pageviews.sort()
        times.sort()
        
        def percentile(data: List, p: float) -> float:
            k = (len(data) - 1) * p
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f])
        
        return {
            "pageviews": {
                "median": percentile(pageviews, 0.5),
                "top_25": percentile(pageviews, 0.75),
                "top_10": percentile(pageviews, 0.9),
                "average": sum(pageviews) / len(pageviews)
            },
            "time_on_page": {
                "median": percentile(times, 0.5) if times else 0,
                "top_25": percentile(times, 0.75) if times else 0,
                "average": sum(times) / len(times) if times else 0
            },
            "total_posts_analyzed": len(posts)
        }
    
    def get_comprehensive_insights(self) -> Dict[str, Any]:
        """
        Get all insights in a single call
        
        Useful for the analytics dashboard.
        """
        return {
            "title_patterns": [
                {"name": p.name, "description": p.description, "impact": p.impact_score}
                for p in self.analyze_title_patterns()
            ],
            "tag_trends": [
                {"tag": t.name, "direction": t.direction, "change": t.change_percent}
                for t in self.analyze_tag_trends()[:10]
            ],
            "content_gaps": [
                {"topic": g.topic, "reason": g.reason, "value": g.potential_value}
                for g in self.identify_content_gaps()[:10]
            ],
            "posting_times": self.get_optimal_posting_times(),
            "benchmarks": self.get_performance_benchmarks(),
            "store_summary": self.store.get_stats_summary(),
            "content_correlations": self.analyze_content_correlations()
        }
    
    def analyze_content_correlations(self) -> Dict[str, Any]:
        """
        Analyze what content attributes correlate with success
        
        This is the real AI insight - finding patterns in:
        - Title length vs performance
        - Tag count vs performance
        - Specific tags vs performance
        - Publishing day/time vs performance
        """
        top_posts = self.store.get_top_posts(limit=50)
        
        if len(top_posts) < 10:
            return {"error": "Not enough data for correlation analysis"}
        
        # Categorize posts by performance
        avg_views = sum(p.total_pageviews for p in top_posts) / len(top_posts)
        high_performers = [p for p in top_posts if p.total_pageviews > avg_views * 1.5]
        low_performers = [p for p in top_posts if p.total_pageviews < avg_views * 0.5]
        
        correlations = {}
        
        # 1. Title Length Correlation
        if high_performers and low_performers:
            avg_title_high = sum(len(p.title or '') for p in high_performers) / len(high_performers)
            avg_title_low = sum(len(p.title or '') for p in low_performers) / len(low_performers)
            correlations["title_length"] = {
                "high_performers_avg": round(avg_title_high),
                "low_performers_avg": round(avg_title_low),
                "insight": f"High performers average {int(avg_title_high)} chars, low performers {int(avg_title_low)} chars"
            }
        
        # 2. Tag Analysis - which tags correlate with success
        tag_performance = {}
        for post in top_posts:
            if hasattr(post, 'tags') and post.tags:
                for tag in post.tags:
                    if tag not in tag_performance:
                        tag_performance[tag] = {"total_views": 0, "post_count": 0}
                    tag_performance[tag]["total_views"] += post.total_pageviews
                    tag_performance[tag]["post_count"] += 1
        
        # Calculate avg views per tag
        for tag, data in tag_performance.items():
            data["avg_views"] = data["total_views"] / data["post_count"] if data["post_count"] > 0 else 0
        
        # Sort by avg views
        sorted_tags = sorted(tag_performance.items(), key=lambda x: x[1]["avg_views"], reverse=True)
        
        correlations["best_tags"] = [
            {"tag": tag, "avg_views": round(data["avg_views"]), "post_count": data["post_count"]}
            for tag, data in sorted_tags[:5]
            if data["post_count"] >= 2  # Only tags with multiple posts
        ]
        
        correlations["worst_tags"] = [
            {"tag": tag, "avg_views": round(data["avg_views"]), "post_count": data["post_count"]}
            for tag, data in sorted_tags[-5:]
            if data["post_count"] >= 2
        ]
        
        # 3. Title Word Patterns
        title_words = {}
        for post in high_performers:
            if post.title:
                words = post.title.lower().split()
                for word in words:
                    if len(word) > 3:  # Skip short words
                        if word not in title_words:
                            title_words[word] = 0
                        title_words[word] += 1
        
        # Most common words in high-performing titles
        common_words = sorted(title_words.items(), key=lambda x: x[1], reverse=True)[:10]
        correlations["successful_title_words"] = [word for word, count in common_words if count >= 2]
        
        # 4. Time on Page Correlation
        if high_performers:
            avg_time_high = sum(p.avg_time_on_page for p in high_performers) / len(high_performers)
            avg_time_low = sum(p.avg_time_on_page for p in low_performers) / len(low_performers) if low_performers else 0
            correlations["engagement"] = {
                "high_performers_avg_time": round(avg_time_high),
                "low_performers_avg_time": round(avg_time_low),
                "insight": f"High performers get {int(avg_time_high)}s avg read time vs {int(avg_time_low)}s for low performers"
            }
        
        return correlations

