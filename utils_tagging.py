"""
Utility functions for generating tags using Anthropic Claude Vision
"""
import os
import json
import base64
from typing import List, Dict, Any
from anthropic import Anthropic
from pathlib import Path
from prompts_config import COMMON_TAG_VOCABULARY, TAG_FOCUS_INSTRUCTION
from tag_normalization import normalize_category

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def encode_image(image_path: str) -> str:
    """Encode image to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def parse_json_response(response_text: str) -> Dict[str, Any]:
    """Parse JSON from Claude's response, handling various formats"""
    try:
        # Try direct JSON parse
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
            return json.loads(json_str)
        else:
            # Fallback: try to parse as-is after stripping whitespace
            return json.loads(response_text.strip())

def generate_project_tags(image_paths: List[str], project_name: str) -> List[str]:
    """
    Generate project-level tags by analyzing multiple screenshots together
    Returns common themes and patterns across all images
    """
    if not image_paths:
        return []
    
    # Sample up to 5 images for project analysis (to manage API costs)
    sample_paths = image_paths[:5] if len(image_paths) > 5 else image_paths
    
    # Prepare message content with multiple images
    content = [
        {
            "type": "text",
            "text": f"""Analyze these UI screenshots from the project "{project_name}".
            
Identify COMMON themes, patterns, and characteristics shared across these interfaces.
Focus on:
1. Shared design patterns or UI elements that appear multiple times
2. Common functionality or features
3. Overall design style or methodology
4. Target audience or use case

Return a JSON object with a single key "project_tags" containing an array of 5-10 common tags.
Tags should be lowercase, concise, and focused on SHARED characteristics.

Example: {{"project_tags": ["mobile-first", "dark-mode", "social-features", "card-based-layout", "onboarding-flow"]}}"""
        }
    ]
    
    # Add each image to the message
    for i, image_path in enumerate(sample_paths, 1):
        content.append({
            "type": "text",
            "text": f"Image {i} of {len(sample_paths)}:"
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": encode_image(image_path)
            }
        })
    
    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Using Haiku for cost efficiency on batch analysis
            max_tokens=500,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": content
            }]
        )
        
        result = parse_json_response(response.content[0].text)
        return result.get("project_tags", [])
        
    except Exception as e:
        print(f"Error generating project tags: {e}")
        # Fallback tags based on project name
        return [project_name.lower().replace(" ", "-"), "ui-design", "interface"]

def generate_image_tags(image_path: str, project_tags: List[str] = None) -> Dict[str, Any]:
    """
    Generate structured tags for a single image
    Returns company name, product category, and descriptive tags
    """
    if project_tags is None:
        project_tags = []
    
    # Build the prompt
    prompt = f"""Analyze this UI screenshot and extract structured information.

{TAG_FOCUS_INSTRUCTION}

Context: This image is part of a project with these tags: {', '.join(project_tags) if project_tags else 'No project context'}

Vocabulary suggestions (use when relevant): {', '.join(COMMON_TAG_VOCABULARY[:20])}

Return a JSON object with exactly these keys:
1. "company_name": The company or brand name visible in the UI (if identifiable, otherwise "")
2. "product_category": The type of product/app (e.g., "mobile banking app", "e-commerce website", "productivity tool")
3. "descriptive_tags": An array of 8-12 specific UI element and feature tags

Example response:
{{
    "company_name": "Chase Bank",
    "product_category": "mobile banking app",
    "descriptive_tags": ["login-screen", "two-factor-auth", "biometric-login", "minimalist-design", "blue-color-scheme", "sans-serif-typography", "centered-layout", "secure-badge", "mobile-first", "ios-design"]
}}"""
    
    try:
        # Prepare the message
        response = client.messages.create(
            model="claude-3-sonnet-20240229",  # Sonnet for good quality/cost balance
            max_tokens=500,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": encode_image(image_path)
                        }
                    }
                ]
            }]
        )
        
        # Parse the response
        result = parse_json_response(response.content[0].text)
        
        # Normalize the product category
        if result.get("product_category"):
            result["product_category"] = normalize_category(result["product_category"])
        
        # Ensure all required fields exist
        return {
            "company_name": result.get("company_name", ""),
            "product_category": result.get("product_category", ""),
            "descriptive_tags": result.get("descriptive_tags", [])
        }
        
    except Exception as e:
        print(f"Error generating tags for {image_path}: {e}")
        # Return empty structure on error
        return {
            "company_name": "",
            "product_category": "",
            "descriptive_tags": []
        }