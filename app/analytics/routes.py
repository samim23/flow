# app/analytics/routes.py
"""
Analytics Routes

Provides the analytics dashboard and API endpoints.
All routes are optional and only enabled if analytics is configured.
"""

import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_analytics_template_context(request: Request, context: dict = None) -> dict:
    """Build template context for analytics pages"""
    from app.settings import settings
    
    base_context = {
        "request": request,
        "app": settings,
        "freeze": 0,
        "is_authenticated": True,  # Analytics only shown to authenticated users
        "is_live_mode": bool(settings.admin_password)
    }
    
    if context:
        base_context.update(context)
    
    return base_context


# Valid date ranges for the dashboard
DATE_RANGES = {
    "7d": {"days": 7, "label": "Last 7 Days"},
    "30d": {"days": 30, "label": "Last 30 Days"},
    "90d": {"days": 90, "label": "Last 90 Days"},
    "365d": {"days": 365, "label": "Last Year"},
}


@analytics_router.get("/", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    range: str = Query("30d", description="Date range: 7d, 30d, 90d, 365d")
):
    """
    Main analytics dashboard
    
    Shows comprehensive overview of blog performance.
    
    Query params:
    - range: Date range for analytics (7d, 30d, 90d, 365d)
    """
    from . import get_matomo_client, get_analytics_store, get_insights_engine
    from app.routes import is_authenticated, is_live_mode
    
    # Check authentication in live mode
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Validate and get date range
    if range not in DATE_RANGES:
        range = "30d"
    days = DATE_RANGES[range]["days"]
    
    matomo = get_matomo_client()
    store = get_analytics_store()
    insights = get_insights_engine()
    
    # Gather data - use cached summary if available to reduce lag
    is_configured = matomo.is_configured
    summary = matomo.get_summary(period="range", days=days) if is_configured else None
    
    # Get NEW AI optimization data
    wow_comparison = matomo.get_week_over_week_comparison() if is_configured else None
    trending_content = matomo.get_trending_content(limit=5) if is_configured else []
    search_keywords = matomo.get_search_keywords(days=days, limit=10) if is_configured else []
    
    # Get referral/social data
    referrer_types = matomo.get_referrer_types(days=days) if is_configured else {}
    social_networks = matomo.get_social_networks(days=days, limit=5) if is_configured else []
    referring_websites = matomo.get_referring_websites(days=days, limit=5) if is_configured else []
    
    # Get historical trends
    monthly_trends = matomo.get_monthly_trends(months=12) if is_configured else []
    
    # Get content correlations
    content_correlations = insights.analyze_content_correlations() if is_configured else {}
    
    # Generate AI recommendations
    recommendations = []
    if is_configured and wow_comparison:
        tag_trends_for_recs = insights.analyze_tag_trends()
        content_gaps_for_recs = insights.identify_content_gaps()
        recommendations = _generate_recommendations(
            wow_comparison, trending_content, search_keywords, 
            tag_trends_for_recs, content_gaps_for_recs
        )
    
    # Get insights
    top_posts = store.get_top_posts(limit=15)
    top_tags = store.get_top_tags(limit=15)
    tag_trends = insights.analyze_tag_trends()
    content_gaps = insights.identify_content_gaps()
    title_patterns = insights.analyze_title_patterns()
    benchmarks = insights.get_performance_benchmarks()
    timing = insights.get_optimal_posting_times()
    store_summary = store.get_stats_summary()
    
    # Get experiments and goals
    from .experiments import get_experiment_manager
    exp_manager = get_experiment_manager()
    experiments = exp_manager.get_experiments()
    goals = exp_manager.get_goals()
    
    # Find primary goal (highest priority, in progress)
    primary_goal = None
    for g in goals:
        if g.status == "in_progress":
            primary_goal = g
            break
    
    # Generate prioritized actions
    prioritized_actions = _generate_prioritized_actions(
        wow_comparison, trending_content, search_keywords,
        tag_trends, content_gaps, experiments, goals
    )
    
    # Get top action for banner
    next_action = prioritized_actions[0] if prioritized_actions else None
    
    # Prepare data for template
    context = {
        "pageTitle": "Analytics Dashboard",
        "is_configured": is_configured,
        "summary": summary,
        "top_posts": top_posts,
        "top_tags": top_tags,
        "tag_trends": [t for t in tag_trends if t.direction in ('rising', 'falling')][:10],
        "content_gaps": content_gaps[:8],
        "title_patterns": title_patterns[:5],
        "benchmarks": benchmarks,
        "timing": timing,
        "store_summary": store_summary,
        "last_sync": store_summary.get('last_sync'),
        # Date range selection
        "current_range": range,
        "date_ranges": DATE_RANGES,
        "days": days,
        # NEW: AI optimization data
        "wow_comparison": wow_comparison,
        "trending_content": trending_content,
        "search_keywords": search_keywords,
        "recommendations": recommendations,
        # Traffic sources
        "referrer_types": referrer_types,
        "social_networks": social_networks,
        "referring_websites": referring_websites,
        # Historical trends
        "monthly_trends": monthly_trends,
        # Content correlations
        "content_correlations": content_correlations,
        # Experiments and goals
        "experiments": experiments,
        "goals": goals,
        # Health banner data
        "primary_goal": primary_goal,
        "next_action": next_action,
        "prioritized_actions": prioritized_actions,
    }
    
    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        get_analytics_template_context(request, context)
    )


