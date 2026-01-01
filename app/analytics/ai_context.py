# app/analytics/ai_context.py
"""
AI Context Generator

Generates rich context for AI assistants based on analytics data.
This enables AI to make data-informed content recommendations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudienceProfile:
    """Profile of the blog's audience"""
    top_countries: List[Dict[str, Any]]
    top_referrers: List[Dict[str, Any]]
    avg_time_on_site: float
    pages_per_visit: float


@dataclass
class ContentProfile:
    """Profile of successful content on this blog"""
    optimal_length_words: int
    best_performing_tags: List[str]
    title_patterns: List[str]
    avg_time_on_page: float
    best_publish_day: Optional[str]


@dataclass
class AIContext:
    """Complete context package for AI content generation"""
    audience: AudienceProfile
    content: ContentProfile
    recent_performance: Dict[str, Any]
    content_gaps: List[Dict[str, Any]]
    trending_topics: List[Dict[str, Any]]
    blog_identity: Dict[str, Any]
    
    def to_system_prompt(self) -> str:
        """Convert context to a system prompt for AI"""
        return self._format_as_prompt()
    
    def _format_as_prompt(self) -> str:
        """Format context as natural language for AI consumption"""
        lines = []
        
        lines.append("=== BLOG ANALYTICS CONTEXT ===\n")
        
        # Audience section
        lines.append("AUDIENCE INSIGHTS:")
        if self.audience.top_countries:
            countries = ", ".join(
                f"{c['name']} ({c['percentage']:.0f}%)" 
                for c in self.audience.top_countries[:5]
            )
            lines.append(f"  • Top countries: {countries}")
        
        if self.audience.top_referrers:
            referrers = ", ".join(r['label'] for r in self.audience.top_referrers[:3])
            lines.append(f"  • Traffic sources: {referrers}")
        
        if self.audience.avg_time_on_site > 0:
            minutes = self.audience.avg_time_on_site / 60
            lines.append(f"  • Avg session: {minutes:.1f} minutes, {self.audience.pages_per_visit:.1f} pages/visit")
        
        lines.append("")
        
        # Content patterns
        lines.append("WHAT WORKS ON THIS BLOG:")
        if self.content.best_performing_tags:
            tags = ", ".join(f"#{t}" for t in self.content.best_performing_tags[:5])
            lines.append(f"  • Best performing tags: {tags}")
        
        if self.content.title_patterns:
            patterns = "; ".join(self.content.title_patterns[:3])
            lines.append(f"  • Successful title patterns: {patterns}")
        
        if self.content.best_publish_day:
            lines.append(f"  • Best day to publish: {self.content.best_publish_day}")
        
        if self.content.avg_time_on_page > 0:
            lines.append(f"  • Avg reading time: {self.content.avg_time_on_page / 60:.1f} minutes")
        
        lines.append("")
        
        # Trending topics
        if self.trending_topics:
            lines.append("TRENDING TOPICS (rising interest):")
            for topic in self.trending_topics[:5]:
                if topic.get('direction') == 'rising':
                    lines.append(f"  • #{topic['tag']} (+{topic['change']:.0f}%)")
            lines.append("")
        
        # Content gaps
        if self.content_gaps:
            lines.append("CONTENT OPPORTUNITIES:")
            for gap in self.content_gaps[:5]:
                lines.append(f"  • {gap['topic']}: {gap['reason']}")
            lines.append("")
        
        # Recent performance
        if self.recent_performance:
            lines.append("RECENT PERFORMANCE:")
            if 'top_posts' in self.recent_performance:
                lines.append("  Top performing posts (last 30 days):")
                for post in self.recent_performance['top_posts'][:3]:
                    lines.append(f"    - {post['title']} ({post['views']} views)")
            lines.append("")
        
        # Blog identity
        if self.blog_identity:
            lines.append("BLOG IDENTITY:")
            if self.blog_identity.get('name'):
                lines.append(f"  • Name: {self.blog_identity['name']}")
            if self.blog_identity.get('description'):
                lines.append(f"  • Focus: {self.blog_identity['description']}")
            if self.blog_identity.get('total_posts'):
                lines.append(f"  • Total posts: {self.blog_identity['total_posts']}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "audience": {
                "top_countries": self.audience.top_countries,
                "top_referrers": self.audience.top_referrers,
                "avg_time_on_site": self.audience.avg_time_on_site,
                "pages_per_visit": self.audience.pages_per_visit
            },
            "content": {
                "best_tags": self.content.best_performing_tags,
                "title_patterns": self.content.title_patterns,
                "best_publish_day": self.content.best_publish_day,
                "avg_reading_time_seconds": self.content.avg_time_on_page
            },
            "recent_performance": self.recent_performance,
            "content_gaps": self.content_gaps,
            "trending_topics": self.trending_topics,
            "blog_identity": self.blog_identity
        }


