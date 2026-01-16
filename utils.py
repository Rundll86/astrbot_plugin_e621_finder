import json
import os
import re
from typing import TypeVar
from urllib.parse import unquote

import httpx

import astrbot.api.message_components as Comp

from .constants import INITIAL_GROUP_DATA, PLUGIN_DATA_PATH, RATING_LEVEL

T = TypeVar("T")
K = TypeVar("K")


def format_tags(tags: list[str]):
    return "+".join([x.replace(" ", "_") for x in tags])


def format_post(post: dict, template: str) -> list[Comp.BaseMessageComponent]:
    file_url = post.get("file_url")
    return [
        Comp.Image.fromURL(file_url) if file_url else Comp.Plain("[此帖子不带图]\n"),
        Comp.Plain(render_template(template, post)),
    ]


def merge_params(url: str, params: dict):
    return unquote(str(httpx.Request("GET", url, params=params).url))


def filter_empty_string(array: list[T]) -> list[T]:
    return [v for v in array if v not in (None, "")]


def compose_rating_map(separator: str = ",\n"):
    return separator.join(
        [f"[{key.upper()}]{RATING_LEVEL[key][1:]}" for key in RATING_LEVEL]
    )


def get_group_data_path(group: str) -> str:
    return os.path.join(PLUGIN_DATA_PATH, f"{group}.json")


def open_group_file(group: str, mode: str):
    with open(get_group_data_path(group), mode, encoding="utf8") as file:
        return file


def read_group_data(group: str) -> dict:
    path = get_group_data_path(group)
    if not os.path.exists(path):
        return INITIAL_GROUP_DATA  # 路径不存在的话就说明这个群第一次存取数据，肯定是写，直接返回默认值
    return json.load(open_group_file(group, "r"))


def write_group_data(group: str, key: str, value: object) -> dict:
    data = read_group_data(group)
    data[key] = value
    json.dump(data, open_group_file(group, "w"), ensure_ascii=False)
    return data


def render_template(template: str, data: dict) -> str:
    def replace_match(match: re.Match[str]):
        path_str = match.group(1)
        keys = path_str.split(".")
        current = data
        try:
            for key in keys:
                if isinstance(current, dict):
                    current = current[key]
                elif isinstance(current, list):
                    current = current[int(key)]
                else:
                    return match.group(0)
            return str(current)
        except (KeyError, IndexError, ValueError, TypeError):
            return match.group(0)

    return re.compile(r"\{([^{}]+)\}").sub(replace_match, template)
