"""
UI Screenshot Search - Multimodal RAG Application
Main Streamlit application for batch uploading and managing UI screenshots
"""
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import os
from pathlib import Path
from PIL import Image
import base64
import config
from utils_tagging import generate_project_tags, generate_image_tags
from utils_db import (
    add_screenshot_to_db, 
    get_all_screenshots, 
    delete_screenshot,
    delete_project,
    get_database_stats,
    update_screenshot_metadata,
    update_project_tags
)
from utils_search import search_screenshots, search_by_tags

# Ensure required directories exist for Streamlit Cloud
os.makedirs("/tmp/chroma_db", exist_ok=True)
os.makedirs("screenshots_library", exist_ok=True)

# Page configuration
st.set_page_config(
    page_title="UI Design Reference Library",
    page_icon="🔍",
    layout="wide"
)

# --- Handle ?home=1 "go home" link ---
if st.query_params.get("home") == "1":
    # Clear any search or filter states if desired
    for key in ["search_query", "search_project_filter", "search_company_filter", "search_category_filter"]:
        st.session_state.pop(key, None)
    
    # Clear the param so it disappears from the URL, then rerun
    try:
        del st.query_params["home"]
    except Exception:
        # fallback if deletion fails on your version
        st.query_params.clear()
    st.rerun()

