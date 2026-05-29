"""WakaReadme : WakaTime progress visualizer.

Wakatime Metrics on your Profile Readme.

Title:

```txt
From: 15 February, 2022 - To: 22 February, 2022
````

Byline:

```txt
Total: 34 hrs 43 mins
```

Body:

```txt
Python     27 hrs 29 mins  ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣀⣀⣀⣀⣀   77.83 %
YAML       2 hrs 14 mins   ⣿⣦⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀   06.33 %
Markdown   1 hr 54 mins    ⣿⣤⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀   05.39 %
TOML       1 hr 48 mins    ⣿⣤⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀   05.11 %
Other      35 mins         ⣦⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀   01.68 %
```

Contents := Title + Byline + Body
"""

# standard
from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import logging as logger
import math
import os
from random import SystemRandom
import re
import sys
from time import sleep
from typing import Any

# external
from faker import Faker
from github import (
    ContentFile,
    Github,
    GithubException,
    InputGitAuthor,
    InputGitTreeElement,
    Repository,
)
from requests import get as rq_get
from requests.exceptions import RequestException

################### setup ###################


print()
# hush existing loggers
for lgr_name in logger.root.manager.loggerDict:
    # to disable log propagation completely set '.propagate = False'
    logger.getLogger(lgr_name).setLevel(logger.WARNING)
# somehow github.Requester gets missed out from loggerDict
logger.getLogger("github.Requester").setLevel(logger.WARNING)
# configure logger
logger.basicConfig(
    datefmt="%Y-%m-%d %H:%M:%S",
    format="[%(asctime)s] ln. %(lineno)-3d %(levelname)-8s %(message)s",
    level=logger.DEBUG,
)
try:
    if len(sys.argv) == 2 and sys.argv[1] == "--dev":
        # get env-vars from .env file for development
        from dotenv import load_dotenv

        # comment this out to disable colored logging
        from loguru import logger

        # load from .env before class def gets parsed
        load_dotenv()
except ImportError as im_err:
    logger.warning(im_err)


################### lib-func ###################


def strtobool(val: str | bool):
    """Strtobool.

    PEP 632 https://www.python.org/dev/peps/pep-0632/ is depreciating distutils.
    This is from the official source code with slight modifications.

    Converts a string representation of truth to `True` or `False`.

    Args:
        val:
            Value to be converted to bool.

    Returns:
        (Literal[True]):
            If `val` is any of 'y', 'yes', 't', 'true', 'on', or '1'.
        (Literal[False]):
            If `val` is any of 'n', 'no', 'f', 'false', 'off', and '0'.

    Raises:
        ValueError: If `val` is anything else.
    """
    if isinstance(val, bool):
        return val

    val = val.lower()

    if val in {"y", "yes", "t", "true", "on", "1"}:
        return True

    if val in {"n", "no", "f", "false", "off", "0"}:
        return False

    raise ValueError(f"invalid truth value for {val}")


################### data ###################


