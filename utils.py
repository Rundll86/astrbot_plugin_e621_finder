import astrbot.api.message_components as Comp
import httpx

from constants import RATING_LEVEL


def format_tags(tags: list[str]):
    return "+".join(map(lambda x: x.replace(" ", "_"), tags))


def format_post(post: dict):
    return [
        Comp.Image.fromURL(post["file_url"]),
        Comp.Plain(
            f"#{post['id']} [❤️{post['score']} ⭐{post['fav_count']} 📻{post['comment_count']}]（{RATING_LEVEL[post['rating']]}）\n\n{post['description']}"
        ),
    ]


def merge_params(url: str, params: dict):
    return httpx.Request("GET", url, params=params).url


def filter_empty_string(array: list):
    return [v for v in array if v not in (None, "")]


def compose_rating_map(separator: str = ",\n"):
    return separator.join(
        map(
            lambda key: f"[{key.upper()}]{RATING_LEVEL[key][1:]}",
            RATING_LEVEL,
        )
    )
