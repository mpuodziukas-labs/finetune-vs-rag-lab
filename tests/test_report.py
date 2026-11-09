import pytest

from ftlab.report import replace_blocks


def test_replace_block_roundtrip_and_missing_marker() -> None:
    text = "a\n<!-- BEGIN:x -->\nold\n<!-- END:x -->\nb"
    out = replace_blocks(text, {"x": "new"})
    assert out == "a\n<!-- BEGIN:x -->\nnew\n<!-- END:x -->\nb"
    assert replace_blocks(out, {"x": "new"}) == out  # idempotent
    with pytest.raises(RuntimeError):
        replace_blocks(text, {"y": "z"})