class AIContextGenerator:
    """
    Generates rich context for AI assistants
    
    Combines data from Matomo, stored analytics, and content analysis
    to provide AI with comprehensive understanding of what works.
    """
    
    def __init__(self):
        from . import get_matomo_client, get_analytics_store, get_insights_engine
        self.matomo = get_matomo_client()
        self.store = get_analytics_store()
        self.insights = get_insights_engine()
    
    def _get_audience_profile(self) -> AudienceProfile:
        """Build audience profile from analytics"""
        countries = []
        referrers = []
        avg_time = 0.0
        pages_per_visit = 0.0
        
        if self.matomo.is_configured:
            # Get country data
            country_data = self.matomo.get_countries(period="month", date="today", limit=10)
            total_visits = sum(c.visits for c in country_data)
            
            for c in country_data:
                percentage = (c.visits / total_visits * 100) if total_visits > 0 else 0
                countries.append({
                    "code": c.country_code,
                    "name": c.country_name,
                    "visits": c.visits,
                    "percentage": percentage
                })
            
            # Get referrer data
            referrer_data = self.matomo.get_referrers(period="month", date="today", limit=10)
            for r in referrer_data:
                referrers.append({
                    "type": r.referrer_type,
                    "label": r.label,
                    "visits": r.visits
                })
            
            # Get summary metrics
            summary = self.matomo.get_summary(period="month", date="today")
            avg_time = summary.avg_visit_duration
            pages_per_visit = summary.pages_per_visit
        
        return AudienceProfile(
            top_countries=countries,
            top_referrers=referrers,
            avg_time_on_site=avg_time,
            pages_per_visit=pages_per_visit
        )
    
    def _get_content_profile(self) -> ContentProfile:
        """Build content profile from successful posts"""
        best_tags = []
        title_patterns = []
        avg_time = 0.0
        best_day = None
        
        # Get best performing tags
        top_tags = self.store.get_top_tags(limit=10)
        best_tags = [t.tag for t in top_tags]
        
        # Get title patterns from insights
        patterns = self.insights.analyze_title_patterns()
        title_patterns = [p.description for p in patterns if p.impact_score > 0.3]
        
        # Get optimal posting times
        timing = self.insights.get_optimal_posting_times()
        best_day = timing.get('best_day')
        
        # Get average reading time
        benchmarks = self.insights.get_performance_benchmarks()
        if 'time_on_page' in benchmarks:
            avg_time = benchmarks['time_on_page'].get('average', 0)
        
        return ContentProfile(
            optimal_length_words=1500,  # Default, could be computed from content
            best_performing_tags=best_tags,
            title_patterns=title_patterns,
            avg_time_on_page=avg_time,
            best_publish_day=best_day
        )
    
    def _get_recent_performance(self) -> Dict[str, Any]:
        """Get recent performance metrics"""
        top_posts = self.store.get_top_posts(limit=10)
        
        return {
            "top_posts": [
                {
                    "path": p.path,
                    "title": p.title,
                    "views": p.total_pageviews,
                    "visitors": p.total_visitors
                }
                for p in top_posts
            ],
            "total_tracked": len(self.store.get_all_post_analytics())
        }
    
    def _get_blog_identity(self) -> Dict[str, Any]:
        """Get blog identity information"""
        try:
            from app.settings import settings
            
            # Count posts
            total_posts = 0
            try:
                from app.content import ContentManager
                cm = ContentManager(settings.content_dir)
                total_posts = len(cm.get_pages_by_status("public"))
            except Exception:
                pass
            
            return {
                "name": settings.site_name,
                "description": settings.site_description,
                "url": settings.site_url,
                "author": settings.author_name,
                "total_posts": total_posts
            }
        except Exception:
            return {}
    
    def generate_context(self, include_details: bool = True) -> AIContext:
        """
        Generate complete AI context
        
        Args:
            include_details: Include detailed analytics (set False for faster/smaller context)
            
        Returns:
            AIContext object with all data
        """
        logger.info("Generating AI context from analytics...")
        
        # Get all component data
        audience = self._get_audience_profile()
        content = self._get_content_profile()
        recent = self._get_recent_performance() if include_details else {}
        
        # Get insights
        insights = self.insights.get_comprehensive_insights()
        
        content_gaps = insights.get('content_gaps', [])
        trending = insights.get('tag_trends', [])
        
        # Build identity
        identity = self._get_blog_identity()
        
        return AIContext(
            audience=audience,
            content=content,
            recent_performance=recent,
            content_gaps=content_gaps,
            trending_topics=trending,
            blog_identity=identity
        )
    
    def get_content_suggestion_prompt(self, topic: Optional[str] = None) -> str:
        """
        Generate a prompt for AI to suggest content topics
        
        Args:
            topic: Optional specific topic area to focus on
            
        Returns:
            Complete system prompt for content suggestion
        """
        context = self.generate_context()
        base_prompt = context.to_system_prompt()
        
        task_prompt = """
Based on the analytics context above, suggest content topics that would likely perform well.

Consider:
1. Topics that align with proven successful patterns
2. Content gaps that represent opportunities
3. Trending topics that show rising interest
4. Audience demographics and interests

For each suggestion, explain WHY it would likely succeed based on the data.
"""
        
        if topic:
            task_prompt += f"\nFocus specifically on content related to: {topic}\n"
        
        return base_prompt + "\n" + task_prompt
    
    def get_title_optimization_prompt(self, draft_title: str) -> str:
        """
        Generate a prompt for AI to optimize a title
        
        Args:
            draft_title: The draft title to optimize
            
        Returns:
            System prompt for title optimization
        """
        context = self.generate_context(include_details=False)
        base_prompt = context.to_system_prompt()
        
        task_prompt = f"""
Optimize this draft title for better performance:

DRAFT TITLE: "{draft_title}"

Based on the successful title patterns identified above, suggest 3-5 alternative titles that:
1. Follow proven patterns from this blog's top performers
2. Are likely to attract the blog's audience
3. Maintain the original meaning/topic
4. Are optimized for shareability and SEO

For each suggestion, briefly explain which pattern it follows.
"""
        
        return base_prompt + "\n" + task_prompt
    
    def get_content_review_prompt(self, content_summary: str, tags: List[str]) -> str:
        """
        Generate a prompt for AI to review content before publishing
        
        Args:
            content_summary: Brief summary of the content
            tags: Proposed tags
            
        Returns:
            System prompt for content review
        """
        context = self.generate_context(include_details=False)
        base_prompt = context.to_system_prompt()
        
        tags_str = ", ".join(f"#{t}" for t in tags) if tags else "none specified"
        
        task_prompt = f"""
Review this content before publishing:

SUMMARY: {content_summary}
PROPOSED TAGS: {tags_str}

Based on the analytics context, provide feedback on:
1. How well this aligns with what performs on this blog
2. Tag suggestions (add/remove based on what's trending)
3. Potential title improvements
4. Best timing to publish
5. Any audience considerations
"""
        
        return base_prompt + "\n" + task_prompt

