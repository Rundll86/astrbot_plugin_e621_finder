import json
import os
from typing import TypeVar
from urllib.parse import unquote

import httpx

import astrbot.api.message_components as Comp

from .constants import INITIAL_GROUP_DATA, PLUGIN_DATA_PATH, RATING_LEVEL

T = TypeVar("T")
K = TypeVar("K")


def format_tags(tags: list[str]):
    return "+".join([x.replace(" ", "_") for x in tags])


def format_post(post: dict):
    return [
        Comp.Image.fromURL(post["file_url"]),
        Comp.Plain(
            f"#{post['id']} [❤️{post['score']} ⭐{post['fav_count']} 📻{post['comment_count']}]（{RATING_LEVEL[post['rating']]}）\n\n{post['description']}"
        ),
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
