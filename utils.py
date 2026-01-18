import copy
import json
import os
from typing import Literal, TypeVar
from urllib.parse import unquote

import aiocqhttp
import httpx

import astrbot.api.message_components as Comp

from .constants import INITIAL_GROUP_DATA, PLUGIN_DATA_PATH, RATING_LEVEL
from .parser import render_template

T = TypeVar("T")
K = TypeVar("K")


def format_tags(tags: list[str]):
    return "+".join([x.replace(" ", "_") for x in tags])


def format_post(
    post: dict,
    type: Literal["random"] | Literal["post"],
    template: str,
    index: tuple[int, int] | None = None,
) -> list[Comp.BaseMessageComponent]:
    if type == "random":
        file_url = post.get("file_url")
    elif type == "post":
        file: dict = post.get("file", {})
        file_url = file.get("url")
    result: list[Comp.BaseMessageComponent] = [
        Comp.Plain(
            render_template(
                f"\n{template}",
                post
                | {
                    "RATING": RATING_LEVEL[post["rating"]],
                },
            )
        ),
    ]
    try:
        result.insert(
            0,
            Comp.Image.fromURL(file_url)
            if file_url
            else Comp.Image.fromFileSystem(
                os.path.join(os.path.dirname(__file__), "tip.png")
            ),
        )
    except aiocqhttp.exceptions.NetworkError:
        result = [
            Comp.Plain(f"服务端下载图片失败，请使用view {post['id']}重新查看帖子。")
        ]
    if index:
        result.insert(0, Comp.Plain(f"第({index[0] + 1}/{index[1]})条帖子："))
    return result


def merge_params(url: str, params: dict):
    return unquote(str(httpx.Request("GET", url, params=params).url))


def filter_empty_string(array: list[T]) -> list[T]:
    return [v for v in array if v not in (None, "")]


def compose_rating_map(separator: str = ",\n"):
    return separator.join(
        [f"[{key.upper()}]{RATING_LEVEL[key][1:]}" for key in RATING_LEVEL]
    )


def get_group_data_path(group: str):
    return PLUGIN_DATA_PATH / f"{group}.json"


def open_group_file(group: str, mode: str):
    return open(get_group_data_path(group), mode, encoding="utf8")


def read_group_data(group: str) -> dict:
    path = get_group_data_path(group)
    if not os.path.exists(path):
        # 路径不存在的话就说明这个群第一次存取数据，肯定是写，直接返回默认值
        return copy.deepcopy(INITIAL_GROUP_DATA)
    with open_group_file(group, "r") as file:
        return json.load(file)


def write_group_data(group: str, key: str, value: object) -> dict:
    data = read_group_data(group)
    data[key] = value
    with open_group_file(group, "w") as file:
        json.dump(data, file, ensure_ascii=False)
        return data
