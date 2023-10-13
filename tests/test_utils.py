from __future__ import annotations

import bwscanner.utils
from hypothesis import given

from .utils import raw_url


@given(url=raw_url())
def test_idempotent_get_normalized_url(url: str) -> None:
    result = bwscanner.utils.get_normalized_url(url=url)
    repeat = bwscanner.utils.get_normalized_url(url=result)
    assert result == repeat, (result, repeat)
