import logging

from mkdocs.structure.nav import Page, Section

from .types import ConfluencePage, MD_to_Page

logger = logging.getLogger("mkdocs.plugins.confluence_publisher.create_pages")

class ConfluenceClient:
    def __init__(self, confluence):
        self._confluence = confluence

    def get_page_by_title(self, space_key: str, title: str):
        return self._confluence.get_page_by_title(space_key, title)

    def create_page(self, space: str, title: str, body: str, parent_id: int):
        return self._confluence.create_page(
            space=space,
            title=title,
            body=body,
            parent_id=parent_id
        )

class PageCreator:
    def __init__(self, confluence_client: ConfluenceClient, prefix: str, suffix: str, space_key: str):
        self.confluence_client = confluence_client
        self.prefix = prefix
        self.suffix = suffix
        self.space_key = space_key

    def create_pages_in_space(self, items, parent_id, md_to_page: MD_to_Page):
        for item in items:
            page_title = f"{self.prefix}{item.title}{self.suffix}"
            logger.debug(f"Processing item: {page_title}")

            page_id = self.ensure_page_exists(page_title, parent_id, is_section=isinstance(item, Section))
            if not page_id:
                continue

            if isinstance(item, Page):
                md_to_page[item.file.src_path] = ConfluencePage(id=page_id, title=page_title)
                logger.debug(f"Mapped URL {item.url} to page ID {page_id}")

            if isinstance(item, Section) and item.children:
                logger.debug(f"Processing children of {page_title}")
                self.create_pages_in_space(item.children, page_id, md_to_page)
        return md_to_page

    def ensure_page_exists(self, title: str, parent_id: int, is_section: bool = False) -> int | None:
        existing_page = self.confluence_client.get_page_by_title(self.space_key, title)
        if existing_page:
            logger.debug(f"Page already exists: {title}")
            return existing_page["id"]

        body = '<ac:structured-macro ac:name="children" />' if is_section else ""
        logger.info(f"Creating {'section ' if is_section else ''}page: {title}")
        try:
            new_page = self.confluence_client.create_page(
                space=self.space_key,
                title=title,
                body=body,
                parent_id=parent_id
            )
            return new_page["id"]
        except Exception as e:
            logger.error(f"Error creating page {title}: {str(e)}")
            return None

    def create_orphan_pages(self, files, parent_id, md_to_page: MD_to_Page):
        for file in files.documentation_pages():
            if file.src_path in md_to_page:
                continue

            # Handle directory structure
            path_parts = file.src_path.split("/")
            current_parent_id = parent_id

            # Create intermediate pages for directories
            for part in path_parts[:-1]:
                dir_title = f"{self.prefix}{part}{self.suffix}"
                page_id = self.ensure_page_exists(dir_title, current_parent_id, is_section=True)
                if not page_id:
                    break
                current_parent_id = page_id
            else:
                # Create the actual page
                # Try to get title from Page object if it exists
                title = getattr(file, "page", None) and getattr(file.page, "title", None)
                if not title:
                    title = path_parts[-1].replace(".md", "").replace("_", " ").capitalize()

                page_title = f"{self.prefix}{title}{self.suffix}"
                page_id = self.ensure_page_exists(page_title, current_parent_id)
                if page_id:
                    md_to_page[file.src_path] = ConfluencePage(id=page_id, title=page_title)
                    logger.debug(f"Mapped orphan {file.src_path} to page ID {page_id}")

        return md_to_page


def create_pages(confluence, items, prefix, suffix, space_key, parent_id, md_to_page: MD_to_Page, files=None):
    confluence_client = ConfluenceClient(confluence)
    page_creator = PageCreator(confluence_client, prefix, suffix, space_key)
    md_to_page = page_creator.create_pages_in_space(items, parent_id, md_to_page)
    if files:
        md_to_page = page_creator.create_orphan_pages(files, parent_id, md_to_page)
    return md_to_page