@dataclass(slots=True)
class WakaInput:
    """WakaReadme Input Env Variables."""

    # constants
    prefix_length: int = 16
    graph_length: int = 25

    # mapped environment variables
    # # required
    gh_token: str | None = os.getenv("INPUT_GH_TOKEN")
    waka_key: str | None = os.getenv("INPUT_WAKATIME_API_KEY")
    api_base_url: str | None = os.getenv("INPUT_API_BASE_URL", "https://wakatime.com/api")
    repository: str | None = os.getenv("INPUT_REPOSITORY")
    # # depends
    commit_message: str = os.getenv(
        "INPUT_COMMIT_MESSAGE", "Updated WakaReadme graph with new metrics"
    )
    _section_name: str = os.getenv("INPUT_SECTION_NAME", "waka")
    start_comment: str = f"<!--START_SECTION:{_section_name}-->"
    end_comment: str = f"<!--END_SECTION:{_section_name}-->"
    waka_block_pattern: str = f"{start_comment}[\\s\\S]+{end_comment}"
    # # optional
    show_title: str | bool = os.getenv("INPUT_SHOW_TITLE") or False
    graph_style: str = os.getenv("INPUT_GRAPH_STYLE", "mermaid")
    theme: str = os.getenv("INPUT_THEME", "terracotta")
    svg_path: str = os.getenv("INPUT_SVG_PATH", "assets/waka-readme.svg")
    time_range: str = os.getenv("INPUT_TIME_RANGE", "last_7_days")
    show_total_time: str | bool = os.getenv("INPUT_SHOW_TOTAL") or False
    language_count: str | int = os.getenv("INPUT_LANG_COUNT") or 5
    # # optional meta
    target_branch: str = os.getenv("INPUT_TARGET_BRANCH", "NOT_SET")
    target_path: str = os.getenv("INPUT_TARGET_PATH", "NOT_SET")
    committer_name: str = os.getenv("INPUT_COMMITTER_NAME", "NOT_SET")
    committer_email: str = os.getenv("INPUT_COMMITTER_EMAIL", "NOT_SET")
    author_name: str = os.getenv("INPUT_AUTHOR_NAME", "NOT_SET")
    author_email: str = os.getenv("INPUT_AUTHOR_EMAIL", "NOT_SET")

    def validate_input(self):
        """Validate Input Env Variables."""
        logger.debug("Validating input variables")
        if not self.gh_token or not self.waka_key or not self.api_base_url or not self.repository:
            logger.error("Invalid inputs")
            logger.info("Refer https://github.com/athul/waka-readme")
            return False

        if len(self.commit_message) < 1:
            logger.error("Commit message length must be greater than 1 character long")
            return False

        try:
            self.show_title = strtobool(self.show_title)
            self.show_total_time = strtobool(self.show_total_time)
        except (ValueError, AttributeError) as err:
            logger.error(err)
            return False

        if not self._section_name.isalnum():
            logger.warning("Section name must be in any of [[a-z][A-Z][0-9]]")
            logger.debug("Using default section name: waka")
            self._section_name = "waka"
            self.start_comment = f"<!--START_SECTION:{self._section_name}-->"
            self.end_comment = f"<!--END_SECTION:{self._section_name}-->"
            self.waka_block_pattern = f"{self.start_comment}[\\s\\S]+{self.end_comment}"

        self.graph_style = self.graph_style.strip().lower()
        if self.graph_style != "mermaid" and self.graph_style not in _PATTERNS:
            logger.warning("Invalid graph style")
            logger.debug("Using default graph style: mermaid")
            self.graph_style = "mermaid"

        self.theme = self.theme.strip().lower()
        if self.theme not in _THEMES:
            logger.warning("Invalid theme")
            logger.debug("Using default theme: terracotta")
            self.theme = "terracotta"

        if not self.svg_path.strip():
            self.svg_path = "assets/waka-readme.svg"

        if self.time_range not in {
            "last_7_days",
            "last_30_days",
            "last_6_months",
            "last_year",
            "all_time",
        }:  # "all_time" is un-documented, should it be used?
            logger.warning("Invalid time range")
            logger.debug("Using default time range: last_7_days")
            self.time_range = "last_7_days"

        try:
            self.language_count = int(self.language_count)
            if self.language_count < -1:
                raise ValueError
        except ValueError:
            logger.warning("Invalid language count")
            logger.debug("Using default language count: 5")
            self.language_count = 5

        for option in (
            "target_branch",
            "target_path",
            "committer_name",
            "committer_email",
            "author_name",
            "author_email",
        ):
            if not getattr(self, option):
                logger.warning(f"Improper '{option}' configuration")
                logger.debug(f"Using default '{option}'")
                setattr(self, option, "NOT_SET")

        logger.debug("Input validation complete\n")
        return True


################### logic ###################


def generate_mermaid_pie_chart(stats, language_count):
    """Convert WakaTime stats to Mermaid pie chart."""
    chart_data = "pie\n"
    total_seconds = sum(lang.get("total_seconds", 0) for lang in stats.get("languages", []))

    top_languages = sorted(
        stats.get("languages", []), key=lambda x: x.get("total_seconds", 0), reverse=True
    )[:language_count]

    for lang in top_languages:
        lang_name = lang.get("name")
        lang_percentage = (lang.get("total_seconds", 0) / total_seconds) * 100
        chart_data += f'    "{lang_name}" : {lang_percentage:.1f}\n'

    return f"```mermaid\n{chart_data}```"


