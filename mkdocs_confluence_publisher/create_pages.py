import logging
import os

from mkdocs.structure.nav import Page, Section

from .types import ConfluencePage, MD_to_Page

logger = logging.getLogger("mkdocs.plugins.confluence_publisher.create_pages")


class ConfluenceClient:
    """Client for interacting with Confluence."""

    def __init__(self, confluence):
        self._confluence = confluence

    def get_page_by_title(self, space_key: str, title: str):
        """Get a page by title."""
        return self._confluence.get_page_by_title(space_key, title)

    def get_child_pages(self, page_id: int | str):
        """Get child pages."""
        return self._confluence.get_child_pages(page_id)

    def create_page(self, space: str, title: str, body: str, parent_id: int | str):
        """Create a page."""
        return self._confluence.create_page(space=space, title=title, body=body, parent_id=parent_id)

    def remove_page(self, page_id: int | str):
        """Remove a page."""
        return self._confluence.remove_page(page_id)


class PageCreator:
    """Page creator for creating pages in Confluence."""

    def __init__(self, confluence_client: ConfluenceClient, prefix: str, suffix: str, space_key: str):
        self.confluence_client = confluence_client
        self.prefix = prefix
        self.suffix = suffix
        self.space_key = space_key
        self.active_page_ids = set()
        self.dir_to_id = {}

    def create_pages_in_space(self, items, parent_id, md_to_page: MD_to_Page):
        """Create pages in a space."""
        for item in items:
            title = item.title
            if not title and isinstance(item, Page):
                # Fallback for pages without titles (e.g. not yet parsed)
                title = self._get_title_from_file(item.file)

            page_title = f"{self.prefix}{title}{self.suffix}"
            logger.debug(f"Processing item: {page_title}")

            page_id = self.ensure_page_exists(page_title, parent_id, is_section=isinstance(item, Section))
            if not page_id:
                continue

            self.active_page_ids.add(str(page_id))

            if isinstance(item, Page):
                md_to_page[item.file.src_path] = ConfluencePage(id=page_id, title=page_title)
                logger.debug(f"Mapped URL {item.url} to page ID {page_id}")

                # Track directory ownership: map the directory to its Confluence parent ID
                path_parts = item.file.src_path.split("/")
                if len(path_parts) > 1:
                    directory = "/".join(path_parts[:-1])
                    if directory not in self.dir_to_id:
                        self.dir_to_id[directory] = parent_id
                        logger.debug(f"Mapped directory {directory} to parent ID {parent_id}")

            if isinstance(item, Section) and item.children:
                logger.debug(f"Processing children of {page_title}")
                self.create_pages_in_space(item.children, page_id, md_to_page)
        return md_to_page

    def ensure_page_exists(self, title: str, parent_id: int, is_section: bool = False) -> int | None:
        """Ensure a page exists."""
        existing_page = self.confluence_client.get_page_by_title(self.space_key, title)
        if existing_page:
            logger.debug(f"Page already exists: {title}")
            return existing_page["id"]

        body = '<ac:structured-macro ac:name="children" />' if is_section else ""
        logger.info(f"Creating {'section ' if is_section else ''}page: {title}")
        try:
            new_page = self.confluence_client.create_page(
                space=self.space_key, title=title, body=body, parent_id=parent_id
            )
            return new_page["id"]
        except Exception as e:
            logger.error(f"Error creating page {title}: {str(e)}")
            return None

    def _get_title_from_file(self, file) -> str:
        """Helper to extract title from a file's content or filename."""
        title = None
        # Try to find the title from the file content (first H1)
        try:
            if os.path.exists(file.abs_src_path):
                with open(file.abs_src_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("# "):
                            title = line[2:].strip()
                            break
        except (AttributeError, OSError):
            pass

        if not title:
            # Fallback to filename
            path_parts = file.src_path.split("/")
            filename = path_parts[-1]
            if filename.endswith(".md"):
                filename = filename[:-3]
            title = filename.replace("_", " ").replace("-", " ").capitalize()

        return title

    def create_orphan_pages(self, files, parent_id, md_to_page: MD_to_Page):
        """Create orphan pages."""
        for file in files.documentation_pages():
            if file.src_path in md_to_page:
                continue

            # Handle directory structure
            path_parts = file.src_path.split("/")
            current_parent_id = parent_id

            # Find the deepest already-mapped ancestor directory to "graft" onto
            start_index = 0
            for i in range(len(path_parts) - 1, 0, -1):
                ancestor_dir = "/".join(path_parts[:i])
                if ancestor_dir in self.dir_to_id:
                    current_parent_id = self.dir_to_id[ancestor_dir]
                    start_index = i
                    logger.debug(
                        f"Found existing ancestor for orphan {file.src_path}: {ancestor_dir} -> {current_parent_id}"
                    )
                    break

            # Create intermediate pages for missing directories
            current_path = "/".join(path_parts[:start_index]) if start_index > 0 else ""
            for i in range(start_index, len(path_parts) - 1):
                part = path_parts[i]
                current_path = f"{current_path}/{part}" if current_path else part

                dir_title = f"{self.prefix}{part}{self.suffix}"
                page_id = self.ensure_page_exists(dir_title, current_parent_id, is_section=True)
                if not page_id:
                    break
                self.active_page_ids.add(str(page_id))
                self.dir_to_id[current_path] = page_id  # Update mapping for siblings
                current_parent_id = page_id
            else:
                # Create the actual page
                # Try to get title from Page object if it exists
                title = getattr(file, "page", None) and getattr(file.page, "title", None)

                if not title:
                    title = self._get_title_from_file(file)

                page_title = f"{self.prefix}{title}{self.suffix}"
                page_id = self.ensure_page_exists(page_title, current_parent_id)
                if page_id:
                    self.active_page_ids.add(str(page_id))
                    md_to_page[file.src_path] = ConfluencePage(id=page_id, title=page_title)
                    logger.debug(f"Mapped orphan {file.src_path} to page ID {page_id}")

        return md_to_page

    def prune_orphans(self, parent_id: int | str):
        """Recursively prune orphaned pages under parent_id."""
        children = self.confluence_client.get_child_pages(parent_id)
        if not children:
            return

        for child in children:
            child_id = str(child["id"])
            child_title = child["title"]

            if child_id not in self.active_page_ids:
                logger.info(f"Pruning orphaned Confluence page: {child_title} (ID: {child_id})")
                try:
                    self.confluence_client.remove_page(child_id)
                except Exception as e:
                    logger.error(f"Error pruning page {child_title}: {str(e)}")
                continue  # Skip recursing into deleted page

            # Recurse to check children of this page
            self.prune_orphans(child_id)


def create_pages(
    confluence,
    items,
    prefix,
    suffix,
    space_key,
    parent_id,
    md_to_page: MD_to_Page,
    files=None,
):
    """Create pages and return mapping and set of active IDs."""
    confluence_client = ConfluenceClient(confluence)
    page_creator = PageCreator(confluence_client, prefix, suffix, space_key)
    md_to_page = page_creator.create_pages_in_space(items, parent_id, md_to_page)
    if files:
        md_to_page = page_creator.create_orphan_pages(files, parent_id, md_to_page)
    return md_to_page, page_creator
