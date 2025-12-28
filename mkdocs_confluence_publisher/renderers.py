import logging
import re
import urllib.parse as urlparse
from pathlib import Path
from typing import Any, Optional

from mistune.renderers.html import HTMLRenderer

logger = logging.getLogger("mkdocs.plugins.confluence_publisher.renderers")


class ConfluenceTag:
    """A class representing a Confluence XML tag."""

    def __init__(self, name, text="", attrib=None, namespace="ac", cdata=False):
        self.name = name
        self.text = text
        self.namespace = namespace
        self.attrib = attrib or {}
        self.children = []
        self.cdata = cdata

    def render(self):
        """Render the tag and its children to an XML string."""
        namespaced_name = self.add_namespace(self.name, namespace=self.namespace)
        namespaced_attribs = {
            self.add_namespace(attribute_name, namespace=self.namespace): attribute_value
            for attribute_name, attribute_value in self.attrib.items()
        }

        attrib_str = " ".join([f'{name}="{value}"' for name, value in sorted(namespaced_attribs.items())])
        if attrib_str:
            attrib_str = " " + attrib_str

        children_rendered = "".join([child.render() for child in self.children])
        content = f"<![CDATA[{self.text}]]>" if self.cdata else self.text

        return f"<{namespaced_name}{attrib_str}>{children_rendered}{content}</{namespaced_name}>\n"

    @staticmethod
    def add_namespace(tag, namespace):
        """Add a namespace prefix to a tag name."""
        return f"{namespace}:{tag}"

    def append(self, child):
        """Append a child tag to this tag."""
        self.children.append(child)


class ConfluenceRenderer(HTMLRenderer):
    """A mistune renderer for Confluence storage format."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.attachments = []
        self.title = None
        self.used_ids = set()

    def reinit(self):
        """Reset the renderer state."""
        self.attachments = []
        self.title = None
        self.used_ids = set()

    def heading(self, text: str, level: int, **attrs: Any) -> str:
        """Render a heading tag and track the title."""
        if self.title is None and level == 1:
            self.title = text

        # Generate a meaningful ID from the text to support case-sensitive internal anchors
        # This matches common Markdown slugification but preserves case as requested
        if text:
            # Strip HTML tags
            clean_text = re.sub(r"<[^>]*>", "", text)
            # Replace whitespace with hyphens
            slug = re.sub(r"\s+", "-", clean_text)
            # Remove non-alphanumeric/hyphen/underscore
            slug = re.sub(r"[^\w-]", "", slug)
            # Strip leading/trailing hyphens
            slug = slug.strip("-")

            if slug:
                base_slug = slug
                counter = 1
                while slug in self.used_ids:
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                self.used_ids.add(slug)
                attrs["id"] = slug

        return super().heading(text, level, **attrs)

    def structured_macro(self, name):
        """Create a Confluence structured-macro tag."""
        return ConfluenceTag("structured-macro", attrib={"name": name})

    def parameter(self, name, value):
        """Create a Confluence parameter tag."""
        parameter_tag = ConfluenceTag("parameter", attrib={"name": name})
        parameter_tag.text = value
        return parameter_tag

    def plain_text_body(self, text):
        """Create a Confluence plain-text-body tag."""
        body_tag = ConfluenceTag("plain-text-body", cdata=True)
        body_tag.text = text
        return body_tag

    def rich_text_body(self, text):
        """Create a Confluence rich-text-body tag."""
        body_tag = ConfluenceTag("rich-text-body")
        body_tag.text = text
        return body_tag

    def block_code(self, code: str, info: str | None = None) -> str:
        """Render a fenced code block as a Confluence code macro."""
        root_element = self.structured_macro("code")
        if info:
            lang = info.split(None, 1)[0]
            lang_parameter = self.parameter(name="language", value=lang)
            root_element.append(lang_parameter)

        root_element.append(self.parameter(name="linenumbers", value="true"))
        root_element.append(self.plain_text_body(code))
        return root_element.render()

    def admonition(self, text: str, name: str, title: str | None = None) -> str:
        """Render a Markdown admonition as a Confluence macro."""
        if title is None:
            title_match = re.search(r'<p class="admonition-title">(.*?)</p>', text)
            if title_match:
                title = title_match.group(1)
                text = text.replace(title_match.group(0), "", 1)

        macro_name = name.lower()
        if macro_name in ["warning", "caution", "danger", "error", "attention"]:
            macro_name = "warning"
        elif macro_name in ["tip", "hint", "success", "check", "done"]:
            macro_name = "tip"
        elif macro_name in ["note", "important"]:
            macro_name = "note"
        elif macro_name in ["info", "todo"]:
            macro_name = "info"

        allowed_macros = {"tip", "info", "note", "warning", "expand"}
        if macro_name not in allowed_macros:
            macro_name = "info"

        root_element = self.structured_macro(macro_name)
        if title:
            root_element.append(self.parameter("title", title))

        root_element.append(self.rich_text_body(text))
        return root_element.render()

    def toc(self, *args: Any, **kwargs: Any) -> str:
        """Render a Table of Contents as a Confluence macro."""
        return self.structured_macro("toc").render()

    def image(self, text: str, url: str, title: str | None = None) -> str:
        """Render an image tag as a Confluence image macro."""
        attributes = {"alt": text}
        if title:
            attributes["title"] = title

        root_element = ConfluenceTag(name="image", attrib=attributes)
        parsed_source = urlparse.urlparse(url)

        if not parsed_source.netloc and not url.startswith("data:"):
            # Local file, requires upload
            basename = Path(url).name
            url_tag = ConfluenceTag("attachment", attrib={"filename": basename}, namespace="ri")
            if url not in self.attachments:
                self.attachments.append(url)
        else:
            url_tag = ConfluenceTag("url", attrib={"value": url}, namespace="ri")

        root_element.append(url_tag)
        return root_element.render()

    def list(self, text: str, ordered: bool, **attrs: Any) -> str:
        """Render a list as a Confluence task-list if it contains tasks."""
        if "<ac:task" in text:
            return f"<ac:task-list>\n{text}</ac:task-list>\n"
        return super().list(text, ordered, **attrs)

    def task_list_item(self, text: str, checked: bool, **attrs: Any) -> str:
        """Render a task list item as a Confluence task."""
        status = "complete" if checked else "incomplete"
        text = text.strip()
        return f"<ac:task>\n<ac:task-status>{status}</ac:task-status>\n<ac:task-body>{text}</ac:task-body>\n</ac:task>\n"

    def thematic_break(self) -> str:
        """Render a horizontal rule as a Confluence hr tag."""
        return "<hr />\n"

    def table(self, content: str) -> str:
        """Render a table as a Confluence table."""
        return f'<table data-table-width="760" data-layout="default"><tbody>\n{content}</tbody></table>\n'

    def table_head(self, content: str) -> str:
        """Render a table head."""
        return f"<tr>\n{content}</tr>\n"

    def table_body(self, content: str) -> str:
        """Render a table body."""
        return content

    def table_row(self, content: str) -> str:
        """Render a table row."""
        return f"<tr>\n{content}</tr>\n"

    def table_cell(self, content: str, align: str | None = None, head: bool = False, **attrs: Any) -> str:
        """Render a table cell."""
        if head:
            return f"<th><p><strong>{content}</strong></p></th>\n"
        return f"<td><p>{content}</p></td>\n"
