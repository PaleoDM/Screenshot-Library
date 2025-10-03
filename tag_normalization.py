"""
Tag normalization to prevent category duplication
"""
from difflib import SequenceMatcher

# Canonical category names - these are the "official" versions
# Add new categories here as your taxonomy grows
CANONICAL_CATEGORIES = [
    "ai/ml developer platform",
    "developer tools platform",
    "mobile banking app",
    "e-commerce platform",
    "social media app",
    "fitness tracker",
    "healthcare platform",
    "productivity app",
    "educational platform"
]

# Similarity threshold (0-1) - higher = more strict matching
# 0.85 means 85% similar before considering it the same category
SIMILARITY_THRESHOLD = 0.85


def similarity_ratio(a, b):
    """Calculate similarity between two strings (0-1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_category(category, threshold=None):
    """
    Check if category is similar to existing canonical categories
    
    Args:
        category: The category string to normalize
        threshold: Similarity threshold (uses SIMILARITY_THRESHOLD if None)
    
    Returns:
        tuple: (normalized_category, is_new)
            - normalized_category: The canonical version or original if new
            - is_new: True if this is a new category not in canonical list
    """
    if threshold is None:
        threshold = SIMILARITY_THRESHOLD
    
    if not category:
        return "", False
    
    category_lower = category.lower()
    
    # Check exact match first
    if category_lower in [c.lower() for c in CANONICAL_CATEGORIES]:
        return category_lower, False
    
    # Find best match among canonical categories
    best_match = None
    best_score = 0
    
    for canonical in CANONICAL_CATEGORIES:
        score = similarity_ratio(category, canonical)
        if score > best_score:
            best_score = score
            best_match = canonical
    
    # If similarity is high enough, use canonical version
    if best_score >= threshold:
        return best_match, False
    
    # Otherwise, it's a new category
    return category_lower, True


def get_canonical_categories():
    """Return list of all canonical categories"""
    return CANONICAL_CATEGORIES.copy()


def add_canonical_category(category):
    """
    Add a new canonical category to the list
    Note: This only modifies the in-memory list, not the file
    """
    if category and category.lower() not in [c.lower() for c in CANONICAL_CATEGORIES]:
        CANONICAL_CATEGORIES.append(category.lower())
        return True