# -----------------------------
# Clickable Logo Function
# -----------------------------
def clickable_logo(path: str, width: int = 260, alt: str = "Code.org Logo"):
    """Create a clickable logo that returns to home"""
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        st.markdown(
            f"""
            <div style="display:flex; justify-content:center; margin: 8px 0 16px;">
                <a href="?home=1" target="_self" style="text-decoration:none;">
                    <img src="data:image/png;base64,{b64}" alt="{alt}" width="{width}">
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Fallback if logo file doesn't exist
        st.markdown(
            """
            <div style="display:flex; justify-content:center; margin: 8px 0 16px;">
                <a href="?home=1" target="_self" style="text-decoration:none; font-size: 24px; font-weight: bold; color: #0066cc;">
                    Code.org
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

# Display clickable logo at top
clickable_logo("codeorg-logo.png", width=260)
st.markdown("---")

# Main App Title
st.title("UI Design Reference Library")
st.markdown("Upload and manage your library of UI design references")




# Custom CSS for Code.org branding
# ========= Code.org Branding CSS =========
st.markdown(
    f"""
    <style>
    :root {{
      --cod-primary: #00adbc;
      --cod-primary-dark: #009aa8;
      --cod-text: #2b2b2b;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --cod-text: #e8e8e8;
      }}
    }}

    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap');

    html, body, [class*="css"] {{
      font-family: "Gotham Rounded", "Nunito", Arial, sans-serif !important;
      color: var(--cod-text);
    }}

    .stButton > button {{
      border-radius: 10px;
      font-weight: 600;
      padding: 0.6em 1.2em;
      outline: none;
    }}
    .stButton > button:hover {{
      filter: brightness(0.92);
    }}
    .stButton > button:focus-visible {{
      box-shadow: 0 0 0 3px rgba(0,173,188,0.35);
    }}

    /* Tabs underline height */
    div[role="tablist"] > div[aria-selected="true"]::after {{ height: 3px; }}

    /* Centered logo container + responsive image */
    .cod-logo-wrap {{
      display:flex; justify-content:center; margin: 8px 0 16px;
    }}
    .cod-logo-wrap img {{
      height: auto;
      max-width: 100%;
      image-rendering: -webkit-optimize-contrast;
    }}

    /* Subtle divider */
    .cod-divider {{
      margin: 8px 0 24px; opacity: 0.75; border: none; height: 1px; background: rgba(0,0,0,0.1);
    }}
    </style>
    """,
    unsafe_allow_html=True
)




# Initialize session state
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'project_tags' not in st.session_state:
    st.session_state.project_tags = []
if 'image_data_dict' not in st.session_state:
    st.session_state.image_data_dict = {}
if 'project_name' not in st.session_state:
    st.session_state.project_name = ""
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'upload_key' not in st.session_state:
    st.session_state.upload_key = 0


def is_image_file(filename):
    """Check if file is a supported image format"""
    return any(filename.lower().endswith(ext) for ext in config.SUPPORTED_IMAGE_FORMATS)


def save_uploaded_files(uploaded_files, project_name):
    """Save uploaded files temporarily and return paths"""
    temp_dir = Path("screenshots_library") / project_name
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    for uploaded_file in uploaded_files:
        if is_image_file(uploaded_file.name):
            file_path = temp_dir / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            saved_paths.append(str(file_path))
    
    return saved_paths


def get_unique_companies():
    """Get list of unique company names from database"""
    all_screenshots = get_all_screenshots()
    companies = set()
    for screenshot in all_screenshots:
        if screenshot.get('company_name'):
            companies.add(screenshot['company_name'])
    return sorted(list(companies))


def get_unique_categories():
    """Get list of unique product categories from database"""
    all_screenshots = get_all_screenshots()
    categories = set()
    for screenshot in all_screenshots:
        if screenshot.get('product_category'):
            categories.add(screenshot['product_category'])
    return sorted(list(categories))


def display_image_grid(screenshots, columns=3, show_similarity=False, allow_edit=False, allow_preview=False, allow_delete=True):
    """Display screenshots in a grid with delete and optional edit buttons"""
    if not screenshots:
        st.info("No screenshots found.")
        return
    
    for i in range(0, len(screenshots), columns):
        cols = st.columns(columns)
        for j, col in enumerate(cols):
            if i + j < len(screenshots):
                screenshot = screenshots[i + j]
                with col:
                    try:
                        # Display image with optional click-to-preview
                        if os.path.exists(screenshot['path']):
                            img = Image.open(screenshot['path'])
                            
                            # If preview enabled, make image clickable
                            if allow_preview:
                                if st.button("🔍 Preview", key=f"preview_{screenshot['id']}_{i}_{j}", use_container_width=True):
                                    st.session_state.preview_id = screenshot['id']
                                
                                # Show preview inline if this is the selected one
                                if st.session_state.get('preview_id') == screenshot['id']:
                                    with st.container():
                                        st.divider()
                                        st.subheader("Preview")
                                        
                                        # Display all metadata
                                        preview_col1, preview_col2 = st.columns(2)
                                        with preview_col1:
                                            st.markdown(f"**Project:** {screenshot['project']}")
                                            if screenshot.get('company_name'):
                                                st.markdown(f"**Company:** {screenshot['company_name']}")
                                            if screenshot.get('product_category'):
                                                st.markdown(f"**Category:** {screenshot['product_category']}")
                                        
                                        with preview_col2:
                                            if screenshot.get('similarity') is not None:
                                                similarity_pct = screenshot['similarity'] * 100
                                                st.markdown(f"**Match Score:** {similarity_pct:.1f}%")
                                            st.markdown(f"**File:** {os.path.basename(screenshot['path'])}")
                                        
                                        # Show all tags
                                        if screenshot.get('project_tags') and screenshot['project_tags']:
                                            project_tags_display = ', '.join([tag for tag in screenshot['project_tags'] if tag])
                                            if project_tags_display:
                                                st.markdown(f"**Project Tags:** {project_tags_display}")
                                        
                                        if screenshot.get('image_tags'):
                                            descriptive_tags_display = ', '.join(screenshot['image_tags'])
                                            st.markdown(f"**Descriptive Tags:** {descriptive_tags_display}")
                                        
                                        if st.button("Close Preview", key=f"close_preview_{screenshot['id']}"):
                                            st.session_state.preview_id = None
                                            st.rerun()
                                        st.divider()
                            
                            st.image(img, use_container_width=True)
                        else:
                            st.warning(f"Image not found: {screenshot['path']}")
                        
                        # Display metadata
                        st.caption(f"**Project:** {screenshot['project']}")
                        
                        # Show project tags if available
                        if screenshot.get('project_tags') and screenshot['project_tags']:
                            project_tags_display = ', '.join([tag for tag in screenshot['project_tags'] if tag])
                            if project_tags_display:
                                st.caption(f"**Project Tags:** {project_tags_display}")
                        
                        # Show company and category if available
                        if screenshot.get('company_name'):
                            st.caption(f"**Company:** {screenshot['company_name']}")
                        if screenshot.get('product_category'):
                            st.caption(f"**Category:** {screenshot['product_category']}")
                        
                        # Show similarity score if available
                        if show_similarity and screenshot.get('similarity') is not None:
                            similarity_pct = screenshot['similarity'] * 100
                            st.caption(f"**Match:** {similarity_pct:.1f}%")
                        
                        st.caption(f"**Tags:** {', '.join(screenshot['image_tags'][:3])}")
                        
                        # Button row with Edit and Delete (3:1 ratio)
                        button_col1, button_col2 = st.columns([3, 1])
                        
                        # Edit button (if enabled) - using expander for speed
                        if allow_edit:
                            with button_col1:
                                edit_expander = st.expander("✏️ Edit", expanded=False)
                            
                            with edit_expander:
                                # Editable company name
                                new_company = st.text_input(
                                    "Company/Brand",
                                    value=screenshot.get('company_name', ''),
                                    key=f"edit_company_{screenshot['id']}_{i}_{j}"
                                )
                                
                                # Editable category
                                new_category = st.text_input(
                                    "Product Category",
                                    value=screenshot.get('product_category', ''),
                                    key=f"edit_category_{screenshot['id']}_{i}_{j}"
                                )
                                
                                # Editable tags
                                current_tags = screenshot.get('descriptive_tags', screenshot.get('image_tags', []))
                                tags_str = ", ".join(current_tags)
                                new_tags = st.text_area(
                                    "Descriptive Tags",
                                    value=tags_str,
                                    key=f"edit_tags_{screenshot['id']}_{i}_{j}",
                                    height=80
                                )
                                
                                if st.button("💾 Save", key=f"save_{screenshot['id']}_{i}_{j}", use_container_width=True):
                                    # Update the screenshot in database
                                    new_data = {
                                        'company_name': new_company.strip(),
                                        'product_category': new_category.strip().lower(),
                                        'descriptive_tags': [tag.strip().lower() for tag in new_tags.split(',') if tag.strip()]
                                    }
                                    
                                    if update_screenshot_metadata(screenshot['id'], new_data):
                                        st.success("Saved!")
                                        st.rerun()
                                    else:
                                        st.error("Error saving changes")
                        
                        # Delete button - compact red X (only if allowed)
                        if allow_delete:
                            with button_col2:
                                if st.button("❌", key=f"delete_{screenshot['id']}_{i}_{j}", use_container_width=True, type="secondary"):
                                    if delete_screenshot(screenshot['id']):
                                        st.success("Deleted!")
                                        st.rerun()
                                    else:
                                        st.error("Error deleting screenshot")
                    
                    except Exception as e:
                        st.error(f"Error displaying image: {e}")


@st.dialog("Screenshot Preview")
def show_preview_dialog(screenshot):
    """Display full screenshot with all metadata in a dialog"""
    # Display large image
    if os.path.exists(screenshot['path']):
        img = Image.open(screenshot['path'])
        st.image(img, use_container_width=True)
    else:
        st.warning(f"Image not found: {screenshot['path']}")
    
    # Display all metadata
    st.subheader("Details")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Project:** {screenshot['project']}")
        if screenshot.get('company_name'):
            st.markdown(f"**Company:** {screenshot['company_name']}")
        if screenshot.get('product_category'):
            st.markdown(f"**Category:** {screenshot['product_category']}")
    
    with col2:
        if screenshot.get('similarity') is not None:
            similarity_pct = screenshot['similarity'] * 100
            st.markdown(f"**Match Score:** {similarity_pct:.1f}%")
        st.markdown(f"**File:** {os.path.basename(screenshot['path'])}")
    
    # Show all tags
    if screenshot.get('project_tags') and screenshot['project_tags']:
        project_tags_display = ', '.join([tag for tag in screenshot['project_tags'] if tag])
        if project_tags_display:
            st.markdown(f"**Project Tags:** {project_tags_display}")
    
    if screenshot.get('image_tags'):
        descriptive_tags_display = ', '.join(screenshot['image_tags'])
        st.markdown(f"**Descriptive Tags:** {descriptive_tags_display}")


# Sidebar for database stats
with st.sidebar:
    st.header("📊 Database Stats")
    stats = get_database_stats()
    st.metric("Total Screenshots", stats['total_images'])
    st.metric("Total Projects", stats['total_projects'])
    
    if stats['projects']:
        st.subheader("Projects")
        for project in stats['projects']:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(project)
            with col2:
                if st.button("❌", key=f"delete_project_{project}"):
                    deleted_count = delete_project(project)
                    st.success(f"Deleted {deleted_count} images")
                    st.rerun()

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload New Project", "📚 Browse Library", "🔍 Search", "⚙️ Settings"])

with tab1:
    st.header("Upload Screenshots to a Project")
    
    # Get existing projects for dropdown
    existing_projects = get_database_stats()['projects']
    
    # Project selection mode
    col1, col2 = st.columns([3, 1])
    with col1:
        if existing_projects:
            project_mode = st.radio(
                "Is this a new or existing project?",
                ["Add to existing project", "Create new project"],
                horizontal=True
            )
        else:
            project_mode = "Create new project"
            st.info("No existing projects yet. Create your first project below.")
    
    # Project name input based on mode
    if project_mode == "Add to existing project" and existing_projects:
        project_name = st.selectbox(
            "Select Project",
            existing_projects,
            help="Choose an existing project to add screenshots to"
        )
    else:
        project_name = st.text_input(
            "Project Name",
            placeholder="e.g., Banking App Redesign",
            help="Give this batch of screenshots a project name"
        )
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Upload Screenshots",
        type=['png', 'jpg', 'jpeg', 'webp'],
        accept_multiple_files=True,
        help="Select multiple screenshots from your project",
        key=f"file_uploader_{st.session_state.upload_key}"
    )
    
    if uploaded_files and project_name:
        st.success(f"✅ {len(uploaded_files)} files ready to upload")
        
        # Show info if adding to existing project
        if project_mode == "Add to existing project" and existing_projects:
            st.info(f"These screenshots will be added to the existing '{project_name}' project and will inherit its project-level tags.")
        
        if st.button("🚀 Process and Generate Tags", type="primary"):
            # Save files temporarily
            with st.spinner("Saving files..."):
                file_paths = save_uploaded_files(uploaded_files, project_name)
            
            # Generate project-level tags
            with st.spinner("Analyzing project for common themes..."):
                st.session_state.project_tags = generate_project_tags(file_paths, project_name)
            
            st.session_state.uploaded_files = file_paths
            st.session_state.project_name = project_name
            st.session_state.processing_complete = False
            st.rerun()
    
    # Tag review and confirmation
    if st.session_state.project_tags and not st.session_state.processing_complete:
        st.subheader("Step 1: Review Project Tags")
        st.info("These tags will be applied to all screenshots in this project")
        
        # Editable project tags
        tags_string = ", ".join(st.session_state.project_tags)
        edited_tags = st.text_area(
            "Edit Project Tags",
            value=tags_string,
            help="Comma-separated tags. Edit as needed."
        )
        
        final_project_tags = [tag.strip().lower() for tag in edited_tags.split(',') if tag.strip()]
        
        st.subheader("Step 2: Review Individual Image Details")
        st.info("Edit company name, category, and tags for each screenshot below")
        
        # Generate individual tags if not already done
        if not st.session_state.image_data_dict:
            import time
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, image_path in enumerate(st.session_state.uploaded_files):
                status_text.text(f"Generating tags for image {idx + 1}/{len(st.session_state.uploaded_files)}: {os.path.basename(image_path)}")
                
                image_data = generate_image_tags(image_path, final_project_tags)
                st.session_state.image_data_dict[image_path] = image_data
                
                # Update progress
                progress_bar.progress((idx + 1) / len(st.session_state.uploaded_files))
                
                # Add delay to avoid rate limits (skip delay for last image)
                if idx < len(st.session_state.uploaded_files) - 1:
                    time.sleep(2)  # 2 second delay between API calls
            
            status_text.text("✅ Tag generation complete!")
            progress_bar.empty()
            status_text.empty()
        
        # Display images in grid with editable structured fields
        for i in range(0, len(st.session_state.uploaded_files), config.IMAGES_PER_ROW):
            cols = st.columns(config.IMAGES_PER_ROW)
            for j, col in enumerate(cols):
                if i + j < len(st.session_state.uploaded_files):
                    image_path = st.session_state.uploaded_files[i + j]
                    with col:
                        # Display image
                        img = Image.open(image_path)
                        st.image(img, use_container_width=True)
                        
                        # Display filename
                        st.caption(f"**{os.path.basename(image_path)}**")
                        
                        # Get current data
                        current_data = st.session_state.image_data_dict.get(image_path, {
                            'company_name': '',
                            'product_category': '',
                            'descriptive_tags': []
                        })
                        
                        # Editable company name (required)
                        company_name = st.text_input(
                            "Company/Brand *",
                            value=current_data.get('company_name', ''),
                            key=f"company_{i}_{j}",
                            placeholder="e.g., Chase Bank"
                        )
                        
                        # Editable product category (required)
                        product_category = st.text_input(
                            "Product Category *",
                            value=current_data.get('product_category', ''),
                            key=f"category_{i}_{j}",
                            placeholder="e.g., mobile banking app"
                        )
                        
                        # Editable descriptive tags
                        tags_list = current_data.get('descriptive_tags', [])
                        tags_str = ", ".join(tags_list)
                        
                        descriptive_tags = st.text_area(
                            "Descriptive Tags",
                            value=tags_str,
                            key=f"tags_{i}_{j}",
                            height=80,
                            help="Additional UI element tags"
                        )
                        
                        # Update data in session state
                        st.session_state.image_data_dict[image_path] = {
                            'company_name': company_name.strip(),
                            'product_category': product_category.strip().lower(),
                            'descriptive_tags': [tag.strip().lower() for tag in descriptive_tags.split(',') if tag.strip()]
                        }
        
        st.divider()
        
        # Validation: check if all required fields are filled
        all_valid = True
        missing_fields = []
        for image_path, data in st.session_state.image_data_dict.items():
            if not data.get('company_name') or not data.get('product_category'):
                all_valid = False
                missing_fields.append(os.path.basename(image_path))
        
        if not all_valid:
            st.warning(f"⚠️ Please fill in Company and Category for all images. Missing: {', '.join(missing_fields[:3])}{'...' if len(missing_fields) > 3 else ''}")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("✅ Confirm & Add to Library", type="primary", disabled=not all_valid):
                # Process each image
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                num_added = 0
                for idx, image_path in enumerate(st.session_state.uploaded_files):
                    status_text.text(f"Processing {idx + 1}/{len(st.session_state.uploaded_files)}: {os.path.basename(image_path)}")
                    
                    # Get the edited data
                    image_data = st.session_state.image_data_dict.get(image_path)
                    
                    # Add to database
                    add_screenshot_to_db(
                        image_path,
                        st.session_state.project_name,
                        final_project_tags,
                        image_data
                    )
                    
                    num_added += 1
                    progress_bar.progress((idx + 1) / len(st.session_state.uploaded_files))
                
                status_text.text("✅ All screenshots processed!")
                
                # Clear session state and increment upload key to reset file uploader
                st.session_state.processing_complete = True
                st.session_state.project_tags = []
                st.session_state.uploaded_files = []
                st.session_state.image_data_dict = {}
                st.session_state.project_name = ""
                st.session_state.upload_key += 1
                
                st.success(f"Successfully added {num_added} screenshots to your library!")
                st.balloons()
                st.rerun()
        
        with col2:
            if st.button("❌ Cancel"):
                st.session_state.project_tags = []
                st.session_state.uploaded_files = []
                st.session_state.image_data_dict = {}
                st.session_state.project_name = ""
                st.session_state.upload_key += 1
                st.rerun()

