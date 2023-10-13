#! /bin/env python3
from __future__ import annotations

import argparse
import asyncio
import re
import urllib.parse

import aiohttp

from . import builtwith, core, net

BUILTWITH_SITE = "https://trends.builtwith.com/websitelist/"


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Process builtwith websites.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("bwtech", help="The builtwith tech.")
    parser.add_argument(
        "-n",
        "--no-remove-comments",
        help="Remove all HTML comments.",
        action="store_false",
    )
    parser.add_argument(
        "-i",
        "--ignorecase",
        help="Ignore case.",
        action="store_true",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        help="Timeout in seconds",
        default=7,
        type=int,
    )
    # parser.add_argument("regex", help="The regular expression to match.")

    args = parser.parse_args()

    bwtech: str = args.bwtech
    bwtech = bwtech.replace("/", " ")
    bwsite = urllib.parse.urljoin(BUILTWITH_SITE, urllib.parse.quote(bwtech))
    print(bwsite)

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(
            total=None,
            sock_connect=args.timeout,
            sock_read=args.timeout,
        )
    ) as session:
        bwsite_resp = await net.get_response(
            session,
            bwsite,
            allow_redirects=False,
        )
        if bwsite_resp is None:
            return

        # print the details about the Technology
        bw_techsite = builtwith.get_technology_link(bwsite_resp.text)
        if bw_techsite is not None:
            tech_details = await builtwith.get_technology_details(
                session, bw_techsite
            )
            if tech_details is not None:
                print("Techsite:", tech_details.site)
                print("Description:", tech_details.description)
                print("Tags:", ", ".join(tech_details.tags))
                print("Image link:", tech_details.image_link)
                print(
                    "Is image blank:",
                    "blank" in tech_details.image_link.rsplit("/", 1)[-1],
                    "\n",
                )

        pattern = input("regex: ")
        regex = re.compile(
            pattern,
            re.MULTILINE | (re.IGNORECASE if args.ignorecase else re.NOFLAG),  # type: ignore[attr-defined]
        )

        stats = await core.process_sites(
            session,
            bwsite_resp.text,
            regex,
            args.no_remove_comments,
        )

    if stats is not None:
        print(f"\nChecked {stats.checked} websites")
        print(f"Passed {stats.matched} websites")
        print(f"Failed in {stats.failed} websites")
        print(f"Total checked {stats.checked + stats.failed} websites")


def main() -> None:
    asyncio.run(_main())
