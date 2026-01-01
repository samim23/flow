# app/analytics/__init__.py
"""
Analytics Module for Flow Blog

This module provides optional analytics integration with Matomo,
including performance dashboards, AI content insights, and more.

The module is designed to be completely optional - if analytics
settings are not configured, it gracefully degrades.

Usage:
    from app.analytics import is_analytics_enabled, get_analytics_router
    
    if is_analytics_enabled():
        app.include_router(get_analytics_router())
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading if not configured
_matomo_client = None
_analytics_store = None
_insights_engine = None


def is_analytics_enabled() -> bool:
    """Check if analytics is properly configured"""
    try:
        from app.settings import settings
        return bool(
            getattr(settings, 'matomo_url', None) and 
            getattr(settings, 'matomo_token', None)
        )
    except Exception:
        return False


def get_matomo_client():
    """Get singleton Matomo client instance"""
    global _matomo_client
    if _matomo_client is None:
        from .matomo import MatomoClient
        _matomo_client = MatomoClient()
    return _matomo_client


def get_analytics_store():
    """Get singleton analytics store instance"""
    global _analytics_store
    if _analytics_store is None:
        from .store import AnalyticsStore
        _analytics_store = AnalyticsStore()
    return _analytics_store


def get_insights_engine():
    """Get singleton insights engine instance"""
    global _insights_engine
    if _insights_engine is None:
        from .insights import InsightsEngine
        _insights_engine = InsightsEngine()
    return _insights_engine


def get_analytics_router():
    """Get the analytics router for FastAPI integration"""
    from .routes import analytics_router
    return analytics_router


def get_ai_context():
    """Get AI context generator for content optimization"""
    from .ai_context import AIContextGenerator
    return AIContextGenerator()


# Export key classes for direct import if needed
__all__ = [
    'is_analytics_enabled',
    'get_matomo_client',
    'get_analytics_store', 
    'get_insights_engine',
    'get_analytics_router',
    'get_ai_context',
]

