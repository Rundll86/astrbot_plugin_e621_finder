import astrbot.api.message_components as Comp
import httpx
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register


@register("Random Post", "陨落基围虾", "随机获取某插画网站上的图片", "1.0.0")
class RanddomPostPlugin(Star):
    RATING_LEVEL: dict[str, str] = {
        "s": "Safe",
        "q": "Questionable",
        "e": "Explicit",
    }
    CONSTANT_TAGS: list[str] = []
    USER_AGENT: str = ""

    currentRating: str = "s"
    userConstantTags: list[str] = ["male"]

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.client = httpx.AsyncClient()
        self.USER_AGENT = config["user_agent"]

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
    async def executeRandomPost(self, event: AstrMessageEvent, tags: str = ""):
        yield event.plain_result(
            f"正在获取随机图：{self.getApiUrl(self.processTags(tags))}"
        )
        try:
            post = await self.getPost(self.processTags(tags))
        except:
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
        yield event.chain_result(
            self.formatPostAsMessageChain(post, event.get_sender_id())
        )

    @filter.command_group("rating", desc="分级相关指令")
    def rating(self):
        pass

    @rating.command("list", desc="列出所有分级")
    async def listRating(self, event: AstrMessageEvent):
        yield event.plain_result(
            ",\n".join(
                map(
                    lambda key: f"[{key.upper()}]{self.RATING_LEVEL[key][1:]}",
                    self.RATING_LEVEL,
                )
            )
            + "\n\nall: 允许所有分级"
        )

    @rating.command("set", desc="设置当前分级")
    async def setRating(
        self,
        event: AstrMessageEvent,
        newRating: str = "all",
    ):
        if newRating in ["s", "q", "e", "all"]:
            self.currentRating = newRating
            if newRating == "all":
                yield event.plain_result("已取消分级限制。")
            else:
                yield event.plain_result(
                    f"分级已设置为：{self.RATING_LEVEL[self.currentRating]}"
                )
        else:
            yield event.plain_result("无效分级标签。")

    @rating.command("get", desc="查看当前分级")
    def lookRating(self, event: AstrMessageEvent):
        if self.currentRating == "all":
            yield event.plain_result("当前无分级限制。")
        else:
            yield event.plain_result(
                f"当前分级为：{self.RATING_LEVEL[self.currentRating]}"
            )

    @filter.llm_tool("search_random_image")
    async def getRandomImage(self, event: AstrMessageEvent, tags: list[str]):
        """搜索或获取随机图

        Args:
            tags(array[string]): The label content of the random graph must consist of all-English keywords. If it is a character name, use the official translation.
        """
        tagsProcessed = self.processTags(
            "+".join(map(lambda x: x.replace(" ", "_"), tags))
        )
        post = await self.getPost(tagsProcessed)
        await event.send(
            MessageChain(chain=[Comp.Plain(f"正在使用标签搜索随机图：{tagsProcessed}")])
        )
        if post:
            await event.send(
                MessageChain(
                    chain=self.formatPostAsMessageChain(post, event.get_sender_id())
                )
            )
            return f"帖子数据：{post}。"
        else:
            return "没有任何帖子符合你所给的标签。"

    @filter.command_group("constants", desc="恒标签相关指令")
    async def constants(self):
        pass

    @constants.command("add", alias={"+"}, desc="添加恒标签")
    async def addConstants(self, event: AstrMessageEvent, tag: str):
        if self.userConstantTags.count(tag) > 0:
            yield event.plain_result("这个恒标签已存在。")
        else:
            self.userConstantTags.append(tag)
            yield event.plain_result("恒标签添加成功！")

    @constants.command("delete", alias={"-"}, desc="删除恒标签")
    async def deleteConstants(self, event: AstrMessageEvent, tag: str):
        if self.userConstantTags.count(tag) == 0:
            yield event.plain_result("这个恒标签根本不存在。")
        else:
            self.userConstantTags.remove(tag)
            yield event.plain_result("恒标签删除成功！")

    @constants.command("replace", alias={"="}, desc="替换恒标签（删除+添加）")
    async def replaceConstants(self, event: AstrMessageEvent, oldTag: str, newTag: str):
        if self.userConstantTags.count(oldTag) == 0:
            yield event.plain_result(f"目标恒标签{oldTag}根本不存在。")
            return
        if self.userConstantTags.count(newTag) > 0:
            yield event.plain_result(f"新的恒标签{newTag}已存在。")
            return
        index = self.userConstantTags.index(oldTag)
        self.userConstantTags.remove(oldTag)
        self.userConstantTags.insert(index, newTag)
        yield event.plain_result(f"替换成功：{oldTag}->{newTag}")

    @constants.command("get", alias={"?"}, desc="查看当前恒标签列表")
    async def getConstants(self, event: AstrMessageEvent):
        result = ",".join(self.userConstantTags)
        yield event.plain_result(result if result else "当前没有任何恒标签。")

    async def getPost(self, tags: str) -> dict | None:
        url = self.getApiUrl(tags)
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

    def processTags(self, origin: str):
        return "+".join(
            map(
                lambda x: x.replace(" ", "%20"),
                origin.split(",")
                + self.CONSTANT_TAGS
                + (
                    []
                    if self.currentRating == "all"
                    else [f"rating:{self.currentRating}"]
                )
                + self.userConstantTags,
            )
        ).strip("+")

    def getApiUrl(self, tags: str):
        return f"https://e621.net/posts/random.json?tags={tags}"

    def formatPostAsMessageChain(self, post: dict, senderID: str):
        return [
            Comp.Image.fromURL(post["file_url"]),
            Comp.Plain(
                f"#{post['id']} [❤️{post['score']} ⭐{post['fav_count']} 📻{post['comment_count']}]（{self.RATING_LEVEL[post['rating']]}）\n\n{post['description']}"
            ),
        ]

    async def terminate(self):
        await self.client.aclose()
