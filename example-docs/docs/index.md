# Home - MkDocs Confluence Publisher

Welcome to the feature showcase for the **MkDocs Confluence Publisher** plugin. This page demonstrates the various Markdown features supported during the publishing process.

[TOC]

## Admonition Support

We support mapping MkDocs admonitions to native Confluence macros.

!!! info "Information"
    This is an `info` macro in Confluence. Use it for general information.

!!! note "Note"
    This is a `note` macro in Confluence. Use it for important notes.

!!! success "Success"
    This is mapped to a `tip` macro in Confluence. Use it for positive results.

!!! tip "Tip"
    This is a `tip` macro in Confluence. Use it for helpful hints.

!!! warning "Warning"
    This is a `warning` macro in Confluence. Use it for potential issues.

!!! error "Error"
    This is also mapped to a `warning` macro in Confluence. Use it for critical errors.

## Expandable Sections

Support for `pymdownx.details` syntax is provided via Confluence's `expand` macro.

??? expand "Click to see more technical details"
    This content is hidden by default in Confluence and requires a user to click to expand it.
    - Feature A
    - Feature B
    - Feature C

## Navigation and Links

- **Internal Link**: [Go to Admonition Support](#Admonition-Support)
- **Nested Link**: [Go to Sub Page 1](sub-pages/sub-page1.md)
- **Orphan Link**: [Check out the Orphan Page](orphans/orphan-page.md) (This page is not in `mkdocs.yml`)

## Task Lists

Native Confluence task lists are supported via Markdown checkboxes.

- [ ] Task 1 (incomplete)
- [x] Task 2 (complete)

## Basic Formatting

Text can be **bold**, *italic*, or ~~strikethrough~~. You can also use `inline code`.

## Lists

### Unordered List
- Item 1
- Item 2
    - Sub-item 2.1
    - Sub-item 2.2
- Item 3

### Ordered List
1. First item
2. Second item
3. Third item

## Tables

| Feature | Support | Note |
| ------- | ------- | ---- |
| Admonitions | Yes | Mapped to native macros |
| Tables | Yes | Standard Markdown tables |
| Code Blocks | Yes | With syntax highlighting |

## Code Blocks

```python
def hello_confluence():
    print("Hello from MkDocs Confluence Publisher!")

if __name__ == "__main__":
    hello_confluence()
```

---

## Attachments

Local images are automatically uploaded as attachments to the corresponding Confluence page.

![Sample Image](images/sample-image.png)
