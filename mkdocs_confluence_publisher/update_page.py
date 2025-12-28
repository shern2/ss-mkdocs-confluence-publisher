import logging
import os
import re
from typing import cast

import mistune
from mistune.directives import Admonition, RSTDirective, TableOfContents
from mistune.plugins.table import table
from mistune.plugins.task_lists import task_lists

from .renderers import ConfluenceRenderer
from .types import ConfluencePage, MD_to_Page

logger = logging.getLogger("mkdocs.plugins.confluence_publisher.store_page")
# logger.setLevel(logging.DEBUG)

# Add support for MkDocs specific admonitions and expand directive
Admonition.SUPPORTED_NAMES.update(["expand", "info", "todo", "success", "check", "done"])

confluence_mistune = mistune.create_markdown(
    renderer=ConfluenceRenderer(escape=False),
    plugins=[RSTDirective([Admonition(), TableOfContents()]), task_lists, table],  # pyrefly: ignore[bad-argument-type]
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


def slugify(text: str) -> str:
    """
    Generate a meaningful ID from the text to support case-sensitive internal anchors.
    This matches the logic in ConfluenceRenderer.heading.
    """
    # Strip HTML tags
    clean_text = re.sub(r"<[^>]*>", "", text)
    # Replace whitespace with hyphens
    slug = re.sub(r"\s+", "-", clean_text)
    # Remove non-alphanumeric/hyphen/underscore
    slug = re.sub(r"[^\w-]", "", slug)
    # Strip leading/trailing hyphens
    return slug.strip("-")


def validate_internal_links(markdown: str, page_path: str):
    """
    Validate that same-page internal links match the case of the heading IDs.
    """
    # Extract all headings and their slugified IDs
    # Heading regex: lines starting with # (ATX style)
    heading_pattern = r"^(#{1,6})\s+(.*)$"
    heading_ids = set()
    used_ids = set()

    for match in re.finditer(heading_pattern, markdown, re.MULTILINE):
        heading_text = match.group(2).strip()
        slug = slugify(heading_text)
        if slug:
            base_slug = slug
            counter = 1
            while slug in used_ids:
                slug = f"{base_slug}-{counter}"
                counter += 1
            used_ids.add(slug)
            heading_ids.add(slug)

    # Find all same-page links: [text](#anchor)
    # link_pattern matches [any text](#anchor)
    link_pattern = r"\[[^\]]*\]\(#(.*?)\)"
    for match in re.finditer(link_pattern, markdown):
        anchor = match.group(1)
        if not anchor:
            continue

        # Check for case-sensitive match
        if anchor in heading_ids:
            continue

        # Check for case-insensitive match to find casing errors
        lowercase_heading_ids = {h.lower(): h for h in heading_ids}
        if anchor.lower() in lowercase_heading_ids:
            correct_case = lowercase_heading_ids[anchor.lower()]
            raise ValueError(
                f"Internal link error in '{page_path}': "
                f"Link anchor '#{anchor}' does not match the case of heading ID '#{correct_case}'. "
                f"Confluence internal links are case-sensitive."
            )


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

    # Fix links to relative markdown pages and internal anchors
    def replace_link(match):
        href = match.group(2)
        link_text = match.group(4)

        # Split href into path and anchor
        parts = href.split("#", 1)
        path = parts[0]
        anchor = parts[1] if len(parts) > 1 else None

        if path.endswith(".md") and path in md_to_page:
            page = md_to_page[path]
            anchor_attr = f' ac:anchor="{anchor}"' if anchor else ""
            logger.debug(
                f"Replaced link to {href} with Confluence page {page.title}{' (anchor: ' + anchor + ')' if anchor else ''}"
            )
            return (
                f'<ac:link{anchor_attr}>'
                f'<ri:page ri:content-title="{page.title}" />'
                f"<ac:plain-text-link-body><![CDATA[{link_text}]]></ac:plain-text-link-body>"
                f"</ac:link>"
            )
        elif not path and anchor:
            logger.debug(f"Replaced internal anchor link: {anchor}")
            return (
                f'<ac:link ac:anchor="{anchor}">'
                f"<ac:plain-text-link-body><![CDATA[{link_text}]]></ac:plain-text-link-body>"
                f"</ac:link>"
            )

        return match.group(0)

    confluence_content = re.sub(
        r'<a (.*?)href="(.*?)"(.*?)>(.*?)</a>',
        replace_link,
        confluence_content,
        flags=re.DOTALL,
    )
    logger.debug("Fixed links to relative markdown pages and anchors")

    # Replace incompatible code macros
    confluence_content = replace_incompatible_macros(confluence_content)

    return confluence_content, attachments


def update_page(markdown: str, page, confluence, md_to_page: MD_to_Page) -> list[str]:
    """
    Update a page in Confluence with markdown content.
    """
    logger.debug(f"Starting to process page for Confluence: {page.file.src_path}")

    # Validate internal links casing before processing
    validate_internal_links(markdown, page.file.src_path)

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
