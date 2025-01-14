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
- 🔍 **Full-Text Search**: Full-text search functionality in the admin interface
- 📊 **Content Explorer**: Visual timeline view of your content
- 📡 **FTP Integration**: One-click deployments to any host
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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](https://github.com/samim23/flow/blob/master/LICENSE.md) for details

---

_Built by [samim](https://samim.io)_
