import pytest

from gpd_tests.helpers import selectors


@pytest.mark.unit
def test_sidebar_action_selectors_defined():
    assert selectors.SIDEBAR_NEW_SESSION == '[data-action="workspace-new-session"]'
    assert selectors.SIDEBAR_PROJECT_MENU == '[data-action="project-menu"]'


@pytest.mark.unit
def test_kobalte_data_component_selector_helper():
    assert selectors.kobalte("button") == '[data-component="button"]'
    assert (
        selectors.kobalte("dialog-overlay", slot="content")
        == '[data-component="dialog-overlay"][data-slot="content"]'
    )


@pytest.mark.unit
def test_aria_label_text_constants_resolve_from_i18n():
    """Assert the selector constants come from real keys in the committed dict.

    Using the `_safe` fallback without this check would let silent drift hide
    behind hardcoded English strings. We look up each key directly and require
    the constant value to equal the dict entry.
    """
    from gpd_tests.helpers import i18n

    pairs = [
        (selectors.TEXT_WELCOME_TITLE, "welcome.title"),
        (selectors.TEXT_WELCOME_SUBTITLE, "welcome.subtitle"),
        (selectors.TEXT_WELCOME_GET_STARTED, "welcome.getStarted"),
        (selectors.TEXT_WELCOME_API_KEY_PROMPT, "welcome.apiKey.placeholder"),
        (selectors.TEXT_PROMPT_PLACEHOLDER, "prompt.placeholder.simple"),
        (selectors.TEXT_SIDEBAR_HELP, "sidebar.help"),
        (selectors.TEXT_SIDEBAR_SETTINGS, "sidebar.settings"),
    ]
    for value, key in pairs:
        assert value == i18n.t(key), (
            f"selector constant drifted from en.json[{key!r}]: "
            f"got {value!r} vs {i18n.t(key)!r}"
        )
