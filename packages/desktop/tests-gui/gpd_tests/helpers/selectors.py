"""Named selector constants for GPD's DOM. Source: spec §4."""
from __future__ import annotations

from gpd_tests.helpers.i18n import t

SIDEBAR_NEW_SESSION = '[data-action="new-session"]'
SIDEBAR_WORKSPACE_MENU = '[data-action="workspace-menu"]'
SIDEBAR_WORKSPACE_TOGGLE = '[data-action="workspace-toggle"]'
SIDEBAR_PROJECT_MENU = '[data-action="project-menu"]'
SIDEBAR_PROJECT_CLOSE_MENU = '[data-action="project-close-menu"]'
SIDEBAR_PROJECT_SWITCH = '[data-action="project-switch"]'
SIDEBAR_PROJECT_WORKSPACES_TOGGLE = '[data-action="project-workspaces-toggle"]'
SIDEBAR_PROJECT_CLEAR_NOTIFICATIONS = '[data-action="project-clear-notifications"]'


def kobalte(component: str, slot: str | None = None) -> str:
    """Build a Kobalte selector: [data-component="C"][data-slot="S"]."""
    base = f'[data-component="{component}"]'
    if slot is None:
        return base
    return f'{base}[data-slot="{slot}"]'


def _safe(key: str, fallback: str) -> str:
    try:
        return t(key)
    except KeyError:
        return fallback


TEXT_WELCOME_TITLE = _safe("welcome.title", "Welcome to GPD")
TEXT_WELCOME_SUBTITLE = _safe("welcome.subtitle", "Physics Research Workspace by PSI")
TEXT_WELCOME_GET_STARTED = _safe("welcome.getStarted", "Get Started")
TEXT_WELCOME_API_KEY_PROMPT = _safe(
    "welcome.apiKey.placeholder", "Paste your GPD API key"
)
TEXT_PROMPT_PLACEHOLDER = _safe(
    "prompt.placeholder.simple", "Ask anything..."
)
TEXT_SIDEBAR_HELP = _safe("sidebar.help", "Help")
TEXT_SIDEBAR_SETTINGS = _safe("sidebar.settings", "Settings")