with tab2:
    st.header("Reference Library")
    
    # Filter options
    col1, col2 = st.columns([2, 1])
    with col1:
        filter_project = st.selectbox(
            "Filter by Project",
            ["All Projects"] + get_database_stats()['projects']
        )
    
    # Edit Project Tags button (only shows when a specific project is selected)
    if filter_project != "All Projects":
        with st.expander("✏️ Edit Project Tags", expanded=False):
            st.info(f"These tags apply to all screenshots in '{filter_project}'")
            
            # Get current project tags from any screenshot in the project
            all_screenshots = get_all_screenshots()
            project_screenshots = [s for s in all_screenshots if s['project'] == filter_project]
            
            if project_screenshots:
                current_project_tags = project_screenshots[0].get('project_tags', [])
                project_tags_str = ", ".join([tag for tag in current_project_tags if tag])
                
                edited_project_tags = st.text_area(
                    "Project Tags",
                    value=project_tags_str,
                    height=100,
                    help="Comma-separated tags that apply to all screenshots in this project"
                )
                
                if st.button("💾 Save Project Tags", use_container_width=True):
                    new_tags = [tag.strip().lower() for tag in edited_project_tags.split(',') if tag.strip()]
                    updated_count = update_project_tags(filter_project, new_tags)
                    if updated_count > 0:
                        st.success(f"✅ Updated {updated_count} screenshots with new project tags!")
                        st.rerun()
                    else:
                        st.error("Error updating project tags")
    
    # Get and display screenshots
    all_screenshots = get_all_screenshots()
    
    if filter_project != "All Projects":
        filtered_screenshots = [s for s in all_screenshots if s['project'] == filter_project]
    else:
        filtered_screenshots = all_screenshots
    
    st.subheader(f"Showing {len(filtered_screenshots)} screenshots")
    
    display_image_grid(filtered_screenshots, columns=config.IMAGES_PER_ROW, allow_edit=True)

