"""
Editable prompt configuration for image tagging
Modify these values to tune how the AI generates tags
"""

# Common tag vocabulary - these are SUGGESTIONS for the AI
# The AI can still generate other tags, but will prioritize these types
COMMON_TAG_VOCABULARY = [
    "button",
    "form",
    "modal",
    "navigation bar",
    "card",
    "list",
    "sidebar",
    "hero section",
    "empty state",
    "error message",
    "loading spinner",
    "dropdown",
    "search bar",
    "tab bar",
    "footer",
    "header",
    "icon",
    "tooltip",
    "badge",
    "avatar"
]

# What to focus on when generating descriptive tags
TAG_FOCUS_INSTRUCTION = """Focus on:
- Specific UI components (button, form, modal, navigation bar, card, list, etc)
- Screen type (login, signup, profile, settings, dashboard, etc)
- Interactions (empty state, error state, loading, success message, etc)
- Layout patterns (sidebar, grid, tabs, drawer, etc)

IMPORTANT: Use spaces between words, not hyphens. For example: "navigation bar" not "navigation-bar", "login screen" not "login-screen"."""

# Instructions for identifying company/brand
COMPANY_INSTRUCTION = "Look for branding, logos, or identifiable design systems"