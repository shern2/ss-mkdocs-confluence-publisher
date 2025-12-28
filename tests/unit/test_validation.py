import pytest

from mkdocs_confluence_publisher.update_page import validate_internal_links


def test_valid_case_link():
    """
    Test that a valid case link does not raise an error.
    """
    markdown = """
# Admonition Support

[Link to Admonition Support](#Admonition-Support)
"""
    # Should not raise any error
    validate_internal_links(markdown, "index.md")


def test_invalid_case_link():
    """
    Test that an invalid case link raises an error.
    """
    markdown = """
# Admonition Support

[Link to Admonition Support](#admonition-support)
"""
    with pytest.raises(ValueError) as excinfo:
        validate_internal_links(markdown, "index.md")

    assert "Link anchor '#admonition-support' does not match the case of heading ID '#Admonition-Support'" in str(
        excinfo.value
    )


def test_multiple_headings_deduplication():
    """
    Test that multiple headings with the same name are deduplicated.
    """
    markdown = """
# Duplicate
# Duplicate

[First](#Duplicate)
[Second](#Duplicate-1)
"""
    # Should not raise any error
    validate_internal_links(markdown, "index.md")


def test_invalid_case_link_deduplicated():
    """
    Test that an invalid case link raises an error for a deduplicated heading.
    """
    markdown = """
# Duplicate
# Duplicate

[Second](#duplicate-1)
"""
    with pytest.raises(ValueError) as excinfo:
        validate_internal_links(markdown, "index.md")

    assert "Link anchor '#duplicate-1' does not match the case of heading ID '#Duplicate-1'" in str(excinfo.value)


def test_no_match_no_error():
    """
    Test that links that don't match any heading (even case-insensitively) should not raise errors.
    """
    # Links that don't match any heading (even case-insensitively) should not raise errors
    # from THIS validator (other validators might catch them)
    markdown = """
# Header

[Non-existent](#something-else)
"""
    validate_internal_links(markdown, "index.md")
