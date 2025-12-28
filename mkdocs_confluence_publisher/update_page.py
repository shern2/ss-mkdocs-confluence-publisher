import logging
import os
import re
from typing import cast

import mistune
from mistune.directives import Admonition, RSTDirective, TableOfContents

from .renderers import ConfluenceRenderer
from .types import ConfluencePage, MD_to_Page

logger = logging.getLogger("mkdocs.plugins.confluence_publisher.store_page")
# logger.setLevel(logging.DEBUG)

# Add support for MkDocs specific admonitions and expand directive
Admonition.SUPPORTED_NAMES.update(["expand", "info", "todo", "success", "check", "done"])

confluence_mistune = mistune.create_markdown(
    renderer=ConfluenceRenderer(escape=False),
    plugins=[RSTDirective([Admonition(), TableOfContents()])],  # pyrefly: ignore[bad-argument-type]
)

# Define the replacements for incompatible code macros
MACRO_REPLACEMENTS = {
    "json": "yaml",
    # Add more replacements here as needed
    # 'incompatible_language': 'compatible_language',
}


def replace_incompatible_macros(content: str) -> str:
    """
    Replace incompatible code macros in the content.
    """
    for incompatible, compatible in MACRO_REPLACEMENTS.items():
        pattern = f'<ac:parameter ac:name="language">{incompatible}</ac:parameter>'
        replacement = f'<ac:parameter ac:name="language">{compatible}</ac:parameter>'
        content = content.replace(pattern, replacement)

    logger.debug("Replaced incompatible code macros")
    return content


def generate_confluence_content(markdown: str, md_to_page: MD_to_Page, page) -> tuple[str, list[str]]:
    """
    Generate Confluence storage format content from markdown.
    """
    # Scan markdown for image tags and collect filenames
    attachments = []
    image_pattern = r"!\[.*?\]\((.*?)\)"
    for match in re.finditer(image_pattern, markdown):
        image_path = match.group(1)
        logger.debug(f"Found image reference: {image_path}")
        if not image_path.startswith(("http://", "https://")):
            full_path = os.path.join(os.path.dirname(page.file.abs_src_path), image_path)
            if os.path.exists(full_path):
                attachments.append(full_path)
                logger.debug(f"Added image to attachments list: {full_path}")
            else:
                logger.warning(f"Referenced image not found: {full_path}")

    logger.debug(f"Found {len(attachments)} image references")

    # Support ??? (expand) by converting it to .. expand:: before parsing
    markdown = re.sub(r"^\?\?\?\+?\s*([\w-]+)?(?:\s+\"(.*)\")?", r".. \1:: \2", markdown, flags=re.MULTILINE)

    # Support !!! note by converting it to .. note:: before parsing
    markdown = re.sub(r"^!!!\s*([\w-]+)(?:\s+\"(.*)\")?", r".. \1:: \2", markdown, flags=re.MULTILINE)

    # Support [TOC] by converting it to .. toc:: before parsing
    # This maps mkdocs/markdown.extensions.toc syntax to mistune's TableOfContents directive
    markdown = re.sub(r"^\[TOC\]", ".. toc::", markdown, flags=re.MULTILINE | re.IGNORECASE)

    # Render markdown to Confluence storage format
    confluence_content = cast(str, confluence_mistune(markdown))
    logger.debug("Converted markdown to Confluence storage format")

    # Fix links to relative markdown pages
    def replace_link(match):
        href = match.group(2)
        if href.endswith(".md") and href in md_to_page:
            page = md_to_page[href]
            logger.debug(f"Replaced link to {href} with Confluence page {page}")
            return f'<ac:link><ri:page ri:content-title="{page.title}" /></ac:link>'
        return match.group(0)

    confluence_content = re.sub(r'<a (.*?)href="(.*?)"(.*?)>(.*?)</a>', replace_link, confluence_content)
    logger.debug("Fixed links to relative markdown pages")

    # Replace incompatible code macros
    confluence_content = replace_incompatible_macros(confluence_content)

    return confluence_content, attachments


def update_page(markdown: str, page, confluence, md_to_page: MD_to_Page) -> list[str]:
    """
    Update a page in Confluence with markdown content.
    """
    logger.debug(f"Starting to process page for Confluence: {page.file.src_path}")

    confluence_content, attachments = generate_confluence_content(markdown, md_to_page, page)

    # Update the page content in Confluence
    confluence_page: ConfluencePage | None = md_to_page.get(page.file.src_path)
    if confluence_page:
        logger.debug(f"Updating Confluence page: {confluence_page.title}")
        confluence.update_page(
            page_id=confluence_page.id,
            body=confluence_content,
            title=confluence_page.title,
        )
        logger.info(f"Updated Confluence page: {confluence_page.title}")
    else:
        logger.warning(f"No Confluence page ID found for {page.file.src_path}")

    logger.debug(f"Finished processing page for Confluence: {page.file.src_path}")
    return attachments
