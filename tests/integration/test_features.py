import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mkdocs.commands.build import build
from mkdocs.config import load_config


@pytest.fixture
def temp_docs_dir():
    """Create a temporary directory for mkdocs project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_integration_full_features(temp_docs_dir, mocker):
    """Test full build flow with various markdown features and orphans."""
    # Setup temporary project structure
    docs_dir = temp_docs_dir / "docs"
    docs_dir.mkdir()

    # Create main index page with various features
    index_md = """# Test Page

!!! note "This is a note"
    With some content

??? expand "Click to see more"
    Hidden content

!!! success "Success"
    It worked!

!!! error "Error"
    Something failed.

[TOC]

![Sample Image](images/sample.png)

[Link to Orphan](sub/orphan.md)

- [ ] task 1
- [x] task 2

| Feature | Support |
| :--- | :--- |
| Admonitions | Yes |

---
"""
    (docs_dir / "index.md").write_text(index_md)

    # Create images directory and a dummy image
    images_dir = docs_dir / "images"
    images_dir.mkdir()
    (images_dir / "sample.png").write_text("dummy image content")

    # Create an orphan page in a subdirectory
    sub_dir = docs_dir / "sub"
    sub_dir.mkdir()
    (sub_dir / "orphan.md").write_text("# Orphan Page")

    # mkdocs.yml configuration
    mkdocs_yml = """
site_name: Integration Test
nav:
  - Home: index.md
plugins:
  - confluence-publisher:
      confluence_prefix: "TEST - "
      space_key: "TESTSPACE"
      parent_page_id: 123
