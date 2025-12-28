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

def test_integration_pruning(temp_docs_dir, mocker):
    """Test that orphaned pages are pruned when prune_orphans is true."""
    docs_dir = temp_docs_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home")

    # mkdocs.yml configuration with pruning enabled
    mkdocs_yml = """
site_name: Pruning Test
plugins:
  - confluence-publisher:
      confluence_prefix: "TEST - "
      space_key: "TESTSPACE"
      parent_page_id: 123
      prune_orphans: true
"""
    (temp_docs_dir / "mkdocs.yml").write_text(mkdocs_yml)

    # Mock Confluence client
    mock_confluence = MagicMock()

    # Mock behavior for get_page_by_title (simulate index page exists)
    mock_confluence.get_page_by_title.return_value = {"id": "2001", "title": "TEST - Home"}

    # Mock child pages hierarchy
    # 123 (parent) -> 2001 (Home - active), 2002 (Old Page - orphan), 2003 (Not our prefix)
    # 2003 -> 2004 (Deep Orphan - orphan)
    mock_confluence.get_child_pages.side_effect = lambda pid: {
        "123": [
            {"id": "2001", "title": "TEST - Home"},
            {"id": "2002", "title": "TEST - Old Page"},
            {"id": "2003", "title": "Not our prefix"},
        ],
        "2001": [],
        "2003": [
            {"id": "2004", "title": "TEST - Deep Orphan"},
        ],
        "2004": []
    }.get(str(pid), [])

    mock_confluence.get_attachments_from_content.return_value = {"results": []}

    # Patch the Confluence class in the plugin
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
            # Change to temp directory to run mkdocs
            original_cwd = os.getcwd()
            os.chdir(temp_docs_dir)
            try:
                cfg = load_config()
                build(cfg)
            finally:
                os.chdir(original_cwd)

    # Verifications
    # 1. Verify pruning calls
    # Should remove 2002 and 2003
    assert mock_confluence.remove_page.call_count == 2
    mock_confluence.remove_page.assert_any_call("2002")
    mock_confluence.remove_page.assert_any_call("2003")

    # Verify that it didn't remove 2001 (active)
    removed_ids = [call[0][0] for call in mock_confluence.remove_page.call_args_list]
    assert "2001" not in removed_ids
    # 2004 won't be visited because 2003 was deleted
    assert "2004" not in removed_ids

def test_integration_no_pruning_by_default(temp_docs_dir, mocker):
    """Test that orphaned pages are NOT pruned by default."""
    docs_dir = temp_docs_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home")

    # mkdocs.yml configuration without prune_orphans
    mkdocs_yml = """
site_name: No Pruning Test
plugins:
  - confluence-publisher:
      confluence_prefix: "TEST - "
      space_key: "TESTSPACE"
      parent_page_id: 123
"""
    (temp_docs_dir / "mkdocs.yml").write_text(mkdocs_yml)

    # Mock Confluence client
    mock_confluence = MagicMock()
    mock_confluence.get_page_by_title.return_value = {"id": "2001", "title": "TEST - Home"}
    mock_confluence.get_child_pages.return_value = [
        {"id": "2001", "title": "TEST - Home"},
        {"id": "2002", "title": "TEST - Old Page"},
    ]
    mock_confluence.get_attachments_from_content.return_value = {"results": []}

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
                build(cfg)
            finally:
                os.chdir(original_cwd)

    # Verify NO pruning calls
    assert mock_confluence.remove_page.call_count == 0