# color themes mirroring the ones used across the readme and personal-website
_THEMES = {
    "terracotta": {
        "bg": "#f0e0c8",
        "line": "#2a1810",
        "text": "#1e1108",
        "ramp": (
            "#b87040",
            "#7a4a2a",
            "#d89868",
            "#9a5a3a",
            "#c4a488",
            "#e0a878",
            "#5c3a22",
            "#cfa978",
        ),
    },
    "sumi": {
        "bg": "#e8e2d4",
        "line": "#2a2620",
        "text": "#1c1a17",
        "ramp": ("#3a3228", "#6b5c48", "#8a7e6a", "#5a5040", "#9a8c74", "#4a4030"),
    },
    "matcha": {
        "bg": "#e6ecd6",
        "line": "#2a3018",
        "text": "#2a3018",
        "ramp": ("#4a5a38", "#354028", "#7a8a68", "#5c7040", "#8a9878", "#425030"),
    },
    "washi": {
        "bg": "#f5efe5",
        "line": "#2a1810",
        "text": "#2a1810",
        "ramp": ("#8b7860", "#c0b098", "#a89878", "#6e5c44", "#b0a088", "#9a8868"),
    },
    "ai": {
        "bg": "#dce8f0",
        "line": "#13293a",
        "text": "#1b3a4b",
        "ramp": ("#2a5a72", "#1b3a4b", "#4a7a94", "#234d63", "#6a9ab0", "#3a6a84"),
    },
    "sakura": {
        "bg": "#f7ecec",
        "line": "#2e1a1a",
        "text": "#2e1a1a",
        "ramp": ("#c07a7a", "#8a5a5a", "#d6a0a0", "#a87878", "#b88a8a", "#9a6a6a"),
    },
}


def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(channel))):02x}" for channel in rgb)


def _mix(color_a: str, color_b: str, ratio: float):
    first, second = _hex_to_rgb(color_a), _hex_to_rgb(color_b)
    return _rgb_to_hex(tuple(first[i] + (second[i] - first[i]) * ratio for i in range(3)))


def _luminance(color: str):
    red, green, blue = _hex_to_rgb(color)
    return 0.299 * red + 0.587 * green + 0.114 * blue


def _ramp(anchors: tuple[str, ...], count: int):
    if count <= len(anchors):
        return list(anchors[:count])
    ramp = list(anchors)
    while len(ramp) < count:
        index = len(ramp)
        ramp.append(_mix(anchors[index % len(anchors)], anchors[(index + 1) % len(anchors)], 0.5))
    return ramp


def _stroke_for(base: str, theme: dict[str, object]):
    # light outline over dark fills, dark outline over light fills
    if _luminance(base) < 115:
        return _mix(base, str(theme["bg"]), 0.6)
    return _mix(base, str(theme["line"]), 0.42)


def _xml_escape(text: str):
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _pattern_seigaiha(width: float, height: float, scale: float):
    radii = (scale, scale * 2 / 3, scale / 3)
    arcs = []
    row, y = 0, 0.0
    while y <= height + scale:
        offset = scale if row % 2 else 0
        x = -scale + offset
        while x <= width + scale:
            for r in radii:
                arcs.append(f"M{x - r:.1f},{y:.1f} A{r:.1f},{r:.1f} 0 0 0 {x + r:.1f},{y:.1f}")
            x += 2 * scale
        row += 1
        y += scale
    return f'<path d="{" ".join(arcs)}"/>'


def _pattern_shippo(width: float, height: float, scale: float):
    circles = []
    y = 0.0
    while y <= height + scale:
        x = 0.0
        while x <= width + scale:
            circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{scale:.1f}"/>')
            x += scale
        y += scale
    return "".join(circles)


