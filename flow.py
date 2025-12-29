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


if __name__ == "__main__":
    cli()