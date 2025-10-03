"""
Configuration settings for the UI Screenshot Search application
"""

# Chroma DB settings
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "ui_screenshots"

# Image processing settings
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".webp"]
MAX_IMAGE_SIZE = (1024, 1024)  # Resize large images for processing

# Search settings
DEFAULT_SEARCH_RESULTS = 12
MAX_SEARCH_RESULTS = 24

# Tagging settings
PROJECT_TAG_SAMPLE_SIZE = 5  # Number of images to sample for project-level tagging
MAX_TAGS_PER_IMAGE = 10
MAX_PROJECT_TAGS = 8

# GPT-4V settings
GPT_MODEL = "gpt-4o"
MAX_TOKENS = 300

# UI settings
IMAGES_PER_ROW = 3
THUMBNAIL_SIZE = (300, 300)
