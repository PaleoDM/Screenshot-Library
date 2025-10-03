"""
Search utilities for querying the screenshot database
"""
from utils_db import get_or_create_collection
import config


def search_screenshots(query, n_results=None, project_filter=None):
    """
    Search for screenshots using natural language query
    
    Args:
        query: Natural language search query
        n_results: Number of results to return (default from config)
        project_filter: Optional project name to filter results
    
    Returns:
        List of screenshot dictionaries with paths, metadata, and similarity scores
    """
    if n_results is None:
        n_results = config.DEFAULT_SEARCH_RESULTS
    
    collection = get_or_create_collection()
    
    # Build where clause for project filtering
    where_clause = None
    if project_filter and project_filter != "All Projects":
        where_clause = {"project_name": project_filter}
    
    try:
        # Query using CLIP embeddings - ChromaDB will convert the text query to embedding
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        
        # Format results
        screenshots = []
        if results['ids'] and results['ids'][0]:  # Check if we got results
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i]
                screenshots.append({
                    'id': results['ids'][0][i],
                    'path': metadata['file_path'],
                    'project': metadata['project_name'],
                    'company_name': metadata.get('company_name', ''),
                    'product_category': metadata.get('product_category', ''),
                    'project_tags': metadata.get('project_tags', '').split(',') if metadata.get('project_tags') else [],
                    'descriptive_tags': metadata.get('descriptive_tags', '').split(',') if metadata.get('descriptive_tags') else [],
                    # Keep image_tags for backwards compatibility
                    'image_tags': metadata.get('descriptive_tags', metadata.get('image_tags', '')).split(',') if metadata.get('descriptive_tags', metadata.get('image_tags')) else [],
                    'distance': results['distances'][0][i] if 'distances' in results else None,
                    'similarity': 1 - results['distances'][0][i] if 'distances' in results else None
                })
        
        return screenshots
    
    except Exception as e:
        print(f"Error searching screenshots: {e}")
        return []


def search_by_tags(tag_query, n_results=None, project_filter=None):
    """
    Search screenshots by matching tags (text-based search)
    
    Args:
        tag_query: Tag or tags to search for
        n_results: Number of results to return
        project_filter: Optional project name to filter results
    
    Returns:
        List of screenshot dictionaries
    """
    if n_results is None:
        n_results = config.DEFAULT_SEARCH_RESULTS
    
    collection = get_or_create_collection()
    
    # Build where clause
    where_clause = {}
    if project_filter and project_filter != "All Projects":
        where_clause["project_name"] = project_filter
    
    try:
        # Get all items (we'll filter client-side for tag matching)
        results = collection.get(
            where=where_clause if where_clause else None
        )
        
        # Filter by tags containing the query
        tag_query_lower = tag_query.lower()
        matching_screenshots = []
        
        if results['ids']:
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                all_tags = metadata.get('all_tags', '').lower()
                
                if tag_query_lower in all_tags:
                    matching_screenshots.append({
                        'id': doc_id,
                        'path': metadata['file_path'],
                        'project': metadata['project_name'],
                        'company_name': metadata.get('company_name', ''),
                        'product_category': metadata.get('product_category', ''),
                        'project_tags': metadata.get('project_tags', '').split(',') if metadata.get('project_tags') else [],
                        'descriptive_tags': metadata.get('descriptive_tags', '').split(',') if metadata.get('descriptive_tags') else [],
                        # Keep image_tags for backwards compatibility
                        'image_tags': metadata.get('descriptive_tags', metadata.get('image_tags', '')).split(',') if metadata.get('descriptive_tags', metadata.get('image_tags')) else [],
                    })
        
        return matching_screenshots[:n_results]
    
    except Exception as e:
        print(f"Error searching by tags: {e}")
        return []