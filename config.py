"""
Configuration settings for the UI Screenshot Search application
"""

# Chroma DB settings - use /tmp for Streamlit Cloud
CHROMA_DB_PATH = "/tmp/chroma_db"
COLLECTION_NAME = "ui_screenshots"

# Image processing settings
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".webp"]
MAX_IMAGE_SIZE = (1024, 1024)

# Search settings
DEFAULT_SEARCH_RESULTS = 12
MAX_SEARCH_RESULTS = 24

# Tagging settings
PROJECT_TAG_SAMPLE_SIZE = 5
MAX_TAGS_PER_IMAGE = 10
MAX_PROJECT_TAGS = 8

# Anthropic settings
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 300

# UI settings
IMAGES_PER_ROW = 3
THUMBNAIL_SIZE = (300, 300)