def _pattern_kikko(width: float, height: float, scale: float):
    cells = []
    hex_w = math.sqrt(3) * scale
    row, cy = 0, 0.0
    while cy <= height + scale:
        cx = hex_w / 2 if row % 2 else 0.0
        while cx <= width + hex_w:
            points = [
                (
                    cx + scale * math.cos(math.radians(90 + 60 * k)),
                    cy + scale * math.sin(math.radians(90 + 60 * k)),
                )
                for k in range(6)
            ]
            corners = " L".join(f"{px:.1f},{py:.1f}" for px, py in points)
            cells.append(f'<path d="M{corners} Z"/>')
            cx += hex_w
        row += 1
        cy += 1.5 * scale
    return "".join(cells)


def _pattern_yabane(width: float, height: float, scale: float):
    feathers = []
    half = scale / 2
    x = 0.0
    while x <= width + scale:
        y = -scale
        while y <= height + scale:
            feathers.append(
                f'<path d="M{x:.1f},{y:.1f} L{x + half:.1f},{y + half:.1f} '
                f'L{x + scale:.1f},{y:.1f}"/>'
            )
            feathers.append(
                f'<path d="M{x:.1f},{y + half:.1f} L{x + half:.1f},{y + scale:.1f} '
                f'L{x + scale:.1f},{y + half:.1f}"/>'
            )
            y += scale
        x += scale
    return "".join(feathers)


def _pattern_asanoha(width: float, height: float, scale: float):
    delta_y = scale * math.sqrt(3) / 2
    lines = []

    def offset(j: int):
        return scale / 2 if j % 2 else 0.0

    def midpoint(p: tuple[float, float], q: tuple[float, float]):
        return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)

    def add_medians(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]):
        for vertex, opposite in ((a, midpoint(b, c)), (b, midpoint(a, c)), (c, midpoint(a, b))):
            lines.append(f"M{vertex[0]:.1f},{vertex[1]:.1f} L{opposite[0]:.1f},{opposite[1]:.1f}")

    rows = int(height / delta_y) + 2
    cols = int(width / scale) + 2
    for j in range(-1, rows):
        low, high = offset(j), offset(j + 1)
        for i in range(-1, cols):
            add_medians(
                (i * scale + low, j * delta_y),
                ((i + 1) * scale + low, j * delta_y),
                ((i + 0.5) * scale + low, (j + 1) * delta_y),
            )
            add_medians(
                (i * scale + high, (j + 1) * delta_y),
                ((i + 1) * scale + high, (j + 1) * delta_y),
                ((i + 0.5) * scale + high, j * delta_y),
            )
    return f'<path d="{" ".join(lines)}"/>'


_PATTERNS = {
    "seigaiha": (_pattern_seigaiha, 19),
    "shippo": (_pattern_shippo, 22),
    "kikko": (_pattern_kikko, 18),
    "yabane": (_pattern_yabane, 26),
    "asanoha": (_pattern_asanoha, 30),
}


