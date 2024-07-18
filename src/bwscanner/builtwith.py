from __future__ import annotations

import typing
from dataclasses import dataclass

from lxml import html

from . import net, utils

if typing.TYPE_CHECKING:
    import aiohttp


@dataclass
class TechnologyDetails:
    description: str
    site: str
    tags: str
    image_link: str


def get_client_websites(source: str) -> list[str]:
    """
    Parse the "Uses" page of BuiltWith and list the websites that uses a
    particular technology.
    """
    urls = html.fromstring(source).xpath(
        r".//tr[@data-domain]/td[@class='pl-0 text-primary']/text()",
    )
    assert isinstance(urls, list)  # noqa: S101
    return list(map(utils.get_normalized_url, urls))  # type: ignore[arg-type]


def get_technology_link(source: str) -> str | None:
    """
    Parse the BuiltWith "Uses" page and get the link to the BuiltWith
    "Technology Overview" page.
    """
    tree = html.fromstring(source)
    technology_link_arr = tree.xpath(
        r".//nav[@aria-label='breadcrumb']/ol/li/a/@href[contains(., '//trends')]",
    )
    assert isinstance(technology_link_arr, list)  # noqa: S101
    if not len(technology_link_arr):
        return None
    return utils.get_normalized_url(technology_link_arr[0])  # type: ignore[arg-type]


async def get_technology_details(
    session: aiohttp.ClientSession,
    technology_site: str,
) -> TechnologyDetails | None:
    """
    Get the technology details from the BuiltWith "Technology Details" page.
    """
    site_data = await net.get_response(session, technology_site)
    if site_data is None:
        return None

    tree = html.fromstring(site_data.text)
    p_elements = tree.xpath(r".//div/*/div[@class='col-9 col-md-10']/p")
    assert isinstance(p_elements, list)  # noqa: S101
    if len(p_elements) != 3:  # noqa: PLR2004
        return None

    # get image link
    image_el = tree.xpath(
        r".//div[@class='col-md-2 col-3 text-center']/img/@data-src",
    )
    assert isinstance(image_el, list)  # noqa: S101
    image_link = typing.cast(str, image_el.pop())

    # TODO: the type errors are too complex to solve. Python tries to be
    #  TypeScript without giving TypeScript's benefits.
    p_description, p_techsite, p_tags = p_elements
    description = p_description.text  # type: ignore[union-attr]
    technology_site = p_techsite.xpath(r".//a/text()")[0]  # type: ignore[union-attr,index,assignment]
    tags = p_tags.xpath(r".//a/text()")  # type: ignore[union-attr]
    return TechnologyDetails(description, technology_site, tags, image_link)  # type: ignore[arg-type]
