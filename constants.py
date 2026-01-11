import os

from astrbot.core.utils.astrbot_path import get_astrbot_data_path

RATING_LEVEL: dict[str, str] = {
    "s": "Safe",
    "q": "Questionable",
    "e": "Explicit",
}
PLUGIN_DATA_PATH = os.path.join(get_astrbot_data_path(), "plugin_data", "e621_finder")
INITIAL_GROUP_DATA = {
    "rating": "s",
    "constants": ["male"],
}
