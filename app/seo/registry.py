"""
registry.py — Registry of the server-rendered HTML pages under /pages/*.

Mirrors app/routers/pages_router.py. Titles and descriptions are copied from
the current templates and left as None where a template does not define them.
lastmod is None until a real modification date is tracked.
"""

from dataclasses import dataclass
from typing import Optional

# Same value as UI_PREFIX in app/main.py (kept here to avoid importing main).
UI_PREFIX = "/automiteaiapplication/automiteui"
PAGES_PREFIX = f"{UI_PREFIX}/pages"

PAGE_TYPES = ("marketing", "legal", "auth", "dashboard", "admin", "preview")


@dataclass(frozen=True)
class PageEntry:
    path: str
    template: str
    page_type: str
    indexable: bool
    title: Optional[str] = None
    description: Optional[str] = None
    lastmod: Optional[str] = None

    @property
    def canonical_path(self) -> Optional[str]:
        """Canonical path for indexable pages; noindex pages have none."""
        return self.path if self.indexable else None


PAGES: tuple[PageEntry, ...] = (
    PageEntry(
        path=f"{PAGES_PREFIX}/landing",
        template="landing.html",
        page_type="marketing",
        indexable=True,
        title="Automite AI — Call and Lead Automation for Growing Businesses",
        description=(
            "Recover missed enquiries, follow up eligible leads, and reduce repetitive admin "
            "with call and lead-management automation scoped around your business."
        ),
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/case-studies",
        template="case-studies.html",
        page_type="marketing",
        indexable=True,
        title="Case Studies — AI Voice Agents That Win Back Hours",
        description=(
            "See how dental, HVAC, real estate, legal, spa, and auto businesses use "
            "Automite AI voice agents to capture more calls and win back hours weekly."
        ),
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/privacy-policy",
        template="privacy-policy.html",
        page_type="legal",
        indexable=True,
        title="Privacy Policy — How Automite AI Protects Your Data",
        description=(
            "Read how Automite AI collects, uses, and protects your information across "
            "our website, client dashboard, and AI voice agent services."
        ),
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/login",
        template="login.html",
        page_type="auth",
        indexable=False,
        title="Client Login — Your Automite AI Voice Agent Dashboard",
        description=(
            "Sign in to your Automite AI dashboard to manage your voice agent, calls, "
            "appointments, calendar sync, and monthly usage in one place."
        ),
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/register",
        template="register.html",
        page_type="auth",
        indexable=False,
        title="Register — Get Your Automite AI Voice Agent Account",
        description=(
            "Create your Automite AI account to launch your own AI voice agent for "
            "inbound calls, bookings, and follow-ups — setup takes just minutes."
        ),
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/dashboard",
        template="dashboard.html",
        page_type="dashboard",
        indexable=False,
        title="Client Dashboard — Your Automite AI Voice Agent Hub",
        description=(
            "Manage your Automite AI voice assistant, services, appointments, Google "
            "Calendar integration, and monthly usage from one dashboard."
        ),
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/landing-moves-preview",
        template="landing_moves_preview.html",
        page_type="preview",
        indexable=False,
        title="Automite AI — Design Prototype Preview",
        description="Preview of proposed landing design moves. Prototype only, not the live page.",
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/mngr-sys-access-78",
        template="admin/login.html",
        page_type="admin",
        indexable=False,
        title="System Access",
    ),
    PageEntry(
        path=f"{PAGES_PREFIX}/mngr-sys-access-78/dashboard",
        template="admin/dashboard.html",
        page_type="admin",
        indexable=False,
        title="System Dashboard",
    ),
)

PAGES_BY_PATH: dict[str, PageEntry] = {p.path: p for p in PAGES}


def get_page(path: str) -> Optional[PageEntry]:
    return PAGES_BY_PATH.get(path)


def indexable_pages() -> tuple[PageEntry, ...]:
    return tuple(p for p in PAGES if p.indexable)
