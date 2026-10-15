"""The games that draw full side by side themselves, from the list the wiz3D project keeps online

The wiz3D README lists the games it leaves alone because they output side by side by themselves
("Excluded (Native SBS/TAB)"). The list is fetched now and then and kept in the cache folder; without
a network the last copy is used, and without a copy no game is on the list."""

import json
import os
import re
import time
from typing import Set

from lutris import settings
from lutris.util import system
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger

LIST_URL = "https://raw.githubusercontent.com/effcol/wiz3D/main/README.md"
CACHE_PATH = os.path.join(settings.CACHE_DIR, "wiz3d-native-stereo.json")
MAX_AGE = 7 * 24 * 3600
TIMEOUT = 5

# Whether a game's checkbox is filled in from the list when the game is first run
PREFILL_NATIVE_STEREO = False


def parse_list(readme: str) -> Set[str]:
    """The game names (lower case) of the "Excluded (Native SBS/TAB)" lines of the wiz3D README"""
    names = set()
    for line in readme.splitlines():
        if "Excluded (Native SBS/TAB)" in line and ":**" in line:
            names.update(name.strip().lower() for name in re.findall(r"\*([^*]+)\*", line.split(":**", 1)[1]))
    return names


def get_native_stereo_games() -> Set[str]:
    """The names (lower case) of the games on the list"""
    cached = []
    if system.path_exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as cache_file:
                cached = json.load(cache_file)
        except (OSError, ValueError):
            logger.warning("Invalid cache file %s", CACHE_PATH)
        if cached and time.time() - os.path.getmtime(CACHE_PATH) < MAX_AGE:
            return set(cached)
    try:
        names = parse_list(Request(LIST_URL, timeout=TIMEOUT).get().text)
    except (HTTPError, OSError) as ex:
        logger.warning("Could not read the list of games that output stereo themselves: %s", ex)
        return set(cached)
    if names:
        with open(CACHE_PATH, "w", encoding="utf-8") as cache_file:
            json.dump(sorted(names), cache_file)
    return names or set(cached)


def is_native_stereo_game(name: str) -> bool:
    """True if the game is on the list"""
    return name.strip().lower() in get_native_stereo_games()
