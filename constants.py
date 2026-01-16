from astrbot.api.star import StarTools

RATING_LEVEL: dict[str, str] = {
    "s": "Safe",
    "q": "Questionable",
    "e": "Explicit",
}
PLUGIN_DATA_PATH = StarTools.get_data_dir("astrbot_plugin_e621_finder")
INITIAL_GROUP_DATA = {
    "rating": "s",
    "constants": ["male"],
}
