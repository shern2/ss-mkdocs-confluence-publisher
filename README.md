# MkDocs Confluence Publisher Plugin

> [!CAUTION]
> This is a **hard fork** of the original [mkdocs-confluence-publisher](https://github.com/johnny/mkdocs-confluence-publisher).
> This version is **unmaintained** and is published to PyPI as `ss-mkdocs-confluence-publisher`.

This version adds the following features:
- **Orphan Page Support**: Automatically creates pages in Confluence for Markdown files not listed in `mkdocs.yml`, preserving directory hierarchy.
- **Page Pruning**: Automatically deletes Confluence pages that no longer exist in your MkDocs source (optional).
- **Robust Title Extraction**: Automatically extracts page titles from the first H1 tag in Markdown files or falls back to capitalized filenames.
- **Native Task Lists**: Maps Markdown checkboxes (`- [ ]`, `- [x]`) to native interactive Confluence task list macros.
- **Enhanced Markdown Support**:
    - **Admonitions**: Full support for standard Markdown admonitions (`!!! note`, etc.) mapped to corresponding Confluence macros (`info`, `tip`, `note`, `warning`).
    - **Expandable Sections**: Support for `pymdownx.details` (`??? expand`) syntax using Confluence's expand macro.
    - **Table of Contents**: Support for `[TOC]` markers mapped to Confluence's native TOC macro.
    - **Horizontal Rules**: Maps Markdown `---` to native Confluence `<hr />` elements.
- **Improved Attachment Handling**: Better detection and uploading of local images.
- **Internal Link Validation**: Automatically validates that same-page internal links (anchors) match the casing of the target headings. This prevents issues with Confluence's case-sensitive anchor system.
- **Modern Build System**: Built with `hatchling` and optimized for use with `uv`.

This MkDocs plugin automatically publishes your documentation to Confluence. It creates a hierarchical structure in Confluence that mirrors your MkDocs site structure, updates page content, and handles attachments.

## Features

- Automatically creates and updates pages in Confluence
- Maintains the hierarchy of your MkDocs site in Confluence
- Handles attachments referenced in your markdown files
- Configurable page prefix for easy identification in Confluence

## Installation

Install the plugin using uv:
```bash
uv pip install ss-mkdocs-confluence-publisher
```

## Configuration

Add the following to your `mkdocs.yml`:

```yaml
plugins:
  - confluence-publisher:
      confluence_prefix: "MkDocs - "  # Optional: Prefix for page titles in Confluence
      confluence_suffix: " - MkDocs"  # Optional: Suffix for page titles in Confluence
      space_key: "YOUR_SPACE_KEY"     # Required: Confluence space key
      parent_page_id: 123456          # Required: ID of the parent page in Confluence
      prune_orphans: false            # Optional: If true, deletes Confluence pages that are no longer in MkDocs
```

## Environment Variables

The plugin requires the following environment variables to be set:

- `CONFLUENCE_URL`: The base URL of your Confluence instance
- `CONFLUENCE_USERNAME`: Your Confluence username
- `CONFLUENCE_API_TOKEN`: Your Confluence API token

You can set these in your environment or use a `.env` file.

## Usage

Once configured, the plugin will automatically publish your documentation to Confluence when you build your MkDocs site:

```bash
mkdocs build
```

## How It Works

1. **Initialization**: The plugin connects to Confluence using the provided credentials.
2. **Page Creation**: It creates a structure in Confluence mirroring your MkDocs navigation.
3. **Content Update**: As it processes each page, it updates the content in Confluence.
4. **Attachment Handling**: Any attachments referenced in your markdown are uploaded to the corresponding Confluence page.

## Logging

The plugin uses Python's logging module. You can configure logging in your `mkdocs.yml`:

```yaml
logging:
  level: INFO
```

Set to `DEBUG` for more detailed logging information.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache-2.0 license.
