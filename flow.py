# flow.py 

import uvicorn
from app.settings import settings
import click
from app.content import ContentManager
from app.generator import StaticSiteGenerator
import subprocess
import shutil
import sys

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        ctx.invoke(serve)

@cli.command()
@click.option('--tags/--no-tags', default=False, help='Clear tag page cache')
@click.option('--archives/--no-archives', default=False, help='Clear archive page cache')
@click.option('--tag-archives/--no-tag-archives', default=False, help='Clear tag archive page cache')
@click.option('--posts/--no-posts', default=False, help='Clear post page cache')
@click.option('--all/--no-all', default=False, help='Clear all cache types')
def clear_cache(tags, archives, tag_archives, posts, all):
    """Clear selected parts of the site cache"""
    content_manager = ContentManager(settings.content_dir)
    generator = StaticSiteGenerator(
        "app/templates", 
        "build", 
        content_manager,
        settings=settings
    )
    
    if all:
        tags = archives = tag_archives = posts = True
        
    cleared = generator.clear_cache_selectively(
        clear_tags=tags,
        clear_archives=archives,
        clear_tag_archives=tag_archives,
        clear_posts=posts
    )
    
    click.echo(f"Cleared {cleared} cache entries")

@cli.command()
def serve():
    """Run the development server"""
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.local_server_port, reload=True)


@cli.command()
def cache_stats():
    """Show cache statistics"""
    from app.cache import get_cache
    cache = get_cache()
    stats = cache.get_stats()
    
    click.echo("\n📊 Cache Statistics:")
    click.echo(f"   Database: {stats.get('db_path', 'N/A')}")
    click.echo(f"   Size: {stats.get('db_size_mb', 0)} MB")
    click.echo(f"\n   Total entries: {stats.get('total_entries', 0):,}")
    click.echo(f"   ├── Build files (FTP): {stats.get('build_files', 0):,}")
    click.echo(f"   ├── Static files: {stats.get('static_files', 0):,}")
    click.echo(f"   ├── Page cache: {stats.get('page_cache', 0):,}")
    click.echo(f"   └── Tag cache: {stats.get('tag_cache', 0):,}")
    click.echo("")


