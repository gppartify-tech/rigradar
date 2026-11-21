"""A small robots.txt parser that follows RFC 9309 (the Google-style rules).

Why not urllib.robotparser? It only does prefix matching and ignores the `*`
and `$` wildcards, but the stores we scrape use them (e.g. `Disallow: */search?*`).

Rules:
* Pick the group(s) whose User-agent matches our bot name; otherwise the `*` group(s).
  Several matching groups are merged.
* A rule matches when its pattern matches the start of "path?query".
  `*` matches any characters, a trailing `$` anchors the end.
* The longest matching pattern wins; on a tie, Allow wins.
* No matching rule -> allowed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow?, pattern)


def _pattern_to_regex(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern)
    return re.compile(regex + ("$" if anchored else ""))


class RobotsRules:
    def __init__(self, text: str):
        self.groups: list[_Group] = []
        current: _Group | None = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = _Group()
                    self.groups.append(current)
                current.agents.append(value.lower())
                last_was_agent = True
            elif key in ("allow", "disallow"):
                last_was_agent = False
                if current is None:
                    continue
                if key == "disallow" and value == "":
                    continue  # "Disallow:" with no path allows everything
                current.rules.append((key == "allow", value))
            else:
                last_was_agent = False  # Sitemap:, Crawl-delay:, Content-Signal: ...

    def _rules_for(self, bot_name: str) -> list[tuple[bool, str]]:
        bot = bot_name.lower()
        named = [g for g in self.groups if any(a != "*" and a in bot for a in g.agents)]
        chosen = named or [g for g in self.groups if "*" in g.agents]
        return [rule for g in chosen for rule in g.rules]

    def can_fetch(self, bot_name: str, url: str) -> bool:
        parts = urlsplit(url)
        target = parts.path or "/"
        if parts.query:
            target += "?" + parts.query
        candidates = {target, unquote(target)}

        best_len, best_allow = -1, True
        for allow, pattern in self._rules_for(bot_name):
            regex = _pattern_to_regex(pattern)
            if any(regex.match(t) for t in candidates):
                length = len(pattern)
                if length > best_len or (length == best_len and allow):
                    best_len, best_allow = length, allow
        return best_allow


ALLOW_ALL = RobotsRules("")
