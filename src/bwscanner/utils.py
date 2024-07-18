from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import re


def get_normalized_url(url: str) -> str:
    """Takes a url of form `//site.com` or `site.com` and converts it to `https://site.com`."""
    parsed_url = urllib.parse.urlparse(url, "https")
    normalized_url = parsed_url
    if not parsed_url.netloc and parsed_url.path:
        normalized_url = parsed_url._replace(netloc=parsed_url.path, path="")
    return urllib.parse.urlunparse(normalized_url)


def is_regex_matching(data: str, regex: re.Pattern[str]) -> bool:
    """Check if regex matches or not."""
    return regex.search(data) is not None