@analytics_router.get("/post/{path:path}", response_class=HTMLResponse)
async def post_detail(request: Request, path: str):
    """
    Detailed analytics for a specific post.
    
    Shows referrers, historical trends, and comparison to benchmarks.
    """
    from . import get_analytics_store, get_matomo_client, get_insights_engine
    from app.routes import is_authenticated, is_live_mode
    from datetime import datetime, timedelta
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    store = get_analytics_store()
    matomo = get_matomo_client()
    insights = get_insights_engine()
    
    # Get post analytics from store
    post = store.get_post_analytics(path)
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found in analytics")
    
    # Get referrers for this post
    referrers = []
    if matomo.is_configured:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        date_range = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        try:
            data = matomo._api_request(
                "Referrers.getAll",
                {
                    "period": "range",
                    "date": date_range,
                    "segment": f"pageUrl=@/p/{path}/",
                    "filter_limit": 20
                }
            )
            
            if data and isinstance(data, list):
                for item in data:
                    referrers.append({
                        "referrer": item.get("label", "Unknown"),
                        "visits": item.get("nb_visits", 0),
                        "pageviews": item.get("nb_actions", 0)
                    })
        except Exception as e:
            logger.warning(f"Failed to get referrers for {path}: {e}")
    
    # Get historical trend
    history = []
    lifecycle = "unknown"
    if matomo.is_configured:
        try:
            history = matomo.get_content_performance_history(path, months=6)
            if history and len(history) >= 2:
                lifecycle = "growing" if history[-1].get("pageviews", 0) > history[0].get("pageviews", 0) else "declining"
        except Exception as e:
            logger.warning(f"Failed to get history for {path}: {e}")
    
    # Get benchmarks for comparison
    benchmarks = insights.get_performance_benchmarks()
    
    context = {
        "pageTitle": f"Post Analytics: {post.title or path}",
        "post": post,
        "referrers": referrers,
        "history": history,
        "lifecycle": lifecycle,
        "benchmarks": benchmarks if not benchmarks.get("insufficient_data") else None,
    }
    
    return request.app.state.templates.TemplateResponse(
        "post_detail.html",
        get_analytics_template_context(request, context)
    )


