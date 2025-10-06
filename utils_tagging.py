"""
Utility functions for generating tags using Anthropic Claude Vision
"""

import os
import re
import json
import base64
from typing import List, Dict, Any
from anthropic import Anthropic

from prompts_config import COMMON_TAG_VOCABULARY, TAG_FOCUS_INSTRUCTION
from tag_normalization import normalize_category
import config

# ---------------------------
# Client & small utilities
# ---------------------------

# Initialize Anthropic client
def get_api_key():
    """Get API key from Streamlit secrets or environment variable"""
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY")
    except:
        return os.getenv("ANTHROPIC_API_KEY")

client = Anthropic(api_key=get_api_key())

def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """
    Scan for the first balanced {...} block at top level, respecting strings/escapes.
    Returns a parsed dict or {}.
    """
    if not text:
        return {}
    n = len(text)
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        i = start
        while i < n:
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i+1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            # not valid JSON; keep scanning for the next '{'
                            break
            i += 1
        start = text.find("{", start + 1)
    return {}

def _guess_media_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    # Default to PNG if unknown
    return "image/png"

def encode_image(image_path: str) -> str:
    """Encode image to base64 string"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# ---------------------------
# Robust JSON parsing helpers
# ---------------------------

def parse_json_response(response_text: str) -> Dict[str, Any]:
    if not response_text:
        return {}
    # 1) direct
    try:
        return json.loads(response_text)
    except Exception:
        pass
    # 2) ```json fences
    if "```json" in response_text:
        try:
            json_str = response_text.split("```json", 1)[1].split("```", 1)[0].strip()
            return json.loads(json_str)
        except Exception:
            pass
    # 3) generic ```
    if "```" in response_text:
        try:
            json_str = response_text.split("```", 1)[1].split("```", 1)[0].strip()
            return json.loads(json_str)
        except Exception:
            pass
    # 4) balanced-brace scan (fixed)
    return _extract_first_json_object(response_text)

def _normalize_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map common key variants to the strict schema you expect:
    - company_name: from company_name/company/brand/brand_name
    - product_category: from product_category/category/product_type/app_type
    - descriptive_tags: from descriptive_tags/tags/feature_tags (also accept CSV string)
    """
    if not isinstance(d, dict):
        return {"company_name": "", "product_category": "", "descriptive_tags": []}

    out: Dict[str, Any] = {}

    # Company
    company = d.get("company_name") or d.get("company") or d.get("brand") or d.get("brand_name") or ""
    out["company_name"] = company.strip() if isinstance(company, str) else ""

    # Category - FIX: properly unpack the tuple from normalize_category
    category = (
        d.get("product_category")
        or d.get("category")
        or d.get("product_type")
        or d.get("app_type")
        or ""
    )
    if isinstance(category, str):
        category = category.strip()
        if category:
            # normalize_category returns (normalized_string, is_new) tuple
            normalized_category, is_new = normalize_category(category)
            category = normalized_category
    else:
        category = ""
    out["product_category"] = category

    # Tags
    tags = d.get("descriptive_tags") or d.get("tags") or d.get("feature_tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list):
        tags = []
    out["descriptive_tags"] = tags

    return out

# ---------------------------
# Helper to extract text from response
# ---------------------------

def _extract_text_from_response(response) -> str:
    """
    Extract text content from Anthropic API response.
    Handles the response.content structure properly.
    """
    if not response or not hasattr(response, 'content'):
        return ""
    
    # response.content is a list of content blocks
    for block in response.content:
        if hasattr(block, 'type') and block.type == 'text':
            return block.text
    
    return ""

# ---------------------------
# Public functions
# ---------------------------

def generate_project_tags(image_paths: List[str], project_name: str) -> List[str]:
    """
    Generate project-level tags by analyzing multiple screenshots together.
    Returns common themes and patterns across all images.
    """
    if not image_paths:
        return []

    # Sample up to N images for project analysis (cost control)
    sample_size = config.PROJECT_TAG_SAMPLE_SIZE
    sample_paths = image_paths[:sample_size]

    # Prepare message content with multiple images
    content: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f'Analyze these UI screenshots from the project "{project_name}".\n\n'
                "Identify COMMON themes, patterns, and characteristics shared across these interfaces.\n"
                "Focus on:\n"
                "1) Shared design patterns or UI elements that appear multiple times\n"
                "2) Common functionality or features\n"
                "3) Overall design style or methodology\n"
                "4) Target audience or use case\n\n"
                'Return a JSON object with a single key "project_tags" containing an array of 5-10 common tags.\n'
                "Tags should be lowercase, concise, and focused on SHARED characteristics.\n\n"
                "IMPORTANT: Use spaces between words, NOT hyphens. Example: \"mobile first\" not \"mobile-first\"\n\n"
                'Example: {"project_tags": ["mobile first", "dark mode", "social features", "card based layout", "onboarding flow"]}\n\n'
                "Respond with JSON only, no additional text."
            ),
        }
    ]

    for i, image_path in enumerate(sample_paths, 1):
        content.append({"type": "text", "text": f"\nImage {i} of {len(sample_paths)}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": _guess_media_type(image_path),
                "data": encode_image(image_path),
            },
        })

    try:
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.MAX_TOKENS,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": content,
            }],
        )

        raw = _extract_text_from_response(response)
        result = parse_json_response(raw)
        tags = result.get("project_tags", [])
        
        # Ensure list of strings
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        if not isinstance(tags, list):
            tags = []
        
        # Limit to max project tags
        return tags[:config.MAX_PROJECT_TAGS]

    except Exception as e:
        print(f"Error generating project tags: {e}")
        # Fallback tags based on project name
        base = project_name.lower().strip().replace(" ", "-") if project_name else "project"
        return [base, "ui design", "interface"]

