#! /bin/env python3
from __future__ import annotations

import argparse
import asyncio
import re
import typing
import urllib.parse
from dataclasses import dataclass
from http import HTTPStatus

import aiohttp
from lxml import html

REGEX_REMOVE_HTML_COMMENTS = re.compile(r"(?=<!--)([\s\S]*?)-->", re.MULTILINE)

BUILTWITH_SITE = "https://trends.builtwith.com/websitelist/"

HEADERS_BYPASS_BLOCK = {
    "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"  # noqa: E501
    r"(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.100.0",
    "Referer": "https://google.com/",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "*/*",
    "Connection": "keep-alive",
}


@dataclass
class SiteInfo:
    url: str
    text: str


@dataclass
class Stats:
    checked: int
    failed: int
    matched: int


@dataclass
class TechnologyDetails:
    description: str
    site: str
    tags: str
    image_link: str


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


def get_normalized_url(url: str) -> str:
    """
    Takes a url of form `//site.com` or `site.com` and converts it to `https://site.com`.
    """
    parsed_url = urllib.parse.urlparse(url, "https")
    normalized_url = parsed_url
    if not parsed_url.netloc and parsed_url.path:
        normalized_url = parsed_url._replace(netloc=parsed_url.path, path="")
    return urllib.parse.urlunparse(normalized_url)


def get_builtwith_client_websites(source: str) -> list[str]:
    """
    Parse the "Uses" page of BuiltWith and list the websites that uses a
    particular technology.
    """
    urls = html.fromstring(source).xpath(
        r".//tr[@data-domain]/td[@class='pl-0 text-primary']/text()"
    )
    assert isinstance(urls, list)
    return list(map(get_normalized_url, urls))  # type: ignore


def is_regex_matching(data: str, regex: re.Pattern[str]) -> bool:
    """Check if regex matches or not."""
    return regex.search(data) is not None


def get_builtwith_technology_link(source: str) -> str | None:
    """
    Parse the BuiltWith "Uses" page and get the link to the BuiltWith
    "Technology Overview" page.
    """
    tree = html.fromstring(source)
    technology_link_arr = tree.xpath(
        r".//nav[@aria-label='breadcrumb']/ol/li/a/@href[contains(., '//trends')]"  # noqa: E501
    )
    assert isinstance(technology_link_arr, list)
    if not len(technology_link_arr):
        return None
    return get_normalized_url(technology_link_arr[0])  # type: ignore


async def get_builtwith_technology_details(
    session: aiohttp.ClientSession,
    technology_site: str,
) -> TechnologyDetails | None:
    """
    Get the technology details from the BuiltWith "Technology Details" page.
    """
    site_data = await get_response(session, technology_site)
    if site_data is None:
        return None

    tree = html.fromstring(site_data.text)
    p_elements = tree.xpath(r".//div/*/div[@class='col-9 col-md-10']/p")
    assert isinstance(p_elements, list)
    if len(p_elements) != 3:  # noqa: PLR2004
        return None

    # get image link
    image_el = tree.xpath(
        r".//div[@class='col-md-2 col-3 text-center']/img/@data-src"
    )
    assert isinstance(image_el, list)
    image_link = typing.cast(str, image_el.pop())

    # TODO: the type errors are too complex to solve. Python tries to be
    #  TypeScript without giving TypeScript's benefits.
    p_description, p_techsite, p_tags = p_elements
    description = p_description.text  # type: ignore
    technology_site = p_techsite.xpath(r".//a/text()")[0]  # type: ignore
    tags = p_tags.xpath(r".//a/text()")  # type: ignore
    return TechnologyDetails(description, technology_site, tags, image_link)  # type: ignore


async def process_sites(
    session: aiohttp.ClientSession,
    bwsite_source: str,
    regex: re.Pattern[str],
    remove_comments: bool,
) -> Stats | None:
    # start the response fetch early on
    tasks = []
    for site in get_builtwith_client_websites(bwsite_source):
        tasks.append(
            asyncio.create_task(get_response(session, site, remove_comments))
        )

    if not tasks:
        return None

    failed_websites_count = 0
    checked_websites_count = 0
    regex_match_count = 0

    for completed_task in asyncio.as_completed(tasks):
        result: SiteInfo | None = await completed_task
        if result is None:
            failed_websites_count += 1
            continue
        checked_websites_count += 1
        if is_regex_matching(result.text, regex):
            regex_match_count += 1
            print(result.url)

    return Stats(
        checked_websites_count,
        failed_websites_count,
        regex_match_count,
    )


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
        bwsite_resp = await get_response(
            session,
            bwsite,
            allow_redirects=False,
        )
        if bwsite_resp is None:
            return

        # print the details about the Technology
        bw_techsite = get_builtwith_technology_link(bwsite_resp.text)
        if bw_techsite is not None:
            tech_details = await get_builtwith_technology_details(
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
            re.MULTILINE | (re.IGNORECASE if args.ignorecase else re.NOFLAG),
        )

        stats = await process_sites(
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
