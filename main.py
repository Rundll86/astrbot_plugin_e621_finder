import astrbot.api.message_components as Comp
import httpx
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register

from .constants import RATING_LEVEL
from .utils import (
    compose_rating_map,
    create_data_path,
    filter_empty_string,
    format_post,
    merge_params,
    read_group_data,
    write_group_data,
)


@register("Random Post", "陨落基围虾", "随机获取某插画网站上的图片", "1.0.0")
class RandomPostPlugin(Star):

    CONSTANT_TAGS: list[str] = []

    USER_AGENT: str = ""
    BASE_URL: str = ""
    TAG_SEPARATOR: str = ""

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.client = httpx.AsyncClient()
        self.USER_AGENT = config["user_agent"]
        self.BASE_URL = config["base_url"]
        self.TAG_SEPARATOR = config["tag_separator"]
        create_data_path()

    @filter.command(
        "random-image",
        alias={
            "random",
            "image",
            "e621",
            "pixiv",
            "neko",
            "随机图",
            "随机",
            "图",
            "找图",
            "img",
            "e站",
        },
        desc="从某插画网站获取一张随机图",
    )
    async def execute_random_post(self, event: AstrMessageEvent, tags: str):
        yield event.plain_result(
            f"正在获取随机图：{self.get_api_url(self.format_tags(tags, event.get_group_id()))}"
        )
        try:
            post = await self.fetch_post(self.format_tags(tags, event.get_group_id()))
        except httpx.RequestError:
            yield event.plain_result("无法请求API，可能是服务端网络问题。")
            return
        if not post:
            yield event.plain_result("没有任何帖子符合该标签！")
            return
        url = post.get("file_url")
        if not url:
            yield event.plain_result("你的运气太好了，搜到的帖子刚好没带图。")
            return
        logger.info(post)
        yield event.chain_result(format_post(post))

    # 受不了了，指令组一直有bug，改为纯指令吧💔
    @filter.command("list-rating", desc="列出所有分级")
    async def list_rating(self, event: AstrMessageEvent):
        yield event.plain_result(f"{compose_rating_map()}\n\nall: 允许所有分级")

    @filter.command("set-rating", desc="设置当前分级")
    async def set_rating(
        self,
        event: AstrMessageEvent,
        new_rating: str = "all",
    ):
        if new_rating in ["s", "q", "e", "all"]:
            self.set_current_rating(event.get_group_id(), new_rating)
            if new_rating == "all":
                yield event.plain_result("已取消分级限制。")
            else:
                yield event.plain_result(f"分级已设置为：{RATING_LEVEL[new_rating]}")
        else:
            yield event.plain_result("无效分级标签。")

    @filter.command("look-rating", desc="查看当前分级", alias={"rating"})
    def look_rating(self, event: AstrMessageEvent):
        if self.get_current_rating(event.get_group_id()) == "all":
            yield event.plain_result("当前无分级限制。")
        else:
            yield event.plain_result(
                f"当前分级为：{RATING_LEVEL[self.get_current_rating(event.get_group_id())]}"
            )

    @filter.command("clear-rating", desc="清除分级限制")
    def clear_rating(self, event: AstrMessageEvent):
        self.set_current_rating(event.get_group_id(), "all")
        yield event.plain_result("已取消分级限制。")

    @filter.llm_tool("search_random_image")
    async def get_random_image(self, event: AstrMessageEvent, tags: list[str]):
        """搜索或获取随机图

        Args:
            tags(array[string]): The label content of the random graph must consist of all-English keywords. If it is a anime character name, use the official translation.
        """
        tagsProcessed = self.format_tags(
            self.TAG_SEPARATOR.join(tags), event.get_group_id()
        )
        post = await self.fetch_post(tagsProcessed)
        await event.send(
            MessageChain(chain=[Comp.Plain(f"正在使用标签搜索随机图：{tagsProcessed}")])
        )
        if post:
            await event.send(MessageChain(chain=format_post(post)))
            return f"帖子数据：{post}"
        else:
            return "没有任何帖子符合你所给的标签。"

    @filter.command_group("constants", desc="恒标签相关指令")
    async def constants(self):
        pass

    @constants.command("add", alias={"+"}, desc="添加恒标签")
    async def add_constants(self, event: AstrMessageEvent, tag: str):
        current = self.get_user_constant_tags(event.get_group_id())
        if current.count(tag) > 0:
            yield event.plain_result("这个恒标签已存在。")
        else:
            current.append(tag)
            self.set_user_constant_tags(event.get_group_id(), current)
            yield event.plain_result("恒标签添加成功！")

    @constants.command("delete", alias={"-"}, desc="删除恒标签")
    async def delete_constants(self, event: AstrMessageEvent, tag: str):
        current = self.get_user_constant_tags(event.get_group_id())
        if current.count(tag) == 0:
            yield event.plain_result("这个恒标签根本不存在。")
        else:
            current.remove(tag)
            self.set_user_constant_tags(event.get_group_id(), current)
            yield event.plain_result("恒标签删除成功！")

    @constants.command("replace", alias={"="}, desc="替换恒标签（删除+添加）")
    async def replace_constants(
        self, event: AstrMessageEvent, old_tag: str, new_tag: str
    ):
        current = self.get_user_constant_tags(event.get_group_id())
        if current.count(old_tag) == 0:
            yield event.plain_result(f"目标恒标签{old_tag}根本不存在。")
            return
        if current.count(new_tag) > 0:
            yield event.plain_result(f"新的恒标签{new_tag}已存在。")
            return
        index = current.index(old_tag)
        current.remove(old_tag)
        current.insert(index, new_tag)
        self.set_user_constant_tags(event.get_group_id(), current)
        yield event.plain_result(f"替换成功：{old_tag}->{new_tag}")

    @constants.command("get", alias={"?"}, desc="查看当前恒标签列表")
    async def get_constants(self, event: AstrMessageEvent):
        result = self.TAG_SEPARATOR.join(
            self.get_user_constant_tags(event.get_group_id())
        )
        yield event.plain_result(result if result else "当前没有任何恒标签。")

    async def fetch_post(self, tags: str) -> dict | None:
        url = self.get_api_url(tags)
        logger.info(url)
        response = await self.client.get(
            url,
            headers={
                "User-Agent": (
                    self.USER_AGENT if self.USER_AGENT else "RandomPostPlugin/1.0"
                )
            },
        )
        data: dict = response.json()
        if data.get("success", True):
            return data
        else:
            return None

    def format_tags(self, userRawTags: str, group: str):
        return "+".join(
            [
                x.replace(" ", "_")
                for x in self.compose_total_tags(
                    userRawTags.split(self.TAG_SEPARATOR), group
                )
            ]
        )

    def compose_total_tags(self, userTags: list[str], group: str) -> list[str]:
        return (
            filter_empty_string(userTags)
            + self.CONSTANT_TAGS
            + (
                []
                if self.get_current_rating(group) == "all"
                else [f"rating:{self.get_current_rating(group)}"]
            )
        )

    def get_api_url(self, tags: str):
        logger.info(f"正在合成url：{tags}")
        return merge_params(self.BASE_URL, {"tags": tags})

    def get_user_constant_tags(self, group: str) -> list[str]:
        return read_group_data(group)["constants"]

    def set_user_constant_tags(self, group: str, new_constants: list[str]):
        return write_group_data(group, "constants", new_constants)

    def get_current_rating(self, group: str):
        return read_group_data(group)["rating"]

    def set_current_rating(self, group: str, new_rating: str):
        return write_group_data(group, "rating", new_rating)

    async def terminate(self):
        await self.client.aclose()