with tab3:
    st.header("🔍 Search Library")
    
    # Check if database has any images
    stats = get_database_stats()
    if stats['total_images'] == 0:
        st.info("🔭 No screenshots in your library yet. Upload some in the 'Upload New Project' tab!")
    else:
        # Search filters - Row 1: Project, Company, Category
        col1, col2, col3 = st.columns(3)
        with col1:
            project_filter = st.selectbox(
                "Filter by Project",
                ["All Projects"] + stats['projects'],
                key="search_project_filter"
            )
        with col2:
            company_filter = st.selectbox(
                "Filter by Company",
                ["All Companies"] + get_unique_companies(),
                key="search_company_filter"
            )
        with col3:
            category_filter = st.selectbox(
                "Filter by Category",
                ["All Categories"] + get_unique_categories(),
                key="search_category_filter"
            )
        
        # Search filters - Row 2: Search Type and Results Number
        col4, col5 = st.columns([3, 1])
        with col4:
            search_type = st.selectbox(
                "Search Type",
                ["Semantic", "Tag Match"],
                help="Semantic uses AI understanding, Tag Match searches exact tags"
            )
        with col5:
            num_results = st.number_input(
                "Limit Results",
                min_value=1,
                max_value=config.MAX_SEARCH_RESULTS,
                value=config.DEFAULT_SEARCH_RESULTS,
                help="Number of results to show"
            )
        
        # Chat-style search input with form to trigger on Enter
        with st.form(key="search_form", clear_on_submit=False):
            search_query = st.text_input(
                "What are you looking for?",
                placeholder="e.g., Can you show me examples of a login screen?",
                help="Type your search and press Enter",
                label_visibility="collapsed"
            )
            
            # Hidden submit button (Enter key will trigger this)
            submitted = st.form_submit_button("Search", type="primary")
        
        # Perform search when form is submitted
        if submitted and search_query:
            with st.spinner("Searching..."):
                if search_type == "Semantic":
                    results = search_screenshots(
                        search_query,
                        n_results=num_results,
                        project_filter=project_filter if project_filter != "All Projects" else None
                    )
                else:
                    results = search_by_tags(
                        search_query,
                        n_results=num_results,
                        project_filter=project_filter if project_filter != "All Projects" else None
                    )
                
                # Apply company and category filters to results
                if company_filter != "All Companies":
                    results = [r for r in results if r.get('company_name') == company_filter]
                
                if category_filter != "All Categories":
                    results = [r for r in results if r.get('product_category') == category_filter]
            
            if results:
                st.success(f"Found {len(results)} matching screenshots")
                display_image_grid(results, columns=config.IMAGES_PER_ROW, show_similarity=True, allow_delete=False)
            else:
                st.warning("No results found. Try a different search term or check your filters.")
        elif not search_query:
            st.info("💬 Type what you're looking for and press Enter to search")

