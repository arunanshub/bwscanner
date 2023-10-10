#! /bin/env python3
from __future__ import annotations

import argparse
import asyncio
import re
import urllib.parse
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import quote, urljoin, urlunsplit

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


async def get_response(
    session: aiohttp.ClientSession,
    site: str,
    remove_comments: bool = False,
) -> SiteInfo | None:
    try:
        async with session.get(site, headers=HEADERS_BYPASS_BLOCK) as response:
            if response.status != HTTPStatus.OK:
                return None
            html_source = await response.text(errors="replace")
            if remove_comments:
                html_source = REGEX_REMOVE_HTML_COMMENTS.sub("", html_source)
            return SiteInfo(site, html_source)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass  # Ignore connection and timeout errors
    return None


def get_cleaned_url(url_without_scheme: str) -> str:
    """
    TODO: Give a better name to this function.
    """
    return urlunsplit(("https", url_without_scheme, "", "", ""))


def clean_link(input_link: str) -> str:
    parsed_url = urllib.parse.urlparse(input_link)
    if not parsed_url.scheme:
        parsed_url = parsed_url._replace(scheme="https")
    return urllib.parse.urlunparse(parsed_url)


def get_builtwith_websites(source: str) -> list[str]:
    urls = html.fromstring(source).xpath(
        r".//tr[@data-domain]/td[@class='pl-0 text-primary']/text()"
    )
    assert isinstance(urls, list)
    return list(map(get_cleaned_url, urls))  # type: ignore


def is_regex_matching(data: str, regex: re.Pattern[str]) -> bool:
    return regex.search(data) is not None


def get_builtwith_technology_link(source: str) -> str | None:
    tree = html.fromstring(source)
    technology_link_arr = tree.xpath(
        r".//nav[@aria-label='breadcrumb']/ol/li/a/@href[contains(., '//trends')]"  # noqa: E501
    )
    assert isinstance(technology_link_arr, list)
    if not len(technology_link_arr):
        return None
    return clean_link(technology_link_arr[0])  # type: ignore


async def get_builtwith_technology_description(
    session: aiohttp.ClientSession,
    technology_site: str,
) -> TechnologyDetails | None:
    site_data = await get_response(session, technology_site)
    if site_data is None:
        return None

    tree = html.fromstring(site_data.text)
    p_elements = tree.xpath(r".//div/*/div[@class='col-9 col-md-10']/p")
    assert isinstance(p_elements, list)
    if len(p_elements) != 3:  # noqa: PLR2004
        return None

    # TODO: the type errors are too complex to solve. Python tries to be
    #  TypeScript without giving TypeScript's benefits.
    p_description, p_techsite, p_tags = p_elements
    description = p_description.text  # type: ignore
    technology_site = p_techsite.xpath(r".//a/text()")[0]  # type: ignore
    tags = p_tags.xpath(r".//a/text()")  # type: ignore
    return TechnologyDetails(description, technology_site, tags)  # type: ignore


async def process_sites(
    session: aiohttp.ClientSession,
    bwsite_source: str,
    regex: re.Pattern[str],
    remove_comments: bool,
) -> Stats | None:
    # start the response fetch early on
    tasks = []
    for site in get_builtwith_websites(bwsite_source):
        tasks.append(
            asyncio.create_task(get_response(session, site, remove_comments))
        )

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


async def main() -> None:
    parser = argparse.ArgumentParser(description="Process builtwith websites.")
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
    bwsite = urljoin(BUILTWITH_SITE, quote(bwtech))
    print(bwsite)

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(
            total=None,
            sock_connect=args.timeout,
            sock_read=args.timeout,
        )
    ) as session:
        bwsite_resp = await get_response(session, bwsite)
        if bwsite_resp is None:
            return

        # then print the details
        bw_techsite = get_builtwith_technology_link(bwsite_resp.text)
        if bw_techsite is not None:
            tech_details = await get_builtwith_technology_description(
                session, bw_techsite
            )
            if tech_details is not None:
                print("Techsite:", tech_details.site)
                print("Description:", tech_details.description)
                print("Tags:", ", ".join(tech_details.tags), "\n")

        pattern = input("regex: ")
        regex = re.compile(
            pattern,
            re.MULTILINE | args.ignorecase & re.IGNORECASE,
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


if __name__ == "__main__":
    asyncio.run(main())