def generate_graph_svg(
    stats: dict[str, Any],
    language_count: int,
    pattern: str = "seigaiha",
    theme: str = "terracotta",
    width: int = 820,
):
    """Convert WakaTime stats to a wagara-patterned SVG band."""
    palette = _THEMES.get(theme, _THEMES["terracotta"])
    pattern_fn, scale = _PATTERNS.get(pattern, _PATTERNS["seigaiha"])

    total_seconds = sum(lang.get("total_seconds", 0) for lang in stats.get("languages", []))
    top_languages = sorted(
        stats.get("languages", []), key=lambda lang: lang.get("total_seconds", 0), reverse=True
    )[:language_count]
    languages: list[tuple[str, float]] = []
    for lang in top_languages:
        percent = (lang.get("total_seconds", 0) / total_seconds * 100) if total_seconds else 0.0
        languages.append((str(lang.get("name")), percent))
    if not languages:
        languages = [("No activity", 0.0)]

    pad, seg_gap, legend_w, divider_gap, row_h = 20, 3, 184, 24, 26
    count = len(languages)
    band_h = max(124, count * row_h)
    height = pad * 2 + band_h
    graph_w = width - pad * 2 - legend_w - divider_gap * 2 - 1
    total = sum(percent for _, percent in languages) or 1
    colors = _ramp(palette["ramp"], count)

    defs, segments, legend = ["<defs>"], [], []
    x = float(pad)
    for index, (name, percent) in enumerate(languages):
        seg_w = max(1.0, graph_w * percent / total - seg_gap)
        base = colors[index]
        stroke = _stroke_for(base, palette)
        clip = f"wk-seg-{index}"
        defs.append(
            f'<clipPath id="{clip}"><rect x="{x:.2f}" y="{pad}" '
            f'width="{seg_w:.2f}" height="{band_h}" rx="6"/></clipPath>'
        )
        texture = pattern_fn(seg_w + 44, band_h, scale)
        segments.append(
            f'<g clip-path="url(#{clip})"><g transform="translate({x:.2f},{pad})">'
            f'<rect width="{seg_w:.2f}" height="{band_h}" fill="{base}"/>'
            f'<g fill="none" stroke="{stroke}" stroke-width="1.6" opacity="0.6">'
            f"{texture}</g></g></g>"
        )
        x += seg_w + seg_gap

    div_x = pad + graph_w + divider_gap
    divider = (
        f'<line x1="{div_x:.2f}" y1="{pad + 6}" x2="{div_x:.2f}" y2="{height - pad - 6}" '
        f'stroke="{palette["line"]}" stroke-width="1" opacity="0.3"/>'
    )

    legend_x = div_x + divider_gap
    legend_top = pad + (band_h - count * row_h) / 2
    for index, (name, percent) in enumerate(languages):
        center_y = legend_top + index * row_h + row_h / 2
        legend.append(
            f'<rect x="{legend_x:.2f}" y="{center_y - 6:.2f}" width="12" height="12" rx="3" '
            f'fill="{colors[index]}"/>'
            f'<text x="{legend_x + 20:.2f}" y="{center_y + 4:.2f}" fill="{palette["text"]}" '
            f'font-size="13" font-weight="600">{_xml_escape(name)}</text>'
            f'<text x="{width - pad:.2f}" y="{center_y + 4:.2f}" fill="{palette["line"]}" '
            f'font-size="12" text-anchor="end" opacity="0.7">{percent:.1f}%</text>'
        )

    defs.append("</defs>")
    body = "".join(defs + segments + [divider] + legend)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'font-family="Segoe UI, Helvetica, Arial, sans-serif">'
        f'<rect width="{width}" height="{height}" rx="10" fill="{palette["bg"]}"/>'
        f"{body}</svg>"
    )


def make_title(dawn: str | None, dusk: str | None, /):
    """WakaReadme Title.

    Makes title for WakaReadme.
    """
    logger.debug("Making title")
    if not dawn or not dusk:
        logger.error("Cannot find start/end date\n")
        sys.exit(1)
    api_dfm, msg_dfm = "%Y-%m-%dT%H:%M:%SZ", "%d %B %Y"
    try:
        start_date = datetime.strptime(dawn, api_dfm).strftime(msg_dfm)
        end_date = datetime.strptime(dusk, api_dfm).strftime(msg_dfm)
    except ValueError as err:
        logger.error(f"{err}\n")
        sys.exit(1)

    logger.debug("Title was made\n")
    return f"From: {start_date} - To: {end_date}"


def prep_content(stats: dict[str, Any], /):
    """WakaReadme Prep Content.

    Prepares markdown content from WakaTime stats.
    """
    logger.debug("Making contents")
    contents = ""

    if wk_i.show_title:
        contents += make_title(stats.get("start"), stats.get("end")) + "\n\n"
    if wk_i.show_total_time:
        total_time = stats.get("human_readable_total")
        contents += f"Total Time: {total_time}\n\n"

    if wk_i.graph_style in _PATTERNS:
        contents += f'<img src="{wk_i.svg_path}" alt="WakaTime stats" />'
    else:
        contents += generate_mermaid_pie_chart(stats, wk_i.language_count)

    return contents.rstrip("\n")


