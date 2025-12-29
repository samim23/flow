# Flow

A lightweight static site generator with built-in CMS that creates microblog-style content feeds. Ideal for personal blogs and knowledge collections.

[![Flow](https://samim.io/static/upload/Screenshot-20250114151812-895x631-ahcag9p7.png)](https://samim.io/static/upload/Screenshot-20250114151812-895x631-ahcag9p7.png)

## Why Flow?

Blogging is one of the most valuable practices for developing ideas and sharing knowledge. While there are many platforms available, most are either too complex (WordPress), too limiting (Medium), or require too much setup (static site generators).

I wanted something simpler: A lightweight engine with a built-in editor that makes publishing frictionless and focuses on readability. A tool for maintaining a digital garden that grows over time.

That's why I built Flow - a minimalist blogging engine that gets out of your way and lets you focus on what matters: writing and sharing ideas. _Flow is Powering [samim.io](https://samim.io)_

## Key Features

- ⚡ **Python + FastAPI**: Built on modern, high-performance Python web frameworks
- 🚀 **Lightning Fast**: Generates static pages with intelligent caching
- 💅 **Beautiful Editor**: Medium-style WYSIWYG editing experience
- 🖼️ **Image Management**: Drag-and-drop image uploads with gallery support
- 🏷️ **Tagging**: Supports hashtag and tag page generation
- 📱 **Mobile-First**: Responsive design that works seamlessly across devices
- 🔍 **Full-Text Search**: Search across all posts, works on both editor and published site
- 📊 **Content Explorer**: Visual timeline view of your content
- 🔗 **Related Posts**: Discover and link to related content while writing
- 📧 **Newsletter Integration**: Optional subscribe button with Mailchimp support
- 📡 **FTP Integration**: One-click deployments to any host
- 📰 **RSS with Images**: Full RSS feed support including image enclosures
- 🔄 **Incremental Builds**: Only rebuilds what changed
- 🎯 **Minimal Configuration**: Works out of the box with sensible defaults
- 🎨 **Customizable**: Easy to modify templates and styling

## Installation

```bash
git clone https://github.com/samim23/flow.git
cd flow
pip install -r requirements.txt
```

## Quick Start

1. Setup environment variables:

```bash
cp .env.sample .env
vim .env (or use your favorite text editor to adjust site config)
source .env
```

2. Run the server:

```bash
python3 flow.py
```

3. Visit `http://127.0.0.1:2323/` to start creating content

## Publishing via FTP

In your .env config set `server_ftp_enabled=true` and add your server infos.

## Running as a Live Server

Flow can run directly as a live web application instead of generating static files. This is useful if you want to skip the build/FTP workflow and just run Flow on your server.

### Quick Setup

1. Set an admin password in `app/settings.py`:

```python
admin_password: str = "your-secure-password"
session_secret: str = "change-this-random-string"
```

2. Run with a production server:

```bash
pip install gunicorn uvicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
```

3. Set up nginx as a reverse proxy (recommended):

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static {
        alias /path/to/flow/app/static;
    }
    
    location /upload {
        alias /path/to/flow/upload;
    }
}
```

### How It Works

- **No password set**: Editor is always accessible (local development mode)
- **Password set**: Public users see read-only site, login required for editing
- Visit `/login` to authenticate and access the editor
- All write operations (post, upload, delete) require authentication

### Note on Search

In live mode, search uses server-side filtering instead of Pagefind. For the static site deployment, Pagefind provides faster client-side search.

## About Page Setup

Create a post in the UI and then rename the file in your `/content/p/` folder to `about.md`

## Newsletter Integration

To add a "Subscribe" button to your navigation, set the `newsletter_url` in your settings:

```python
# In app/settings.py
newsletter_url: str = "https://mailchi.mp/xxx/yourlist"
```

Leave empty or remove to hide the subscribe button. Works with any newsletter service (Mailchimp, Buttondown, etc.).

## Related Posts & Backlinks

While editing, click the **Related** button (or press `Cmd+Shift+R`) to open a sidebar showing posts related to your current draft. Click "Insert" to add a rich backlink.

Backlinks use the `<flow-embed>` tag which renders as a Twitter-style quote card:

```html
<flow-embed url="https://yoursite.com/p/your-post/"></flow-embed>
```

The card content is fetched dynamically, so links always show fresh data.

## Cache Management

Flow uses intelligent caching to minimize build times by only regenerating changed content. If you need to manually clear the cache, here are the available commands:

```bash
# Clear specific caches
python flow.py clear-cache --tags            # Clear tag pages
python flow.py clear-cache --archives        # Clear archive pages
python flow.py clear-cache --tag-archives    # Clear tag archive pages
python flow.py clear-cache --posts           # Clear post pages

# Clear multiple caches
python flow.py clear-cache --tags --archives # Clear tags and archives
python flow.py clear-cache --all             # Clear everything
```

## Preview Mode

Add `?freeze=1` to any URL to preview how it will look when published.

## Analytics

Configure your analytics by editing `/static/js/analytics.js`.

## Customizing Posts with Frontmatter

Flow supports special frontmatter fields in your Markdown (`.md`) files to customize how individual posts are rendered and styled:

### Server-Side Markdown Rendering

By default, content in `.md` files is treated as HTML. To enable server-side Markdown parsing (which supports standard Markdown syntax, tables, math rendering with MathJax, etc.), add the following to your post's frontmatter:

```yaml
render_as_markdown: true
```

When this is set, the content of your post (after the `---` frontmatter block) will be processed as Markdown.

Flow's Markdown processor supports the full range of standard Markdown syntax, including:

- **Text Formatting**: Bold with `**double asterisks**` or `__double underscores__`,
  italic with `*single asterisks*` or `_single underscores_`
- **Headers**: Created with `#` at the beginning of a line
- **Lists**: Both ordered (numbered) and unordered (bullet) lists
- **Links**: `[Link text](URL)`
- **Images**: `![Alt text](image-url)`
- **Tables**: Standard Markdown table format
- **Code Blocks**: Both inline with backticks and fenced code blocks
- **Math**: LaTeX-style math expressions with MathJax
- **HTML**: You can mix HTML with Markdown when needed

### Per-Post Custom CSS Class

To apply a custom CSS class to the main content wrapper of a specific post, allowing for unique styling (e.g., a different font), add the following to the frontmatter:

```yaml
custom_css_class: "your-custom-class-name"
```

For example:

```yaml
custom_css_class: "text-serif"
```

This class will be added to the `div` that wraps your post's content, which you can then target in your CSS files.

### Subdirectory Deployment

If you need to deploy this application in a subdirectory on your server (e.g., `https://yourdomain.com/blog/` instead of `https://yourdomain.com/`), you can use the `site_path_prefix` setting in your `.env` file (or `app/settings.py`).

*   **`SITE_URL`**: Set this to your main domain, e.g., `SITE_URL="https://yourdomain.com"`.
*   **`SITE_PATH_PREFIX`**: Set this to the subdirectory path, e.g., `SITE_PATH_PREFIX="/blog/"`. Ensure it starts and ends with a slash, or is just `/` if deploying at the root.

The application will then correctly generate all URLs (for static assets, internal links, RSS feeds, etc.) to include this prefix.

**Note for Live Server (FastAPI):**
When running the live FastAPI server (e.g., via `python app/main.py`), the `root_path` for the FastAPI application is automatically configured based on `SITE_PATH_PREFIX`. This ensures that the live server also operates correctly from the specified subdirectory.

**Important Note for Windows Users:**
If you're using Windows, especially with Git Bash, be aware that `site_path_prefix` may sometimes be affected by your environment's path formatting. The application includes safeguards to prevent Windows-specific paths (like `C:/Program Files/Git/blog/`) from appearing in URLs. If you notice any paths like this in your generated HTML, please ensure your `.env` file uses simple, web-style paths like `/blog/` rather than Windows paths.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](https://github.com/samim23/flow/blob/master/LICENSE.md) for details

---

_Built by [samim](https://samim.io)_