def generate_image_tags(image_path: str, project_tags: List[str] = None) -> Dict[str, Any]:
    """
    Generate structured tags for a single image.
    Returns company name, product category, and descriptive tags.
    """
    if project_tags is None:
        project_tags = []

    prompt = f"""Analyze this UI screenshot and extract structured information.

{TAG_FOCUS_INSTRUCTION}

Context: This image is part of a project with these tags: {', '.join(project_tags) if project_tags else 'No project context'}

Vocabulary suggestions (use when relevant): {', '.join(COMMON_TAG_VOCABULARY[:20])}

Return a JSON object with exactly these keys:
1. "company_name": The company or brand name visible in the UI (if identifiable, otherwise "")
2. "product_category": The type of product/app (e.g., "mobile banking app", "e-commerce website", "productivity tool")
3. "descriptive_tags": An array of 8-12 specific UI element and feature tags

IMPORTANT: Tags should use spaces between words, NOT hyphens. Example: ["login screen", "navigation bar", "blue color scheme"] not ["login-screen", "navigation-bar", "blue-color-scheme"]

Example response:
{{
  "company_name": "Chase Bank",
  "product_category": "mobile banking app",
  "descriptive_tags": [
    "login screen", "two factor auth", "biometric login", "minimalist design",
    "blue color scheme", "sans serif typography", "centered layout",
    "secure badge", "mobile first", "ios design"
  ]
}}

Respond with JSON only, no additional text."""

    try:
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.MAX_TOKENS,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _guess_media_type(image_path),
                            "data": encode_image(image_path),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        raw = _extract_text_from_response(response)
        parsed = parse_json_response(raw)
        normalized = _normalize_keys(parsed)

        # Ensure final structure and limit tags
        tags = normalized.get("descriptive_tags", [])
        return {
            "company_name": normalized.get("company_name", ""),
            "product_category": normalized.get("product_category", ""),
            "descriptive_tags": tags[:config.MAX_TAGS_PER_IMAGE],
        }

    except Exception as e:
        print(f"Error generating tags for {image_path}: {e}")
        import traceback
        traceback.print_exc()  # Print full error for debugging
        return {"company_name": "", "product_category": "", "descriptive_tags": []}
