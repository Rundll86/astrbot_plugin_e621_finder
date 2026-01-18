from json import JSONDecodeError
from urllib.parse import urljoin

import httpx

from astrbot.api import message_components as Comp
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star

from .constants import RATING_LEVEL
from .utils import (
    compose_rating_map,
    filter_empty_string,
    format_post,
    merge_params,
    read_group_data,
    write_group_data,
)


class RandomPostPlugin(Star):
    # 插件不管怎么请求API都会有这里面的标签，可以用来硬编码强制筛选，防止一些莫名其妙bug
    CONSTANT_TAGS: list[str] = []

    USER_AGENT: str = ""
    BASE_URL: str = ""
    TAG_SEPARATOR: str = ""
    POST_TEMPLATE: str = ""
    MAX_COUNT_POSTS: int = -1

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.client = httpx.AsyncClient()
        self.USER_AGENT = config["user_agent"]
        self.BASE_URL = config["base_url"]
        self.TAG_SEPARATOR = config["tag_separator"]
        self.POST_TEMPLATE = config["post_template"]
        self.MAX_COUNT_POSTS = config["max_count_posts"]

    # region 命令&LLM工具
    @filter.command(
        "random-image",
        alias={
            "random",
            "e621",
            "pixiv",
            "neko",
            "猫娘",
            "随机图",
            "找图",
            "e站",
        },
        desc="从某插画网站获取一张随机图",
    )
    async def command_random_post(self, event: AstrMessageEvent, tags: str):
        yield self.tip_fetching_random_image(event, tags)
        try:
            post = await self.fetch_random_post(
                self.format_tags(tags, event.get_group_id())
            )
            yield event.chain_result(format_post(post[0], "random", self.POST_TEMPLATE))
        except Exception as e:
            yield event.plain_result(str(e))

    @filter.command("fetch-post", alias={"fetch", "post", "查看", "view"})
    async def command_fetch_post(self, event: AstrMessageEvent, id: int):
        yield self.tip_fetching_exact_image(event, id)
        try:
            post = await self.fetch_post_by_id(id)
            yield event.chain_result(format_post(post[0], "post", self.POST_TEMPLATE))
        except Exception as e:
            yield event.plain_result(str(e))

    @filter.command("search-post", alias={"search", "find", "搜索", "查找"})
    async def command_search_post(
        self, event: AstrMessageEvent, tags: str, count: int, page: int = 1
    ):
        if count < 1 or count > self.MAX_COUNT_POSTS or not count % 1 == 0:
            yield event.plain_result(
                f"为防止刷屏，命题 count(0,{self.MAX_COUNT_POSTS}]∩Z 必须成立。"
            )
            return
        tags = self.format_tags(tags, event.get_group_id())
        yield self.tip_searching_image(event, count, tags, page)
        try:
            posts = await self.search_post(count, tags, page)
            for post in posts:
                yield event.chain_result(format_post(post, "post", self.POST_TEMPLATE))
        except Exception as e:
            yield event.plain_result(str(e))

    @filter.llm_tool("search_random_image")
    async def get_random_image(self, event: AstrMessageEvent, tags: list[str]):
        """搜索或获取随机图

        Args:
            tags(array[string]): The label content of the random graph must consist of all-English keywords. If it is a anime character name, use the official translation.
        """
        try:
            post = await self.fetch_random_post(
                self.format_tags(self.TAG_SEPARATOR.join(tags), event.get_group_id())
            )
            await event.send(
                MessageChain(chain=format_post(post[0], "random", self.POST_TEMPLATE))
            )
            return f"帖子数据：{post}"
        except Exception as e:
            await event.send(MessageChain(chain=[Comp.Plain(str(e))]))
            return str(e)

    @filter.llm_tool("view_post")
    async def get_exact_image(self, event: AstrMessageEvent, id: int):
        """给用户展示一个已知帖子，如果用户提供了类似ID的东西就调用这个工具，

        Args:
            id(number): The known post ID.
        """
        try:
            post = await self.fetch_post_by_id(id)
            await event.send(
                MessageChain(chain=format_post(post[0], "post", self.POST_TEMPLATE))
            )
            return f"帖子数据：{post}"
        except Exception as e:
            await event.send(MessageChain(chain=[Comp.Plain(str(e))]))
            return str(e)

    # region 分级
    @filter.command_group("rating", desc="分级相关指令")
    def rating(self):
        pass

    @rating.command("list", desc="列出所有分级")
    async def list_rating(self, event: AstrMessageEvent):
        yield event.plain_result(f"{compose_rating_map()}\n\nall: 允许所有分级")

    @rating.command("set", desc="设置当前分级")
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

    @rating.command("look", desc="查看当前分级")
    async def look_rating(self, event: AstrMessageEvent):
        if self.get_current_rating(event.get_group_id()) == "all":
            yield event.plain_result("当前无分级限制。")
        else:
            yield event.plain_result(
                f"当前分级为：{RATING_LEVEL[self.get_current_rating(event.get_group_id())]}"
            )

    @rating.command("clear", desc="清除分级限制")
    async def clear_rating(self, event: AstrMessageEvent):
        self.set_current_rating(event.get_group_id(), "all")
        yield event.plain_result("已取消分级限制。")

    # region 恒标签
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

    # 发提示
    def tip_fetching_random_image(self, event: AstrMessageEvent, tags: str):
        return event.plain_result(
            f"正在获取随机图：{self.get_url_random_post(self.format_tags(tags, event.get_group_id()))}"
        )

    def tip_fetching_exact_image(self, event: AstrMessageEvent, id: int):
        return event.plain_result(f"正在获取帖子#{id}：{self.get_url_exact_post(id)}")

    def tip_searching_image(
        self, event: AstrMessageEvent, count: int, tags: str, page: int
    ):
        return event.plain_result(
            f"正在搜索符合{tags}标签的{count}条帖子：{self.get_url_search_post(count, tags, page)}"
        )

    # 合成一下apiurl
    def get_url_random_post(self, tags: str):
        return self.join_api("posts/random.json", {"tags": tags})

    def get_url_exact_post(self, id: int):
        return self.join_api(f"posts/{id}.json")

    def get_url_search_post(self, count: int, tags: str, page: int):
        return self.join_api(
            "posts.json",
            {
                "tags": tags,
                "limit": count,
                "page": page,
            },
        )

    # region 请求
    async def fetch_api(self, url: str) -> list[dict]:
        try:
            response = await self.client.get(
                url,
                headers={
                    "User-Agent": (
                        self.USER_AGENT if self.USER_AGENT else "RandomPostPlugin/1.0"
                    )
                },
            )
            if response.status_code in [404, 200]:
                try:
                    data: dict = response.json()
                    if data.get("success", True):
                        data = data.get("post", data.get("posts", data))
                        return [data] if isinstance(data, dict) else data
                    else:
                        raise ValueError("未搜索到任何帖子。")
                except JSONDecodeError:
                    raise ValueError("请求失败，API未返回帖子数据。")
            else:
                raise ValueError(
                    f"请求失败，来自API的响应无效，状态码：{response.status_code}"
                )
        except httpx.RequestError:
            raise Exception("请求失败，服务端网络问题。")

    async def fetch_random_post(self, tags: str):
        return await self.fetch_api(self.get_url_random_post(tags))

    async def fetch_post_by_id(self, id: int):
        return await self.fetch_api(self.get_url_exact_post(id))

    async def search_post(self, count: int, tags: str, page: int):
        return await self.fetch_api(self.get_url_search_post(count, tags, page))

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

    def join_api(self, child: str, params: dict = {}):
        return merge_params(urljoin(self.BASE_URL, child), params)

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
