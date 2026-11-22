"""
seo_router.py — Crawler discovery files: robots.txt, sitemaps, llms.txt.

Mounted at the site root (no prefix). Public URLs are built from
settings.public_site_url and the page registry in app/seo/registry.py.
"""

from xml.sax.saxutils import escape

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.seo.registry import PAGES, PAGES_PREFIX, UI_PREFIX, get_page, indexable_pages

router = APIRouter(include_in_schema=False)

APP_PREFIX = "/automiteaiapplication"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Private, API and tooling surfaces that are not registry pages.
_PRIVATE_PREFIXES = (
    f"{UI_PREFIX}/auth/",
    f"{UI_PREFIX}/client-portal/",
    f"{UI_PREFIX}/mngr-sys-access-78/",
    f"{UI_PREFIX}/extraction/",
    f"{UI_PREFIX}/api/",
    f"{APP_PREFIX}/mngr-sys-access-78/",
    f"{APP_PREFIX}/elevenlabs-tools/",
    f"{APP_PREFIX}/client/auth/",
    f"{APP_PREFIX}/docs",
    f"{APP_PREFIX}/redoc",
    f"{APP_PREFIX}/openapi.json",
)


def _site_url() -> str:
    return settings.public_site_url.rstrip("/")


def _url(path: str) -> str:
    return f"{_site_url()}{path}"


def _disallowed_paths() -> list[str]:
    """Every noindex registry page plus the private/API/docs prefixes, de-duplicated."""
    paths = [p.path for p in PAGES if not p.indexable]
    paths.extend(_PRIVATE_PREFIXES)
    return sorted(set(paths))


@router.get("/robots.txt")
async def robots_txt() -> PlainTextResponse:
    lines = ["User-agent: *", "Allow: /"]
    lines.extend(f"Disallow: {path}" for path in _disallowed_paths())
    lines.extend(["", f"Sitemap: {_url('/sitemap.xml')}", ""])
    return PlainTextResponse("\n".join(lines))


@router.get("/sitemap.xml")
async def sitemap_xml() -> Response:
    # Sitemap index: the registry pages plus the separately served blog sitemap.
    locs = (_url("/sitemap-pages.xml"), _url("/blogs/sitemap.xml"))
    entries = "".join(
        f"  <sitemap>\n    <loc>{escape(loc)}</loc>\n  </sitemap>\n" for loc in locs
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<sitemapindex xmlns="{SITEMAP_NS}">\n{entries}</sitemapindex>\n'
    )
    return Response(content=content, media_type="application/xml")


@router.get("/sitemap-pages.xml")
async def sitemap_pages_xml() -> Response:
    entries = []
    for page in indexable_pages():
        entry = f"  <url>\n    <loc>{escape(_url(page.path))}</loc>\n"
        if page.lastmod:
            entry += f"    <lastmod>{escape(page.lastmod)}</lastmod>\n"
        entries.append(entry + "  </url>\n")
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="{SITEMAP_NS}">\n{"".join(entries)}</urlset>\n'
    )
    return Response(content=content, media_type="application/xml")


@router.get("/llms.txt")
async def llms_txt() -> PlainTextResponse:
    landing = get_page(f"{PAGES_PREFIX}/landing")
    cases = get_page(f"{PAGES_PREFIX}/case-studies")
    privacy = get_page(f"{PAGES_PREFIX}/privacy-policy")
    content = (
        "# Automite AI\n"
        "> AI voice agents that handle inbound calls, automate follow-ups, "
        "and work 24/7.\n"
        "\n"
        "## Pages\n"
        f"- [Home]({_url(landing.path)}): {landing.description}\n"
        f"- [Case Studies]({_url(cases.path)}): {cases.description}\n"
        f"- [Privacy Policy]({_url(privacy.path)}): {privacy.description}\n"
        f"- [Blog]({_url('/blogs')}): Automite's blog.\n"
        f"- [Blog index for LLMs]({_url('/blogs/llms.txt')}): "
        "Machine-readable list of blog posts and authors.\n"
        "\n"
        "## Integrations\n"
        "- ElevenLabs: powers the voice agents\n"
        "- Google Calendar: appointment booking and calendar sync\n"
        "- Google Sheets: call summaries are logged to a client sheet\n"
        "\n"
        "## Process\n"
        "Consultation, planning, build, testing, deployment.\n"
        "\n"
        "## Contact\n"
        f"Book a free consultation: {_url(landing.path)}#contact\n"
    )
    return PlainTextResponse(content)