@analytics_router.get("/sync")
async def sync_analytics(request: Request):
    """
    Sync analytics data from Matomo
    
    Fetches latest data and updates local store.
    """
    from . import get_analytics_store
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    store = get_analytics_store()
    
    try:
        updated = store.sync_from_matomo(request.app.state.content_manager)
        return JSONResponse({
            "status": "success",
            "message": f"Synced analytics for {updated} posts"
        })
    except Exception as e:
        logger.error(f"Analytics sync failed: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@analytics_router.get("/api/summary")
async def api_summary(
    request: Request,
    period: str = Query("month", description="Time period: day, week, month, year"),
    date: str = Query("today", description="Date reference")
):
    """API endpoint for analytics summary"""
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return JSONResponse({"error": "Analytics not configured"}, status_code=503)
    
    summary = matomo.get_summary(period=period, date=date)
    
    return {
        "period": period,
        "date": date,
        "total_visits": summary.total_visits,
        "unique_visitors": summary.unique_visitors,
        "pageviews": summary.total_pageviews,
        "avg_duration": summary.avg_visit_duration,
        "bounce_rate": summary.bounce_rate,
        "pages_per_visit": summary.pages_per_visit,
        "top_pages": [
            {"path": p.path, "title": p.label, "views": p.pageviews}
            for p in summary.top_pages[:10]
        ],
        "top_countries": [
            {"code": c.country_code, "name": c.country_name, "visits": c.visits}
            for c in summary.top_countries[:10]
        ]
    }


@analytics_router.get("/api/post/{path:path}")
async def api_post_stats(request: Request, path: str):
    """API endpoint for single post analytics"""
    from . import get_matomo_client, get_analytics_store
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Try local store first
    store = get_analytics_store()
    stored = store.get_post_analytics(path)
    
    # Then try Matomo for fresh data
    matomo = get_matomo_client()
    live_stats = None
    if matomo.is_configured:
        live_stats = matomo.get_page_stats(path, period="month", date="today")
    
    if not stored and not live_stats:
        return JSONResponse({"error": "No analytics found for this post"}, status_code=404)
    
    return {
        "path": path,
        "stored": {
            "total_pageviews": stored.total_pageviews if stored else 0,
            "total_visitors": stored.total_visitors if stored else 0,
            "avg_time": stored.avg_time_on_page if stored else 0,
            "last_updated": stored.last_updated.isoformat() if stored and stored.last_updated else None
        } if stored else None,
        "live": {
            "pageviews": live_stats.pageviews if live_stats else 0,
            "visitors": live_stats.unique_visitors if live_stats else 0,
            "avg_time": live_stats.avg_time_on_page if live_stats else 0,
            "bounce_rate": live_stats.bounce_rate if live_stats else 0
        } if live_stats else None
    }


@analytics_router.get("/api/insights")
async def api_insights(request: Request):
    """API endpoint for content insights"""
    from . import get_insights_engine
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    insights = get_insights_engine()
    return insights.get_comprehensive_insights()


@analytics_router.get("/api/ai-context")
async def api_ai_context(request: Request, format: str = Query("json", description="Output format: json or prompt")):
    """
    API endpoint for AI context
    
    Returns analytics context formatted for AI consumption.
    """
    from . import get_ai_context
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    generator = get_ai_context()
    context = generator.generate_context()
    
    if format == "prompt":
        return {"prompt": context.to_system_prompt()}
    else:
        return context.to_dict()


@analytics_router.get("/api/realtime")
async def api_realtime(request: Request):
    """API endpoint for realtime visitor count"""
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return {"visitors": 0, "configured": False}
    
    count = matomo.get_realtime_visitors(last_minutes=30)
    return {"visitors": count, "configured": True, "window_minutes": 30}


@analytics_router.get("/api/popular")
async def api_popular(
    request: Request,
    days: int = Query(30, description="Number of days to analyze")
):
    """
    Get popular posts for sidebar display.
    
    Used by the homepage sidebar in dev mode to show popular posts.
    Returns top posts by pageviews over the specified period.
    Respects sidebar-popular.txt config for pinning and exclusions.
    """
    from . import get_matomo_client, get_analytics_store
    from app.sidebar_config import SidebarConfig, filter_popular_posts
    
    matomo = get_matomo_client()
    store = get_analytics_store()
    config = SidebarConfig.load()
    
    # Get content manager for validation
    content_manager = request.app.state.content_manager
    
    algo_posts = []
    source = "cache"
    
    if matomo.is_configured:
        source = "matomo"
        # Get top pages from Matomo (fetch more to allow for filtering)
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        date_range = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
        
        top_pages = matomo.get_top_pages(period="range", date=date_range, limit=50)
        
        for page in top_pages:
            post_analytics = store.get_post_analytics(page.path)
            title = post_analytics.title if post_analytics else page.label
            algo_posts.append({
                "path": page.path,
                "title": title or page.path,
                "pageviews": page.pageviews
            })
    else:
        # Fall back to store data if available
        top_posts = store.get_top_posts(limit=50)
        if top_posts:
            algo_posts = [
                {"path": p.path, "title": p.title, "pageviews": p.total_pageviews}
                for p in top_posts
            ]
    
    # Filter and order using config (pinned, exclusions, validation)
    # Return full pool for client-side shuffling
    from app.sidebar_config import SIDEBAR_POPULAR_POOL
    filtered = filter_popular_posts(
        algo_posts,
        content_manager,
        config,
        limit=SIDEBAR_POPULAR_POOL
    )
    
    return {
        "posts": filtered,
        "days": days,
        "source": source,
        "configured": matomo.is_configured
    }


@analytics_router.get("/api/trends")
async def api_trends(request: Request):
    """
    Week-over-week trend comparison
    
    Essential for AI to understand if content strategy is working.
    """
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return {"error": "Matomo not configured", "configured": False}
    
    return {
        "comparison": matomo.get_week_over_week_comparison(),
        "trending_content": matomo.get_trending_content(limit=10),
        "configured": True
    }


@analytics_router.get("/api/search-keywords")
async def api_search_keywords(
    request: Request,
    days: int = Query(30, description="Number of days to analyze")
):
    """
    Search keywords that brought traffic
    
    Critical for understanding what topics people search for.
    """
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return {"keywords": [], "configured": False}
    
    keywords = matomo.get_search_keywords(days=days, limit=30)
    return {
        "keywords": keywords,
        "days": days,
        "configured": True
    }


@analytics_router.get("/api/content-optimization")
async def api_content_optimization(request: Request):
    """
    Comprehensive content optimization data for AI agents
    
    Combines all insights needed to make content recommendations.
    """
    from . import get_matomo_client, get_analytics_store, get_insights_engine
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    store = get_analytics_store()
    insights = get_insights_engine()
    
    if not matomo.is_configured:
        return {"error": "Matomo not configured", "configured": False}
    
    # Gather all optimization data
    wow = matomo.get_week_over_week_comparison()
    trending = matomo.get_trending_content(limit=10)
    keywords = matomo.get_search_keywords(days=30, limit=20)
    top_posts = store.get_top_posts(limit=20)
    tag_trends = insights.analyze_tag_trends()
    content_gaps = insights.identify_content_gaps()
    title_patterns = insights.analyze_title_patterns()
    timing = insights.get_optimal_posting_times()
    
    return {
        "traffic_trend": {
            "direction": wow["changes"]["direction"],
            "visits_change": f"{wow['changes']['visits']:+.1f}%",
            "pageviews_change": f"{wow['changes']['pageviews']:+.1f}%",
            "is_growing": wow["changes"]["visits"] > 0
        },
        "trending_content": [
            {"title": t["label"], "momentum": t["momentum"], "change": f"{t['change_percent']:+.1f}%"}
            for t in trending[:5]
        ],
        "search_keywords": [k["keyword"] for k in keywords[:10] if k["keyword"]],
        "top_performing_posts": [
            {"title": p.title, "views": p.total_pageviews, "path": p.path}
            for p in top_posts[:10]
        ],
        "rising_topics": [
            t.name for t in tag_trends if t.direction == "rising"
        ][:5],
        "falling_topics": [
            t.name for t in tag_trends if t.direction == "falling"
        ][:5],
        "content_gaps": [
            {"topic": g.topic, "reason": g.reason, "value": g.potential_value}
            for g in content_gaps[:5]
        ],
        "title_patterns_that_work": [
            {"pattern": p.name, "description": p.description}
            for p in title_patterns[:3]
        ],
        "best_publishing_day": timing.get("best_day", "unknown") if timing else "unknown",
        "recommendations": _generate_recommendations(wow, trending, keywords, tag_trends, content_gaps)
    }


def _generate_recommendations(wow, trending, keywords, tag_trends, content_gaps) -> List[str]:
    """Generate actionable recommendations based on all data"""
    recommendations = []
    
    # Traffic trend recommendation
    if wow["changes"]["visits"] < -10:
        recommendations.append("⚠️ Traffic is declining. Consider publishing more frequently or promoting recent content.")
    elif wow["changes"]["visits"] > 20:
        recommendations.append("🚀 Traffic is surging! Double down on recent successful topics.")
    
    # Trending content recommendation
    if trending:
        top_trending = trending[0]
        recommendations.append(f"📈 '{top_trending['label'][:50]}...' is hot ({top_trending['momentum']}). Consider follow-up content.")
    
    # Search keyword opportunity
    if keywords:
        top_keywords = [k["keyword"] for k in keywords[:3] if k["keyword"]]
        if top_keywords:
            recommendations.append(f"🔍 Top search terms: {', '.join(top_keywords)}. Ensure content covers these topics.")
    
    # Rising topics
    rising = [t for t in tag_trends if t.direction == "rising"]
    if rising:
        recommendations.append(f"🌱 Rising topics: {', '.join([t.name for t in rising[:3]])}. Good candidates for new content.")
    
    # Content gaps
    high_value_gaps = [g for g in content_gaps if g.potential_value == "high"]
    if high_value_gaps:
        recommendations.append(f"💡 High-value gap: {high_value_gaps[0].topic} - {high_value_gaps[0].reason}")
    
    return recommendations[:5]  # Limit to 5 actionable recommendations


def _generate_prioritized_actions(wow, trending, keywords, tag_trends, content_gaps, experiments, goals) -> List[dict]:
    """
    Generate prioritized actions with clear priority levels.
    
    Returns list of {priority: high/medium/low, action: str, reason: str}
    """
    actions = []
    
    # HIGH PRIORITY: Traffic is crashing
    if wow and wow.get("changes", {}).get("visits", 0) < -20:
        actions.append({
            "priority": "high",
            "action": "Publish new content immediately",
            "reason": f"Traffic down {abs(wow['changes']['visits']):.0f}% week-over-week"
        })
    
    # HIGH PRIORITY: Goal at risk
    for goal in goals:
        if goal.status == "in_progress" and goal.days_remaining >= 0:
            days_passed = 90 - goal.days_remaining  # Assume 90-day goal window
            expected_progress = (days_passed / 90) * 100 if days_passed > 0 else 0
            if goal.progress_percent < expected_progress * 0.7:  # Behind by 30%+
                actions.append({
                    "priority": "high",
                    "action": f"Goal '{goal.title}' at risk",
                    "reason": f"At {goal.progress_percent:.0f}% with {goal.days_remaining} days left"
                })
                break
    
    # HIGH PRIORITY: Content gap with high value
    high_gaps = [g for g in content_gaps if g.potential_value == "high"]
    if high_gaps:
        actions.append({
            "priority": "high",
            "action": f"Create content about: {high_gaps[0].topic}",
            "reason": high_gaps[0].reason
        })
    
    # MEDIUM PRIORITY: Trending content opportunity
    if trending and len(trending) > 0:
        top = trending[0]
        actions.append({
            "priority": "medium",
            "action": f"Write follow-up to '{top['label'][:40]}...'",
            "reason": f"Hot content with {top['momentum']} momentum (+{top['change_percent']:.0f}%)"
        })
    
    # MEDIUM PRIORITY: Rising topics
    rising = [t for t in tag_trends if t.direction == "rising"][:2]
    if rising:
        topic_names = ", ".join([t.name for t in rising])
        actions.append({
            "priority": "medium", 
            "action": f"Publish more about: {topic_names}",
            "reason": "These topics are trending upward in engagement"
        })
    
    # MEDIUM PRIORITY: Search keywords not covered
    if keywords:
        uncovered = [k["keyword"] for k in keywords[:3] if k.get("keyword") and k["keyword"] != "Keyword not defined"]
        if uncovered:
            actions.append({
                "priority": "medium",
                "action": f"Cover search terms: {', '.join(uncovered[:2])}",
                "reason": "People are searching for these topics"
            })
    
    # LOW PRIORITY: Traffic is up (double down)
    if wow and wow.get("changes", {}).get("visits", 0) > 15:
        actions.append({
            "priority": "low",
            "action": "Double down on recent content style",
            "reason": f"Traffic up {wow['changes']['visits']:.0f}% - keep momentum"
        })
    
    # LOW PRIORITY: Running experiments
    running_exps = [e for e in experiments if e.status == "running"]
    if running_exps:
        exp = running_exps[0]
        actions.append({
            "priority": "low",
            "action": f"Monitor experiment: {exp.title}",
            "reason": f"Day {exp.days_running} - check metrics"
        })
    
    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda x: priority_order.get(x["priority"], 1))
    
    return actions[:5]


