from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from http import HTTPStatus

import aiohttp


@dataclass
class SiteInfo:
    url: str
    text: str


HEADERS_BYPASS_BLOCK = {
    "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"  # noqa: E501
    r"(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.100.0",
    "Referer": "https://google.com/",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "*/*",
    "Connection": "keep-alive",
}


REGEX_REMOVE_HTML_COMMENTS = re.compile(r"(?=<!--)([\s\S]*?)-->", re.MULTILINE)


async def get_response(
    session: aiohttp.ClientSession,
    site: str,
    remove_comments: bool = False,
    allow_redirects: bool = True,
) -> SiteInfo | None:
    try:
        async with session.get(
            site,
            headers=HEADERS_BYPASS_BLOCK,
            allow_redirects=allow_redirects,
        ) as response:
            if response.status != HTTPStatus.OK:
                return None
            html_source = await response.text(errors="replace")
            if remove_comments:
                html_source = REGEX_REMOVE_HTML_COMMENTS.sub("", html_source)
            return SiteInfo(site, html_source)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass  # Ignore connection and timeout errors
    return None