def fetch_stats():
    """WakaReadme Fetch Stats.

    Returns statistics as JSON string.
    """
    attempts = 6
    statistic: dict[str, dict[str, Any]] = {}
    encoded_key = str(b64encode(bytes(str(wk_i.waka_key), "utf-8")), "utf-8")
    logger.debug(f"Pulling WakaTime stats from {' '.join(wk_i.time_range.split('_'))}")
    for attempt in range(1, attempts + 1):
        resp_message, fake_ua = "", cryptogenic.choice([str(fake.user_agent()) for _ in range(5)])
        # making a request
        if (
            resp := rq_get(
                url=f"{str(wk_i.api_base_url).rstrip('/')}/v1/users/current/stats/{wk_i.time_range}",
                headers={
                    "Authorization": f"Basic {encoded_key}",
                    "User-Agent": fake_ua,
                },
                timeout=(30.0 * attempt),
            )
        ).status_code != 200:
            resp_message += f" • {conn_info}" if (conn_info := resp.json().get("message")) else ""
        logger.debug(
            f"API response #{attempt}: {resp.status_code} •" + f" {resp.reason}{resp_message}"
        )
        if resp.status_code == 200 and (statistic := resp.json()):
            logger.debug("Fetched WakaTime statistics")
            break
        if attempt < attempts:
            logger.debug(f"Retrying in {30 * attempt}s ...")
            sleep(30 * attempt)

    if err := (statistic.get("error") or statistic.get("errors")):
        logger.error(f"{err}\n")
        sys.exit(1)

    print()
    return statistic.get("data")


def churn(old_readme: str, /) -> tuple[str | None, str | None]:
    """WakaReadme Churn.

    Composes WakaTime stats into the readme, returning the new readme and,
    for the seigaiha style, the SVG to commit alongside it.
    """
    # check if placeholder pattern exists in readme
    if not re.findall(wk_i.waka_block_pattern, old_readme):
        logger.warning(f"Cannot find `{wk_i.waka_block_pattern}` pattern in readme")
        return None, None
    # getting contents
    if not (waka_stats := fetch_stats()):
        logger.error("Unable to fetch data, please rerun workflow\n")
        sys.exit(1)
    # preparing contents
    try:
        svg_content = (
            generate_graph_svg(waka_stats, wk_i.language_count, wk_i.graph_style, wk_i.theme)
            if wk_i.graph_style in _PATTERNS
            else None
        )
        generated_content = prep_content(waka_stats)
    except (AttributeError, KeyError, ValueError) as err:
        logger.error(f"Unable to read API data | {err}\n")
        sys.exit(1)
    print(generated_content, "\n", sep="")
    # substituting old contents
    new_readme = re.sub(
        pattern=wk_i.waka_block_pattern,
        repl=f"{wk_i.start_comment}\n\n{generated_content}\n\n{wk_i.end_comment}",
        string=old_readme,
    )
    if len(sys.argv) == 2 and sys.argv[1] == "--dev":
        logger.debug("Detected run in `dev` mode.")
        # to avoid accidentally writing back to Github
        # when developing or testing waka-readme
        return None, None

    return new_readme, svg_content


def qualify_target(gh_repo: Repository.Repository):
    """Qualify target repository defaults."""

    @dataclass
    class TargetRepository:
        this: ContentFile.ContentFile
        path: str
        commit_message: str
        sha: str
        branch: str
        committer: InputGitAuthor | None
        author: InputGitAuthor | None

    gh_branch = gh_repo.default_branch
    if wk_i.target_branch != "NOT_SET":
        gh_branch = gh_repo.get_branch(wk_i.target_branch)

    target = gh_repo.get_readme()
    if wk_i.target_path != "NOT_SET":
        target = gh_repo.get_contents(
            path=wk_i.target_path,
            ref=gh_branch if isinstance(gh_branch, str) else gh_branch.commit.sha,
        )

    if isinstance(target, list):
        raise RuntimeError("Cannot handle multiple files.")

    committer, author = None, None
    if wk_i.committer_name != "NOT_SET" and wk_i.committer_email != "NOT_SET":
        committer = InputGitAuthor(name=wk_i.committer_name, email=wk_i.committer_email)
    if wk_i.author_name != "NOT_SET" and wk_i.author_email != "NOT_SET":
        author = InputGitAuthor(name=wk_i.author_name, email=wk_i.author_email)

    return TargetRepository(
        this=target,
        path=target.path,
        commit_message=wk_i.commit_message,
        sha=target.sha,
        branch=gh_branch if isinstance(gh_branch, str) else gh_branch.name,
        committer=committer,
        author=author,
    )