# =====================================================
# NEW API ENDPOINTS FOR AI AGENT OPTIMIZATION
# =====================================================

@analytics_router.get("/api/referrers")
async def api_referrers(
    request: Request,
    days: int = Query(30, description="Number of days to analyze")
):
    """
    Get traffic sources breakdown
    
    Shows where traffic comes from: direct, search, social, websites.
    """
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return {"error": "Matomo not configured", "configured": False}
    
    return {
        "referrer_types": matomo.get_referrer_types(days=days),
        "social_networks": matomo.get_social_networks(days=days, limit=10),
        "websites": matomo.get_referring_websites(days=days, limit=15),
        "days": days,
        "configured": True
    }


@analytics_router.get("/api/historical")
async def api_historical(
    request: Request,
    months: int = Query(12, description="Number of months of history")
):
    """
    Get historical time-series data
    
    Essential for long-term trend analysis.
    """
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return {"error": "Matomo not configured", "configured": False}
    
    monthly_trends = matomo.get_monthly_trends(months=months)
    
    # Calculate growth metrics
    if len(monthly_trends) >= 2:
        first_month = monthly_trends[0]
        last_month = monthly_trends[-1]
        
        if first_month["visits"] > 0:
            growth = ((last_month["visits"] - first_month["visits"]) / first_month["visits"]) * 100
        else:
            growth = 0
    else:
        growth = 0
    
    return {
        "monthly_trends": monthly_trends,
        "months": months,
        "overall_growth": round(growth, 1),
        "trend_direction": "up" if growth > 5 else "down" if growth < -5 else "stable",
        "configured": True
    }


