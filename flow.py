# flow.py 

import uvicorn
from app.settings import settings
import click
from app.content import ContentManager
from app.generator import StaticSiteGenerator
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

if __name__ == "__main__":
    cli()