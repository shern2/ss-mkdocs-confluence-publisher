from unittest.mock import MagicMock, call

from mkdocs_confluence_publisher.create_pages import PageCreator


def test_prune_orphans():
    """Test pruning orphans."""
    mock_client = MagicMock()

    # Setup children structure under parent 123
    # 1001: active
    # 1002: orphan -> SHOULD BE DELETED
    # 1003: orphan (no prefix) -> SHOULD BE DELETED
    # 1004: child of 1003 -> WON'T BE VISITED because 1003 is deleted

    mock_client.get_child_pages.side_effect = lambda pid: {
        "123": [
            {"id": "1001", "title": "PREFIX_Active_SUFFIX"},
            {"id": "1002", "title": "PREFIX_Orphan_SUFFIX"},
            {"id": "1003", "title": "Other Page"},
        ],
        "1001": [],
        "1003": [
            {"id": "1004", "title": "PREFIX_Deep Orphan_SUFFIX"},
        ],
        "1004": []
    }.get(str(pid), [])

    page_creator = PageCreator(
        confluence_client=mock_client,
        prefix="PREFIX_",
        suffix="_SUFFIX",
        space_key="TEST"
    )

    # Mark 1001 as active
    page_creator.active_page_ids = {"1001"}

    page_creator.prune_orphans("123")

    # Check deletions
    assert mock_client.remove_page.call_count == 2
    mock_client.remove_page.assert_has_calls([
        call("1002"),
        call("1003")
    ], any_order=True)

    # Check recursions
    # 123 (start), 1001 (active, no deletion)
    # 1002 and 1003 are deleted so we don't call get_child_pages for them
    assert mock_client.get_child_pages.call_count == 2
    mock_client.get_child_pages.assert_has_calls([
        call("123"),
        call("1001"),
    ], any_order=True)

