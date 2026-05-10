from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_BLOCKED_REGEX_TOKENS = ("(?=", "(?!", "(?<=", "(?<!", "\\1", "\\2", "\\3", "\\k", "(?P")
_NESTED_QUANTIFIER = re.compile(r"\([^)]*[+*][^)]*\)[+*{]")


def _clean_list(values: Any, *, limit: int = 30, max_len: int = 160) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = " ".join(str(item or "").strip().split())
        key = value.casefold()
        if not value or len(value) > max_len or key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _safe_pattern(pattern: str) -> bool:
    if len(pattern) > 200:
        return False
    if any(token in pattern for token in _BLOCKED_REGEX_TOKENS):
        return False
    if _NESTED_QUANTIFIER.search(pattern):
        return False
    return True


@dataclass(frozen=True)
class ProjectOntologyRule:
    id: str
    label: str
    target_kind: str
    target_key: str
    match_mode: str = "ANY"
    phrases: tuple[str, ...] = field(default_factory=tuple)
    patterns: tuple[str, ...] = field(default_factory=tuple)
    negative_phrases: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = True
    weight: int = 1

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectOntologyRule | None":
        if not isinstance(payload, dict):
            return None
        target_kind = str(payload.get("target_kind") or "").strip().upper()
        if target_kind not in {"ASPECT", "ISSUE", "TOPIC"}:
            return None
        target_key = str(payload.get("target_key") or "").strip()
        label = str(payload.get("label") or target_key).strip()
        if not target_key or not label:
            return None
        phrases = tuple(_clean_list(payload.get("phrases"), limit=30, max_len=120))
        negative_phrases = tuple(_clean_list(payload.get("negative_phrases"), limit=30, max_len=120))
        raw_patterns = _clean_list(payload.get("patterns"), limit=10, max_len=200)
        patterns: list[str] = []
        for pattern in raw_patterns:
            if not _safe_pattern(pattern):
                continue
            try:
                re.compile(pattern, re.IGNORECASE | re.UNICODE)
            except re.error:
                continue
            patterns.append(pattern)
        if not phrases and not patterns:
            return None
        match_mode = str(payload.get("match_mode") or "ANY").strip().upper()
        if match_mode not in {"ANY", "ALL", "REGEX"}:
            match_mode = "ANY"
        weight = int(payload.get("weight") or 1)
        return cls(
            id=str(payload.get("id") or target_key).strip() or target_key,
            label=label,
            target_kind=target_kind,
            target_key=target_key,
            match_mode=match_mode,
            phrases=phrases,
            patterns=tuple(patterns),
            negative_phrases=negative_phrases,
            enabled=bool(payload.get("enabled", True)),
            weight=max(1, min(weight, 100)),
        )

    def negative_match(self, text: str) -> bool:
        lowered = text.casefold()
        return any(phrase.casefold() in lowered for phrase in self.negative_phrases)

    def evidence(self, text: str) -> list[tuple[int, int, str]]:
        if not self.enabled or not text or self.negative_match(text):
            return []
        evidence: list[tuple[int, int, str]] = []
        lowered = text.casefold()
        for phrase in self.phrases:
            start = lowered.find(phrase.casefold())
            if start >= 0:
                evidence.append((start, start + len(phrase), text[start : start + len(phrase)]))
        for pattern in self.patterns:
            try:
                regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            except re.error:
                continue
            match = regex.search(text)
            if match:
                evidence.append((match.start(), match.end(), match.group(0)))
        if self.match_mode == "ALL":
            needed = len(self.phrases) + len(self.patterns)
            return evidence if needed > 0 and len(evidence) >= needed else []
        if self.match_mode == "REGEX" and self.patterns:
            return [item for item in evidence if any(re.search(pattern, item[2], re.IGNORECASE | re.UNICODE) for pattern in self.patterns)]
        return evidence[:1]

    def matches(self, text: str) -> bool:
        return bool(self.evidence(text))


@dataclass(frozen=True)
class ProjectOntologyRules:
    enabled: bool = True
    rules: tuple[ProjectOntologyRule, ...] = field(default_factory=tuple)

    @classmethod
    def from_payload(cls, payload: Any) -> "ProjectOntologyRules":
        data = payload if isinstance(payload, dict) else {}
        enabled = bool(data.get("enabled", True))
        raw_rules = data.get("rules") or []
        rules: list[ProjectOntologyRule] = []
        if isinstance(raw_rules, list):
            for item in raw_rules:
                rule = ProjectOntologyRule.from_dict(item)
                if rule is not None:
                    rules.append(rule)
        return cls(enabled=enabled, rules=tuple(rules[:80]))

    def for_kind(self, target_kind: str) -> tuple[ProjectOntologyRule, ...]:
        if not self.enabled:
            return ()
        kind = target_kind.strip().upper()
        return tuple(rule for rule in self.rules if rule.enabled and rule.target_kind == kind)