with tab4:
    st.header("⚙️ Settings")
    st.markdown("Configure how the AI generates tags for your screenshots")
    
    # Section 1: Canonical Categories
    st.subheader("Canonical Categories")
    st.info("⚠️ **These are CONSTRAINING**—Similar categories will be automatically normalized to match these exact names. This prevents duplicates like 'mobile banking app' vs 'mobile banking application'. Curate this list to your preferences.")
    
    # Load current canonical categories
    import tag_normalization
    current_categories = tag_normalization.CANONICAL_CATEGORIES.copy()
    
    # Display categories as editable list
    categories_text = "\n".join(current_categories)
    edited_categories = st.text_area(
        "Edit categories (one per line)",
        value=categories_text,
        height=200,
        help="Add or remove categories. Each line is one category. These will be used to normalize similar categories."
    )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("💾 Save Categories", type="primary"):
            # Parse edited categories
            new_categories = [cat.strip().lower() for cat in edited_categories.split('\n') if cat.strip()]
            
            # Update the file
            try:
                with open('tag_normalization.py', 'r') as f:
                    content = f.read()
                
                # Replace the CANONICAL_CATEGORIES list
                import re
                pattern = r'CANONICAL_CATEGORIES = \[.*?\]'
                categories_str = '[\n    "' + '",\n    "'.join(new_categories) + '"\n]'
                new_content = re.sub(pattern, f'CANONICAL_CATEGORIES = {categories_str}', content, flags=re.DOTALL)
                
                with open('tag_normalization.py', 'w') as f:
                    f.write(new_content)
                
                st.success(f"✅ Saved {len(new_categories)} categories!")
                st.info("⚠️ Restart the app to apply changes")
            except Exception as e:
                st.error(f"Error saving: {e}")
    
    with col2:
        st.caption(f"Current: {len(current_categories)} categories")
    
    st.divider()
    
    # Section 2: Common Tag Vocabulary
    st.subheader("Common Tag Vocabulary")
    st.info("💡 **These are SUGGESTIONS**—The AI will prioritize these tag types when relevant, but can still generate other tags. This helps maintain consistency without being restrictive. If you want to focus on specific elements of a design, consider using these to nudge the AI in that direction.")
    
    # Load current tag vocabulary
    import prompts_config
    current_vocab = prompts_config.COMMON_TAG_VOCABULARY.copy()
    
    vocab_text = "\n".join(current_vocab)
    edited_vocab = st.text_area(
        "Edit tag vocabulary (one per line)",
        value=vocab_text,
        height=200,
        help="Common UI element types to suggest to the AI. The AI can still generate tags not on this list."
    )
    
    col3, col4 = st.columns([1, 3])
    with col3:
        if st.button("💾 Save Vocabulary", type="primary"):
            # Parse edited vocabulary
            new_vocab = [tag.strip().lower() for tag in edited_vocab.split('\n') if tag.strip()]
            
            # Update the file
            try:
                with open('prompts_config.py', 'r') as f:
                    content = f.read()
                
                # Replace the COMMON_TAG_VOCABULARY list
                import re
                pattern = r'COMMON_TAG_VOCABULARY = \[.*?\]'
                vocab_str = '[\n    "' + '",\n    "'.join(new_vocab) + '"\n]'
                new_content = re.sub(pattern, f'COMMON_TAG_VOCABULARY = {vocab_str}', content, flags=re.DOTALL)
                
                with open('prompts_config.py', 'w') as f:
                    f.write(new_content)
                
                st.success(f"✅ Saved {len(new_vocab)} vocabulary terms!")
                st.info("⚠️ Restart the app to apply changes")
            except Exception as e:
                st.error(f"Error saving: {e}")
    
    with col4:
        st.caption(f"Current: {len(current_vocab)} terms")
    
    st.divider()
    
    # Section 3: Prompt Instructions
    st.subheader("Tag Focus Instructions")
    st.info("Customize what design elements you would like the AI to focus on when generating descriptive tags.")
    
    current_instructions = prompts_config.TAG_FOCUS_INSTRUCTION
    
    edited_instructions = st.text_area(
        "Edit tag focus instructions",
        value=current_instructions,
        height=150,
        help="Describe what aspects of the UI the AI should focus on"
    )
    
    if st.button("💾 Save Instructions", type="primary"):
        try:
            with open('prompts_config.py', 'r') as f:
                content = f.read()
            
            # Replace TAG_FOCUS_INSTRUCTION
            import re
            pattern = r'TAG_FOCUS_INSTRUCTION = """.*?"""'
            new_content = re.sub(
                pattern, 
                f'TAG_FOCUS_INSTRUCTION = """{edited_instructions}"""', 
                content, 
                flags=re.DOTALL
            )
            
            with open('prompts_config.py', 'w') as f:
                f.write(new_content)
            
            st.success("✅ Saved instructions!")
            st.info("⚠️ Restart the app to apply changes")
        except Exception as e:
            st.error(f"Error saving: {e}")
    
    st.divider()
    
    # Section 4: Advanced Settings
    with st.expander("⚙️ Advanced Settings"):
        st.subheader("Similarity Threshold")
        st.markdown("Controls how similar a category must be to match a canonical category (0-1)")
        
        current_threshold = tag_normalization.SIMILARITY_THRESHOLD
        
        new_threshold = st.slider(
            "Similarity Threshold",
            min_value=0.5,
            max_value=1.0,
            value=current_threshold,
            step=0.05,
            help="Higher = more strict matching. 0.85 means 85% similar."
        )
        
        if st.button("💾 Save Threshold"):
            try:
                with open('tag_normalization.py', 'r') as f:
                    content = f.read()
                
                # Replace SIMILARITY_THRESHOLD
                import re
                pattern = r'SIMILARITY_THRESHOLD = [0-9.]+' 
                new_content = re.sub(pattern, f'SIMILARITY_THRESHOLD = {new_threshold}', content)
                
                with open('tag_normalization.py', 'w') as f:
                    f.write(new_content)
                
                st.success(f"✅ Saved threshold: {new_threshold}")
                st.info("⚠️ Restart the app to apply changes")
            except Exception as e:
                st.error(f"Error saving: {e}")


# -----------------------------
# Footer (render on every page)
# -----------------------------
st.markdown(
    """
    <hr style="margin-top:2em; margin-bottom:0.5em; border:none; height:1px; background:rgba(0,0,0,0.1);" />
    <div style="text-align:center; color:#666; font-size:0.9em; padding-bottom:0.25em;">
        A <strong>Vivitec AI</strong> Product | Developed by <strong>Dr. Carlos Mauricio Peredo</strong>
    </div>
    """,
    unsafe_allow_html=True,
)
