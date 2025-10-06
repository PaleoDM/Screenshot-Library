"""
Database utilities for ChromaDB operations
"""
import chromadb
from chromadb.utils import embedding_functions
import config
import os
from PIL import Image
import io


def get_chroma_client():
    """Initialize and return ChromaDB client"""
    client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
    return client


def get_or_create_collection():
    """Get or create the screenshots collection with CLIP embeddings"""
    client = get_chroma_client()
    
    # Use CLIP for image embeddings
    clip_ef = embedding_functions.OpenCLIPEmbeddingFunction()
    
    collection = client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        embedding_function=clip_ef,
        metadata={"hnsw:space": "cosine"}
    )
    
    return collection


def add_screenshot_to_db(image_path, project_name, project_tags, image_data):
    """
    Add a screenshot to the database with embeddings and structured metadata
    
    Args:
        image_path: Path to the image file
        project_name: Name of the project
        project_tags: List of project-level tags
        image_data: Dict with company_name, product_category, and descriptive_tags
    """
    try:
        collection = get_or_create_collection()
        
        # Create unique ID from path
        doc_id = f"{project_name}_{os.path.basename(image_path)}"
        
        # Extract structured data
        company_name = image_data.get('company_name', '')
        product_category = image_data.get('product_category', '')
        descriptive_tags = image_data.get('descriptive_tags', [])
        
        # Combine all tags for search
        all_tags = list(set(project_tags + descriptive_tags))
        
        # Prepare metadata with structured fields
        metadata = {
            "project_name": project_name,
            "file_path": image_path,
            "company_name": company_name,
            "product_category": product_category,
            "project_tags": ",".join(project_tags),
            "descriptive_tags": ",".join(descriptive_tags),
            "all_tags": ",".join(all_tags)
        }
        
        # Read image for embedding
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create a data URI for CLIP
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            
            # Add to collection
            collection.add(
                ids=[doc_id],
                metadatas=[metadata],
                documents=[image_path]
            )
        
        return doc_id
    
    except Exception as e:
        import traceback
        import sys
        print(f"ERROR in add_screenshot_to_db for {image_path}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise  # Re-raise to see the full error in Streamlit


def get_all_screenshots():
    """
    Retrieve all screenshots from the database
    """
    collection = get_or_create_collection()
    
    try:
        results = collection.get()
        
        screenshots = []
        if results['ids']:
            for i, doc_id in enumerate(results['ids']):
                screenshots.append({
                    'id': doc_id,
                    'path': results['metadatas'][i]['file_path'],
                    'project': results['metadatas'][i]['project_name'],
                    'company_name': results['metadatas'][i].get('company_name', ''),
                    'product_category': results['metadatas'][i].get('product_category', ''),
                    'project_tags': results['metadatas'][i]['project_tags'].split(','),
                    'descriptive_tags': results['metadatas'][i].get('descriptive_tags', '').split(',') if results['metadatas'][i].get('descriptive_tags') else [],
                    # Keep image_tags for backwards compatibility
                    'image_tags': results['metadatas'][i].get('descriptive_tags', results['metadatas'][i].get('image_tags', '')).split(',') if results['metadatas'][i].get('descriptive_tags', results['metadatas'][i].get('image_tags')) else [],
                })
        
        return screenshots
    except Exception as e:
        print(f"Error retrieving screenshots: {e}")
        return []


def update_screenshot_metadata(doc_id, new_data):
    """
    Update metadata for an existing screenshot
    
    Args:
        doc_id: Document ID
        new_data: Dict with company_name, product_category, and descriptive_tags
    """
    collection = get_or_create_collection()
    
    try:
        # Get existing metadata
        result = collection.get(ids=[doc_id])
        
        if not result['ids']:
            return False
        
        existing_metadata = result['metadatas'][0]
        
        # Update with new data
        existing_metadata['company_name'] = new_data.get('company_name', '')
        existing_metadata['product_category'] = new_data.get('product_category', '')
        
        descriptive_tags = new_data.get('descriptive_tags', [])
        existing_metadata['descriptive_tags'] = ",".join(descriptive_tags)
        
        # Update all_tags (project_tags + descriptive_tags)
        project_tags = existing_metadata.get('project_tags', '').split(',')
        all_tags = list(set(project_tags + descriptive_tags))
        existing_metadata['all_tags'] = ",".join(all_tags)
        
        # Update in collection
        collection.update(
            ids=[doc_id],
            metadatas=[existing_metadata]
        )
        
        return True
    
    except Exception as e:
        print(f"Error updating screenshot {doc_id}: {e}")
        return False


def update_project_tags(project_name, new_project_tags):
    """
    Update project-level tags for all screenshots in a project
    
    Args:
        project_name: Name of the project
        new_project_tags: List of new project tags to apply
    
    Returns:
        Number of screenshots updated
    """
    collection = get_or_create_collection()
    
    try:
        # Get all screenshots from this project
        results = collection.get(
            where={"project_name": project_name}
        )
        
        if not results['ids']:
            return 0
        
        # Update each screenshot's project tags
        for i, doc_id in enumerate(results['ids']):
            metadata = results['metadatas'][i]
            
            # Update project_tags
            metadata['project_tags'] = ",".join(new_project_tags)
            
            # Recalculate all_tags (project_tags + descriptive_tags)
            descriptive_tags = metadata.get('descriptive_tags', '').split(',') if metadata.get('descriptive_tags') else []
            all_tags = list(set(new_project_tags + descriptive_tags))
            metadata['all_tags'] = ",".join(all_tags)
            
            # Update in collection
            collection.update(
                ids=[doc_id],
                metadatas=[metadata]
            )
        
        return len(results['ids'])
    
    except Exception as e:
        print(f"Error updating project tags for {project_name}: {e}")
        return 0


def delete_screenshot(doc_id):
    """
    Delete a screenshot from the database and remove the physical file
    """
    collection = get_or_create_collection()
    
    try:
        # Get the file path before deleting from DB
        result = collection.get(ids=[doc_id])
        
        if result['ids']:
            file_path = result['metadatas'][0]['file_path']
            
            # Delete from database
            collection.delete(ids=[doc_id])
            
            # Delete physical file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
            
            return True
        return False
    except Exception as e:
        print(f"Error deleting screenshot {doc_id}: {e}")
        return False


def delete_project(project_name):
    """
    Delete all screenshots from a specific project and remove the physical folder
    """
    collection = get_or_create_collection()
    
    try:
        # Get all items from this project
        results = collection.get(
            where={"project_name": project_name}
        )
        
        if results['ids']:
            # Delete from database
            collection.delete(ids=results['ids'])
            
            # Delete physical project folder
            from pathlib import Path
            project_folder = Path("screenshots_library") / project_name
            if project_folder.exists():
                import shutil
                shutil.rmtree(project_folder)
                print(f"Deleted folder: {project_folder}")
            
            return len(results['ids'])
        return 0
    except Exception as e:
        print(f"Error deleting project {project_name}: {e}")
        return 0


def get_database_stats():
    """
    Get statistics about the database
    """
    collection = get_or_create_collection()
    
    try:
        results = collection.get()
        total_images = len(results['ids'])
        
        # Count unique projects
        projects = set()
        if results['metadatas']:
            projects = {meta['project_name'] for meta in results['metadatas']}
        
        return {
            'total_images': total_images,
            'total_projects': len(projects),
            'projects': list(projects)
        }
    except Exception as e:
        print(f"Error getting database stats: {e}")
        return {'total_images': 0, 'total_projects': 0, 'projects': []}