def _commit_files(gh_repo: Repository.Repository, target, files: dict[str, str]):
    """Commit multiple files to the target branch as a single commit."""
    ref = gh_repo.get_git_ref(f"heads/{target.branch}")
    base_commit = gh_repo.get_git_commit(ref.object.sha)
    elements = [
        InputGitTreeElement(path=path, mode="100644", type="blob", content=content)
        for path, content in files.items()
    ]
    new_tree = gh_repo.create_git_tree(elements, base_commit.tree)
    extra: dict[str, InputGitAuthor] = {}
    if target.committer:
        extra["committer"] = target.committer
    if target.author:
        extra["author"] = target.author
    new_commit = gh_repo.create_git_commit(
        message=target.commit_message, tree=new_tree, parents=[base_commit], **extra
    )
    ref.edit(new_commit.sha)


def _current_svg(gh_repo: Repository.Repository, branch: str):
    """Return the SVG currently stored at the configured path, if any."""
    try:
        existing = gh_repo.get_contents(wk_i.svg_path, ref=branch)
    except GithubException:
        return None
    if isinstance(existing, list):
        return None
    return str(existing.decoded_content, encoding="utf-8")


def genesis():
    """Run Program."""
    logger.debug("Connecting to GitHub")
    gh_connect = Github(wk_i.gh_token)
    # since a validator is being used earlier, casting
    # `wk_i.ENV_VARIABLE` to a string here, is okay
    gh_repo = gh_connect.get_repo(str(wk_i.repository))
    target = qualify_target(gh_repo)
    logger.debug("Decoding readme contents\n")

    readme_contents = str(target.this.decoded_content, encoding="utf-8")
    new_readme, svg_content = churn(readme_contents)
    if new_readme is None:
        logger.info("WakaReadme was not updated")
        return

    # seigaiha style: the readme only holds a static <img>, so the change is in
    # the SVG file; commit the readme (if first run) and the SVG atomically.
    if svg_content is not None:
        readme_changed = new_readme != readme_contents
        svg_changed = svg_content != _current_svg(gh_repo, target.branch)
        if not readme_changed and not svg_changed:
            logger.info("WakaReadme was not updated")
            return
        files = {wk_i.svg_path: svg_content}
        if readme_changed:
            files[target.path] = new_readme
        logger.debug("WakaReadme stats has changed")
        _commit_files(gh_repo, target, files)
        logger.info("Stats updated successfully")
        return

    if new_readme == readme_contents:
        logger.info("WakaReadme was not updated")
        return

    logger.debug("WakaReadme stats has changed")
    update_metric = partial(
        gh_repo.update_file,
        path=target.path,
        message=target.commit_message,
        content=new_readme,
        sha=target.sha,
        branch=target.branch,
    )
    if target.committer:
        update_metric = partial(update_metric, committer=target.committer)
    if target.author:
        update_metric = partial(update_metric, author=target.author)
    update_metric()
    logger.info("Stats updated successfully")


################### driver ###################


if __name__ == "__main__":
    # faker data preparation
    fake = Faker()
    Faker.seed(0)
    cryptogenic = SystemRandom()

    # initial waka-readme setup
    logger.debug("Initialize WakaReadme")
    wk_i = WakaInput()
    if not wk_i.validate_input():
        logger.error("Environment variables are misconfigured\n")
        sys.exit(1)

    # run
    try:
        genesis()
    except KeyboardInterrupt:
        print("\r", end=" ")
        logger.error("Interrupt signal received\n")
        sys.exit(1)
    except RuntimeError as err:
        logger.error(f"{type(err).__name__}: {err}\n")
        sys.exit(1)
    except (GithubException, RequestException) as rq_exp:
        logger.critical(f"{rq_exp}\n")
        sys.exit(1)
    print("\nThanks for using WakaReadme!\n")
