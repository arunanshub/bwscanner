from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import builtwith, net, utils

if TYPE_CHECKING:
    import re

    import aiohttp


@dataclass
class Stats:
    checked: int
    failed: int
    matched: int


async def process_sites(
    session: aiohttp.ClientSession,
    bwsite_source: str,
    regex: re.Pattern[str],
    *,
    remove_comments: bool = False,
) -> Stats | None:
    # start the response fetch early on
    tasks = []
    for site in builtwith.get_client_websites(bwsite_source):
        tasks.append(  # noqa: PERF401
            asyncio.create_task(
                net.get_response(session, site, remove_comments=remove_comments),
            ),
        )

    if not tasks:
        return None

    failed_websites_count = 0
    checked_websites_count = 0
    regex_match_count = 0

    for completed_task in asyncio.as_completed(tasks):
        result: net.SiteInfo | None = await completed_task
        if result is None:
            failed_websites_count += 1
            continue
        checked_websites_count += 1
        if utils.is_regex_matching(result.text, regex):
            regex_match_count += 1
            print(result.url)

    return Stats(
        checked_websites_count,
        failed_websites_count,
        regex_match_count,
    )
