"""Normalise the English token 'Website' on Brazilian pages to 'Site'."""
import re

ORDER = 11
TITLE = "Use Brazilian Portuguese 'Site' instead of 'Website' on /pt-br/ pages"
SELECT = r"^/pt-br/"


def apply(path, src, ctx):
    return re.sub(r"(?<![\w>])Website(?![\w<])", "Site", src)