@cli.command()
def build_search_index():
    """Build the Pagefind search index for the static site"""
    build_dir = settings.local_build_path
    
    # Check if npx is available
    if not shutil.which('npx'):
        click.echo("Error: npx not found. Please install Node.js to use Pagefind.", err=True)
        click.echo("Install with: npm install -g pagefind", err=True)
        sys.exit(1)
    
    click.echo(f"Building search index for {build_dir}...")
    
    try:
        result = subprocess.run(
            ['npx', '-y', 'pagefind', '--site', str(build_dir), '--output-path', f'{build_dir}/static/pagefind'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            click.echo("✓ Search index built successfully!")
            click.echo(result.stdout)
        else:
            click.echo(f"Error building search index: {result.stderr}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error running pagefind: {e}", err=True)
        sys.exit(1)


# ============================================================
# Analytics Commands
# ============================================================

@cli.command()
def analytics_sync():
    """Sync analytics data from Matomo"""
    try:
        from app.analytics import is_analytics_enabled, get_analytics_store
        
        if not is_analytics_enabled():
            click.echo("⚠️  Matomo not configured. Add these to your .env:")
            click.echo("   MATOMO_URL=https://your-matomo-instance/")
            click.echo("   MATOMO_SITE_ID=1")
            click.echo("   MATOMO_TOKEN=your_auth_token")
            return
        
        click.echo("🔄 Syncing analytics from Matomo...")
        content_manager = ContentManager(settings.content_dir)
        store = get_analytics_store()
        updated = store.sync_from_matomo(content_manager)
        click.echo(f"✓ Synced analytics for {updated} posts")
        
    except ImportError as e:
        click.echo(f"Error: Analytics module not available: {e}", err=True)
        sys.exit(1)


@cli.command()
def analytics_stats():
    """Show analytics statistics"""
    try:
        from app.analytics import get_analytics_store, get_matomo_client
        
        store = get_analytics_store()
        matomo = get_matomo_client()
        
        click.echo("\n📊 Analytics Statistics:")
        click.echo(f"   Matomo configured: {'Yes' if matomo.is_configured else 'No'}")
        
        summary = store.get_stats_summary()
        click.echo(f"\n   Local Data Store:")
        click.echo(f"   ├── Posts tracked: {summary.get('posts_tracked', 0):,}")
        click.echo(f"   ├── Tags tracked: {summary.get('tags_tracked', 0):,}")
        click.echo(f"   ├── Total pageviews: {summary.get('total_pageviews', 0):,}")
        click.echo(f"   └── Total visitors: {summary.get('total_visitors', 0):,}")
        
        last_sync = summary.get('last_sync')
        if last_sync:
            click.echo(f"\n   Last sync: {last_sync.strftime('%Y-%m-%d %H:%M')}")
        
        click.echo("")
        
    except ImportError as e:
        click.echo(f"Error: Analytics module not available: {e}", err=True)


@cli.command()
def analytics_top():
    """Show top performing posts"""
    try:
        from app.analytics import get_analytics_store
        
        store = get_analytics_store()
        top_posts = store.get_top_posts(limit=15)
        
        if not top_posts:
            click.echo("No analytics data. Run 'python flow.py analytics-sync' first.")
            return
        
        click.echo("\n🔥 Top Performing Posts:\n")
        for i, post in enumerate(top_posts, 1):
            views = f"{post.total_pageviews:,}"
            visitors = f"{post.total_visitors:,}"
            title = (post.title[:50] + '...') if len(post.title) > 50 else post.title
            click.echo(f"   {i:2}. {title}")
            click.echo(f"       📊 {views} views | 👥 {visitors} visitors")
        
        click.echo("")
        
    except ImportError as e:
        click.echo(f"Error: Analytics module not available: {e}", err=True)


@cli.command()
def analytics_ai_context():
    """Generate AI context from analytics data"""
    try:
        from app.analytics import get_ai_context
        
        generator = get_ai_context()
        context = generator.generate_context()
        prompt = context.to_system_prompt()
        
        click.echo(prompt)
        
    except ImportError as e:
        click.echo(f"Error: Analytics module not available: {e}", err=True)


@cli.command()
def analytics_insights():
    """Show content insights and recommendations"""
    try:
        from app.analytics import get_insights_engine
        
        insights = get_insights_engine()
        data = insights.get_comprehensive_insights()
        
        click.echo("\n💡 Content Insights:\n")
        
        # Title patterns
        if data.get('title_patterns'):
            click.echo("   ✍️  What works in titles:")
            for pattern in data['title_patterns'][:3]:
                click.echo(f"      • {pattern['description']}")
        
        # Tag trends
        rising = [t for t in data.get('tag_trends', []) if t['direction'] == 'rising']
        falling = [t for t in data.get('tag_trends', []) if t['direction'] == 'falling']
        
        if rising:
            click.echo("\n   📈 Rising topics:")
            for t in rising[:5]:
                click.echo(f"      • #{t['tag']} (+{t['change']:.0f}%)")
        
        if falling:
            click.echo("\n   📉 Declining topics:")
            for t in falling[:3]:
                click.echo(f"      • #{t['tag']} ({t['change']:.0f}%)")
        
        # Content gaps
        if data.get('content_gaps'):
            click.echo("\n   🎯 Content opportunities:")
            for gap in data['content_gaps'][:5]:
                click.echo(f"      • {gap['topic']}: {gap['reason']}")
        
        # Best posting time
        timing = data.get('posting_times', {})
        if timing.get('best_day'):
            click.echo(f"\n   🕐 {timing['recommendation']}")
        
        click.echo("")
        
    except ImportError as e:
        click.echo(f"Error: Analytics module not available: {e}", err=True)


if __name__ == "__main__":
    cli()