@analytics_router.get("/api/correlations")
async def api_correlations(request: Request):
    """
    Get content attribute correlations
    
    Answers: What makes posts go viral?
    """
    from . import get_insights_engine
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    insights = get_insights_engine()
    correlations = insights.analyze_content_correlations()
    
    return {
        "correlations": correlations,
        "configured": True
    }


@analytics_router.get("/api/post-history/{path:path}")
async def api_post_history(
    request: Request,
    path: str,
    months: int = Query(6, description="Months of history")
):
    """
    Get historical performance for a specific post
    
    Shows content lifecycle: launch → peak → decay
    """
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return {"error": "Matomo not configured", "configured": False}
    
    history = matomo.get_content_performance_history(path, months=months)
    
    # Analyze lifecycle
    if history:
        peak_month = max(history, key=lambda x: x["pageviews"])
        lifecycle = "growing" if history[-1]["pageviews"] > history[0]["pageviews"] else "declining"
    else:
        peak_month = None
        lifecycle = "unknown"
    
    return {
        "path": path,
        "history": history,
        "peak_month": peak_month,
        "lifecycle": lifecycle,
        "configured": True
    }


# =====================================================
# EXPERIMENTS & GOALS TRACKING
# =====================================================

@analytics_router.get("/api/experiments")
async def api_experiments(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    Get all experiments.
    
    Experiments are stored as markdown files in content/experiments/
    """
    from .experiments import get_experiment_manager
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    manager = get_experiment_manager()
    experiments = manager.get_experiments(status=status)
    
    return {
        "experiments": [
            {
                "filename": exp.path.stem,
                "title": exp.title,
                "hypothesis": exp.hypothesis,
                "status": exp.status,
                "start_date": exp.start_date.isoformat() if exp.start_date else None,
                "end_date": exp.end_date.isoformat() if exp.end_date else None,
                "posts": exp.posts,
                "track_metrics": exp.track_metrics,
                "days_running": exp.days_running,
                "is_active": exp.is_active
            }
            for exp in experiments
        ],
        "total": len(experiments),
        "active": len([e for e in experiments if e.is_active])
    }


@analytics_router.get("/api/experiments/{filename}")
async def api_experiment_detail(request: Request, filename: str):
    """Get detailed experiment info including metrics"""
    from .experiments import get_experiment_manager
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    manager = get_experiment_manager()
    exp = manager.get_experiment(filename)
    
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    # Get actual metrics for experiment posts
    metrics = manager.get_experiment_metrics(exp)
    
    return {
        "filename": exp.path.stem,
        "title": exp.title,
        "hypothesis": exp.hypothesis,
        "status": exp.status,
        "start_date": exp.start_date.isoformat() if exp.start_date else None,
        "end_date": exp.end_date.isoformat() if exp.end_date else None,
        "posts": exp.posts,
        "track_metrics": exp.track_metrics,
        "baseline": exp.baseline,
        "days_running": exp.days_running,
        "content": exp.content,
        "metrics": metrics
    }


@analytics_router.get("/api/goals")
async def api_goals(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    Get all goals.
    
    Goals are stored as markdown files in content/goals/
    """
    from .experiments import get_experiment_manager
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    manager = get_experiment_manager()
    goals = manager.get_goals(status=status)
    
    return {
        "goals": [
            {
                "filename": goal.path.stem,
                "title": goal.title,
                "target_metric": goal.target_metric,
                "target_value": goal.target_value,
                "current_value": goal.current_value,
                "progress_percent": goal.progress_percent,
                "deadline": goal.deadline.isoformat() if goal.deadline else None,
                "days_remaining": goal.days_remaining,
                "status": goal.status,
                "priority": goal.priority
            }
            for goal in goals
        ],
        "total": len(goals),
        "in_progress": len([g for g in goals if g.status == "in_progress"])
    }


@analytics_router.get("/api/goals/{filename}")
async def api_goal_detail(request: Request, filename: str):
    """Get detailed goal info"""
    from .experiments import get_experiment_manager
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    manager = get_experiment_manager()
    goal = manager.get_goal(filename)
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    return {
        "filename": goal.path.stem,
        "title": goal.title,
        "target_metric": goal.target_metric,
        "target_value": goal.target_value,
        "current_value": goal.current_value,
        "progress_percent": goal.progress_percent,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "days_remaining": goal.days_remaining,
        "status": goal.status,
        "priority": goal.priority,
        "content": goal.content
    }


# =====================================================
# WRITE APIs FOR AI AGENT - Close the loop
# =====================================================

@analytics_router.post("/api/experiments/{filename}/complete")
async def api_complete_experiment(
    request: Request,
    filename: str
):
    """
    Mark an experiment as completed and record results.
    
    Body: {
        "results_summary": "Treatment outperformed control by 45%",
        "winner": "treatment" | "control" | null,
        "significance": 0.03
    }
    
    This allows AI agents to close the experiment loop.
    """
    from .experiments import get_experiment_manager
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    results_summary = body.get("results_summary", "")
    winner = body.get("winner")
    significance = body.get("significance")
    
    if not results_summary:
        raise HTTPException(status_code=400, detail="results_summary is required")
    
    # Build results markdown
    results_md = results_summary
    if winner:
        results_md += f"\n\n**Winner:** {winner}"
    if significance is not None:
        results_md += f"\n**Statistical Significance:** p={significance}"
    
    manager = get_experiment_manager()
    success = manager.complete_experiment(
        filename, 
        results_md,
        winner=winner,
        results_summary=results_summary
    )
    
    if success:
        return {
            "status": "completed",
            "filename": filename,
            "message": "Experiment marked as completed with results"
        }
    else:
        raise HTTPException(status_code=404, detail="Experiment not found or update failed")


@analytics_router.patch("/api/goals/{filename}")
async def api_update_goal(
    request: Request,
    filename: str
):
    """
    Update goal progress.
    
    Body: {
        "current_value": 75000
    }
    
    Automatically marks goal as "achieved" when current_value >= target_value.
    """
    from .experiments import get_experiment_manager
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    current_value = body.get("current_value")
    
    if current_value is None:
        raise HTTPException(status_code=400, detail="current_value is required")
    
    try:
        current_value = float(current_value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="current_value must be a number")
    
    manager = get_experiment_manager()
    success = manager.update_goal_progress(filename, current_value)
    
    if success:
        # Get updated goal to return current state
        goal = manager.get_goal(filename)
        return {
            "status": "updated",
            "filename": filename,
            "current_value": current_value,
            "target_value": goal.target_value if goal else None,
            "progress_percent": goal.progress_percent if goal else None,
            "goal_status": goal.status if goal else None
        }
    else:
        raise HTTPException(status_code=404, detail="Goal not found or update failed")


@analytics_router.get("/api/next-action")
async def api_next_action(request: Request):
    """
    Get the single most important action to take right now.
    
    Synthesizes all analytics data into ONE actionable recommendation.
    This is the key API for AI-driven content optimization.
    
    Returns:
    {
        "action": "Publish an ML article about neural architecture search",
        "priority": "high",
        "reason": "ML is trending +45%, you have a content gap, traffic is down",
        "supporting_data": {
            "traffic_trend": "down 15%",
            "top_gap": "Neural Architecture Search",
            "trending_topics": ["ML", "LLMs"]
        }
    }
    """
    from . import get_matomo_client, get_analytics_store, get_insights_engine
    from .experiments import get_experiment_manager
    from app.routes import is_authenticated, is_live_mode
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    insights = get_insights_engine()
    exp_manager = get_experiment_manager()
    
    if not matomo.is_configured:
        return {"error": "Matomo not configured", "configured": False}
    
    # Gather all data
    wow = matomo.get_week_over_week_comparison()
    trending = matomo.get_trending_content(limit=5)
    keywords = matomo.get_search_keywords(days=30, limit=10)
    tag_trends = insights.analyze_tag_trends()
    content_gaps = insights.identify_content_gaps()
    timing = insights.get_optimal_posting_times()
    experiments = exp_manager.get_experiments()
    goals = exp_manager.get_goals()
    
    # Generate prioritized actions
    actions = _generate_prioritized_actions(
        wow, trending, keywords, tag_trends, content_gaps, experiments, goals
    )
    
    if not actions:
        return {
            "action": "Keep creating quality content",
            "priority": "low",
            "reason": "No urgent actions detected - blog is performing well",
            "supporting_data": {}
        }
    
    top_action = actions[0]
    
    # Build supporting data
    supporting_data = {}
    if wow:
        supporting_data["traffic_trend"] = f"{wow['changes']['direction']} {abs(wow['changes']['visits']):.1f}%"
    
    high_gaps = [g for g in content_gaps if g.potential_value == "high"]
    if high_gaps:
        supporting_data["top_gap"] = high_gaps[0].topic
    
    rising = [t for t in tag_trends if t.direction == "rising"][:3]
    if rising:
        supporting_data["trending_topics"] = [t.name for t in rising]
    
    if timing and timing.get("best_day"):
        supporting_data["best_publish_day"] = timing["best_day"]
    
    return {
        "action": top_action["action"],
        "priority": top_action["priority"],
        "reason": top_action["reason"],
        "supporting_data": supporting_data,
        "all_actions": actions[:3],  # Top 3 for context
        "configured": True
    }


@analytics_router.get("/api/post-referrers/{path:path}")
async def api_post_referrers(
    request: Request,
    path: str,
    days: int = Query(30, description="Days to analyze")
):
    """
    Get referrer breakdown for a specific post.
    
    Shows which sources drive traffic to THIS specific post.
    """
    from . import get_matomo_client
    from app.routes import is_authenticated, is_live_mode
    from datetime import datetime, timedelta
    
    if is_live_mode() and not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    matomo = get_matomo_client()
    
    if not matomo.is_configured:
        return {"error": "Matomo not configured", "configured": False}
    
    # Get referrers for this specific page
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    date_range = f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
    
    # Use Matomo API to get referrers for specific URL
    data = matomo._api_request(
        "Referrers.getAll",
        {
            "period": "range",
            "date": date_range,
            "segment": f"pageUrl=@/p/{path}/",
            "filter_limit": 20
        }
    )
    
    referrers = []
    if data and isinstance(data, list):
        for item in data:
            referrers.append({
                "referrer": item.get("label", "Unknown"),
                "visits": item.get("nb_visits", 0),
                "pageviews": item.get("nb_actions", 0)
            })
    
    return {
        "path": path,
        "days": days,
        "referrers": referrers,
        "configured": True
    }


# =============================================================================
# Agent Utilities
# =============================================================================

@analytics_router.post("/api/agent/upload-image")
async def agent_upload_image(request: Request):
    """
    Upload an image from a URL for the AI agent.
    
    Accepts JSON: {"url": "https://example.com/image.jpg", "filename": "optional-name"}
    
    Downloads the image, converts to WebP, saves locally, uploads to FTP if configured.
    Returns the final URL for use in posts.
    
    ALWAYS returns JSON (never HTML error pages).
    """
    import httpx
    import ftplib
    import random
    import os
    from pathlib import Path
    from starlette.responses import JSONResponse
    from app.settings import settings
    from app.routes import convert_to_webp, secure_filename
    
    try:
        body = await request.json()
        image_url = body.get("url")
        custom_filename = body.get("filename")
        
        if not image_url:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing 'url' parameter"}
            )
        
        # Download the image
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(image_url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; FlowCMS/1.0)"
            })
            
            if response.status_code != 200:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Failed to download image: HTTP {response.status_code}", "url_tried": image_url}
                )
            
            content = response.content
            content_type = response.headers.get("content-type", "")
            
            # Validate it's an image
            if not content_type.startswith("image/"):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"URL is not an image (content-type: {content_type})", "url_tried": image_url}
                )
        
        # Determine filename
        if custom_filename:
            filename = secure_filename(custom_filename)
        else:
            # Extract from URL
            url_path = image_url.split("?")[0]  # Remove query params
            filename = url_path.split("/")[-1]
            filename = secure_filename(filename) if filename else "image"
        
        # Ensure it has an extension
        if "." not in filename:
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp"
            }
            filename += ext_map.get(content_type, ".jpg")
        
        # Convert to WebP (except animated GIFs)
        original_ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        if original_ext in {'png', 'jpg', 'jpeg', 'gif'}:
            content, filename = convert_to_webp(content, filename, quality=90)
            logger.info(f"Converted image to WebP: {filename}")
        
        # Make filename unique
        file_path = Path(settings.local_upload_path) / filename
        if file_path.exists():
            random_chars = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
            name, ext = os.path.splitext(filename)
            filename = f"{name}-{random_chars}{ext}"
            file_path = Path(settings.local_upload_path) / filename
        
        # Ensure upload directory exists
        Path(settings.local_upload_path).mkdir(parents=True, exist_ok=True)
        
        # Save file locally
        file_path.write_bytes(content)
        file_size = file_path.stat().st_size
        
        # Construct local URL
        site_path_prefix = settings.site_path_prefix.rstrip('/')
        if site_path_prefix and not site_path_prefix.startswith('/'):
            site_path_prefix = '/' + site_path_prefix
        file_url = f"{site_path_prefix}/upload/{filename}"
        
        # Upload to FTP if enabled
        ftp_uploaded = False
        if settings.server_ftp_enabled:
            try:
                with ftplib.FTP(settings.server_ftp_server,
                               settings.server_ftp_username,
                               settings.server_ftp_password) as session:
                    ftp_path = settings.server_ftp_media_path + filename
                    with open(file_path, 'rb') as f:
                        session.storbinary(f'STOR {ftp_path}', f)
                    file_url = settings.server_ftp_media_site_path + filename
                    ftp_uploaded = True
                    logger.info(f"Agent uploaded to FTP: {file_url}")
            except Exception as e:
                logger.warning(f"FTP upload failed (local file saved): {e}")
        
        return {
            "success": True,
            "url": file_url,
            "filename": filename,
            "size": file_size,
            "ftp_uploaded": ftp_uploaded,
            "local_path": str(file_path),
            "usage": f'<img src="{file_url}" alt="Description" loading="lazy">'
        }
        
    except Exception as e:
        logger.error(f"Agent image upload error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