"""
    (temp_docs_dir / "mkdocs.yml").write_text(mkdocs_yml)

    # Mock Confluence client
    mock_confluence = MagicMock()
    # Mock behavior for get_page_by_title (simulate pages don't exist yet)
    mock_confluence.get_page_by_title.return_value = None

    # Mock behavior for create_page
    # Sequence:
    # 1. Home (index.md) - from nav
    # 2. sub/ directory - intermediate for orphan
    # 3. Orphan Page (sub/orphan.md) - orphan (title from H1)
    mock_confluence.create_page.side_effect = [
        {"id": "1001", "title": "TEST - Home"},  # Home (index.md)
        {"id": "1002", "title": "TEST - sub"},  # sub/ directory
        {"id": "1003", "title": "TEST - Orphan Page"},  # Orphan Page (sub/orphan.md)
    ]

    # Mock behavior for attachments
    mock_confluence.get_attachments_from_content.return_value = {"results": []}

    # Patch the Confluence class in the plugin
    with patch(
        "mkdocs_confluence_publisher.plugin.Confluence", return_value=mock_confluence
    ):
        # Mock environment variables required by the plugin
        with patch.dict(
            os.environ,
            {
                "CONFLUENCE_URL": "http://mock",
                "CONFLUENCE_USERNAME": "testuser",
                "CONFLUENCE_API_TOKEN": "testtoken",
            },
        ):
            # Change to temp directory to run mkdocs
            original_cwd = os.getcwd()
            os.chdir(temp_docs_dir)
            try:
                cfg = load_config()
                build(cfg)
            finally:
                os.chdir(original_cwd)

    # Verifications

    # 1. Verify page creation calls
    assert mock_confluence.create_page.call_count >= 3

    # Check if index page was created under parent 123
    mock_confluence.create_page.assert_any_call(
        space="TESTSPACE", title="TEST - Home", body="", parent_id=123
    )

    # Check if orphan sub-directory page was created
    mock_confluence.create_page.assert_any_call(
        space="TESTSPACE",
        title="TEST - sub",
        body='<ac:structured-macro ac:name="children" />',
        parent_id=123,
    )

    # Check if orphan page was created under sub-directory
    mock_confluence.create_page.assert_any_call(
        space="TESTSPACE", title="TEST - Orphan Page", body="", parent_id="1002"
    )

    # 2. Verify update_page calls (where content is actually pushed)
    # Find the call for the index page
    update_calls = [
        c
        for c in mock_confluence.update_page.call_args_list
        if c.kwargs.get("page_id") == "1001"
    ]
    assert len(update_calls) == 1
    index_content = update_calls[0].kwargs.get("body")

    # Verify Enhanced Markdown Support
    # - Admonition
    assert '<ac:structured-macro ac:name="note">' in index_content
    assert '<ac:parameter ac:name="title">This is a note</ac:parameter>' in index_content

    # - Expand
    assert '<ac:structured-macro ac:name="expand">' in index_content
    assert (
        '<ac:parameter ac:name="title">Click to see more</ac:parameter>'
        in index_content
    )

    # - Success (mapped to tip)
    assert '<ac:structured-macro ac:name="tip">' in index_content
    assert '<ac:parameter ac:name="title">Success</ac:parameter>' in index_content

    # - Error (mapped to warning)
    assert '<ac:structured-macro ac:name="warning">' in index_content
    assert '<ac:parameter ac:name="title">Error</ac:parameter>' in index_content

    # - TOC
    assert '<ac:structured-macro ac:name="toc">' in index_content

    # - Cross-link to orphan
    assert (
        '<ac:link><ri:page ri:content-title="TEST - Orphan Page" /><ac:plain-text-link-body><![CDATA[Link to Orphan]]></ac:plain-text-link-body></ac:link>'
        in index_content
    )

    # - Task List
    assert "<ac:task-list>" in index_content
    assert "<ac:task-status>incomplete</ac:task-status>" in index_content
    assert "<ac:task-body>task 1</ac:task-body>" in index_content
    assert "<ac:task-status>complete</ac:task-status>" in index_content
    assert "<ac:task-body>task 2</ac:task-body>" in index_content

    # - HR
    assert "<hr />" in index_content

    # - Table
    assert '<table data-table-width="760" data-layout="default"><tbody>' in index_content
    assert "<th><p><strong>Feature</strong></p></th>" in index_content
    assert "<td><p>Admonitions</p></td>" in index_content

    # 3. Verify Attachment Handling
    mock_confluence.attach_file.assert_called_once()
    assert "sample.png" in mock_confluence.attach_file.call_args[0][0]
    assert mock_confluence.attach_file.call_args[1]["page_id"] == "1001"


def test_integration_autogen_files(temp_docs_dir, mocker):
    """Test handling of files generated during the build."""
    docs_dir = temp_docs_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home")

    # mkdocs.yml configuration
    mkdocs_yml = """
site_name: Autogen Test
plugins:
  - confluence-publisher:
      space_key: "TESTSPACE"
      parent_page_id: 123
"""
    (temp_docs_dir / "mkdocs.yml").write_text(mkdocs_yml)

    mock_confluence = MagicMock()
    mock_confluence.get_page_by_title.return_value = None
    mock_confluence.create_page.return_value = {"id": "2001", "title": "Autogen"}
    mock_confluence.get_attachments_from_content.return_value = {"results": []}

    # Simulate a file being present on disk but NOT in the nav
    (docs_dir / "autogen.md").write_text("# Autogen\nContent")

    with patch(
        "mkdocs_confluence_publisher.plugin.Confluence", return_value=mock_confluence
    ):
        with patch.dict(
            os.environ,
            {
                "CONFLUENCE_URL": "http://mock",
                "CONFLUENCE_USERNAME": "testuser",
                "CONFLUENCE_API_TOKEN": "testtoken",
            },
        ):
            original_cwd = os.getcwd()
            os.chdir(temp_docs_dir)
            try:
                cfg = load_config()
                # mkdocs will automatically include autogen.md in nav if not specified
                build(cfg)
            finally:
                os.chdir(original_cwd)

    # Verify that autogen.md was processed (either via nav or as orphan)
    # The title should be "Autogen" (from H1)
    mock_confluence.create_page.assert_any_call(
        space="TESTSPACE", title="Autogen", body=mocker.ANY, parent_id=123
    )
