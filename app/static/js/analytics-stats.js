/**
 * Analytics Stats Loader
 * 
 * Provides inline stats badges for posts in the editor.
 * This script loads post analytics asynchronously and displays them.
 */

(function() {
  'use strict';

  // Cache for post stats
  const statsCache = new Map();
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

  /**
   * Format a number with K/M suffixes for large numbers
   */
  function formatNumber(num) {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  }

  /**
   * Format seconds as human-readable time
   */
  function formatTime(seconds) {
    if (seconds < 60) {
      return Math.round(seconds) + 's';
    }
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes}m ${secs}s`;
  }

  /**
   * Fetch stats for a single post
   */
  async function fetchPostStats(postPath) {
    // Check cache first
    const cached = statsCache.get(postPath);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
      return cached.data;
    }

    try {
      const response = await fetch(`/analytics/api/post/${postPath}`);
      if (!response.ok) {
        return null;
      }
      
      const data = await response.json();
      
      // Cache the result
      statsCache.set(postPath, {
        data: data,
        timestamp: Date.now()
      });
      
      return data;
    } catch (e) {
      console.warn('Failed to fetch stats for', postPath, e);
      return null;
    }
  }

  /**
   * Update a stats badge element with data
   */
  function updateBadge(badge, stats) {
    const loading = badge.querySelector('.stats-loading');
    const viewsEl = badge.querySelector('.stats-views');
    const viewCount = badge.querySelector('.view-count');
    const visitorsEl = badge.querySelector('.stats-visitors');
    const visitorCount = badge.querySelector('.visitor-count');
    const timeEl = badge.querySelector('.stats-time');
    const timeValue = badge.querySelector('.time-value');

    if (!stats) {
      if (loading) loading.textContent = '—';
      return;
    }

    // Get the best available data (prefer live, fallback to stored)
    const data = stats.live || stats.stored || {};
    const views = data.pageviews || data.total_pageviews || 0;
    const visitors = data.visitors || data.total_visitors || 0;
    const avgTime = data.avg_time || 0;

    // Hide loading, show stats
    if (loading) loading.style.display = 'none';
    
    if (viewsEl && viewCount) {
      viewCount.textContent = formatNumber(views);
      viewsEl.style.display = 'inline';
    }

    if (visitorsEl && visitorCount) {
      visitorCount.textContent = formatNumber(visitors);
      visitorsEl.style.display = 'inline';
    }

    if (timeEl && timeValue && avgTime > 0) {
      timeValue.textContent = formatTime(avgTime);
      timeEl.style.display = 'inline';
    }
  }

  /**
   * Load stats for all badges on the page
   */
  async function loadAllStats() {
    const badges = document.querySelectorAll('.stats-badge[data-post-path]');
    
    for (const badge of badges) {
      const postPath = badge.dataset.postPath;
      if (!postPath) continue;
      
      const stats = await fetchPostStats(postPath);
      updateBadge(badge, stats);
    }
  }

  /**
   * Create a stats badge element for a post
   */
  function createStatsBadge(postPath, options = {}) {
    const compact = options.compact || false;
    const showDetails = options.showDetails || false;

    const badge = document.createElement('div');
    badge.className = 'stats-badge' + (compact ? ' compact' : '');
    badge.dataset.postPath = postPath;
    badge.title = 'Click for details';

    badge.innerHTML = `
      <span class="stats-loading">📊</span>
      <span class="stats-views" style="display: none;">
        <span class="view-count">—</span>
        <span class="view-label">${compact ? 'v' : 'views'}</span>
      </span>
      ${showDetails ? `
        <span class="stats-visitors" style="display: none;">
          <span class="visitor-count">—</span>
          <span class="visitor-label">visitors</span>
        </span>
        <span class="stats-time" style="display: none;">
          <span class="time-value">—</span>
          <span class="time-label">avg</span>
        </span>
      ` : ''}
    `;

    // Load stats for this badge
    fetchPostStats(postPath).then(stats => updateBadge(badge, stats));

    // Add click handler to show full stats
    badge.addEventListener('click', () => {
      window.open(`/analytics/api/post/${postPath}`, '_blank');
    });

    return badge;
  }

  /**
   * Add stats badges to all posts in a list
   */
  function addBadgesToPosts(containerSelector, postPathExtractor) {
    const container = document.querySelector(containerSelector);
    if (!container) return;

    const posts = container.querySelectorAll('.h-entry, .post-item, [data-post-path]');
    
    for (const post of posts) {
      let postPath = post.dataset.postPath;
      
      // Try to extract path from link if not set
      if (!postPath && postPathExtractor) {
        postPath = postPathExtractor(post);
      }
      
      if (!postPath) {
        // Try to find it from a link
        const link = post.querySelector('a[href*="/p/"]');
        if (link) {
          const match = link.href.match(/\/p\/([^\/]+)\/?/);
          if (match) postPath = match[1];
        }
      }

      if (postPath) {
        // Check if badge already exists
        if (post.querySelector('.stats-badge')) continue;

        const badge = createStatsBadge(postPath, { compact: true });
        
        // Insert badge after title or at the start
        const title = post.querySelector('.post-title, .p-name, h2, h3');
        if (title) {
          title.parentNode.insertBefore(badge, title.nextSibling);
        } else {
          post.insertBefore(badge, post.firstChild);
        }
      }
    }
  }

  // Export functions for use in other scripts
  window.FlowAnalytics = {
    fetchPostStats,
    createStatsBadge,
    addBadgesToPosts,
    loadAllStats,
    formatNumber,
    formatTime
  };

  // Auto-load stats for any badges already on the page
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadAllStats);
  } else {
    loadAllStats();
  }
})();

