from __future__ import annotations

import re

from hypothesis import provisional, strategies as st

REGEX_REMOVE_SLASHES_AND_SCHEME = re.compile(r"^\S+?:\/\/")
REGEX_REMOVE_SCHEME = re.compile(r"^\S+?:")


@st.composite
def raw_url(draw: st.DrawFn) -> str:
    is_url_slashed = draw(st.booleans())
    url = draw(provisional.urls())
    if is_url_slashed:
        url = REGEX_REMOVE_SCHEME.sub("", url)
    else:
        url = REGEX_REMOVE_SLASHES_AND_SCHEME.sub("", url)
    return url
