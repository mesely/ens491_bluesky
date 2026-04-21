"""
Shared political/language filtering utilities for the Bluesky pipeline.
"""

from __future__ import annotations

import re
from typing import Iterable
from agenda_keywords import AGENDA_2023_2026_KEYWORDS


EXCLUDED_HANDLES: set[str] = {
    "omercelik.com",
}


HIGH_SIGNAL_TERMS: set[str] = {
    "akp", "ak parti", "chp", "mhp", "dem parti", "iyi parti", "yeni yol",
    "tbmm", "meclis", "milletvekili", "cumhurbaskani", "cumhurbaşkanı",
    "bakan", "belediye", "belediye baskani", "belediye başkanı", "secim",
    "seçim", "iktidar", "muhalefet", "anayasa", "kanun", "yargi", "yargı",
    "mahkeme", "savci", "savcı", "iddianame", "gozalti", "gözaltı",
    "tutuklama", "protesto", "eylem", "miting", "siyasi", "politika",
    "parti", "ibb", "imamoglu", "imamoğlu", "erdogan", "erdoğan",
    "ozgur ozel", "özgür özel", "kilicdaroglu", "kılıçdaroğlu", "bahceli",
    "bahçeli", "demirtas", "demirtaş", "aksener", "akşener", "sarachane",
    "saraçhane", "kent uzlasisi", "kent uzlaşısı", "diploma iptali",
}

MEDIUM_SIGNAL_TERMS: set[str] = {
    "enflasyon", "asgari ucret", "asgari ücret", "emekli", "issizlik",
    "işsizlik", "vergi", "zam", "butce", "bütçe", "faiz", "doviz", "döviz",
    "deprem", "egitim", "eğitim", "saglik", "sağlık", "universite",
    "üniversite", "ogrenci", "öğrenci", "sendika", "grev", "ifade ozgurlugu",
    "ifade özgürlüğü", "insan haklari", "insan hakları", "hukuk devleti",
    "demokrasi", "adalet", "sosyal devlet", "secmen", "seçmen",
}

TR_FUNCTION_WORDS = (
    " bir ", " bu ", " ve ", " ile ", " için ", " değil ", " gibi ", " kadar ",
    " çünkü ", " ama ", " fakat ", " ancak ", " daha ", " sonra ", " önce ",
)

TR_CHAR_PATTERN = re.compile(r"[çğıöşüİı]", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"#(\w+)", r"\1", text)
    text = re.sub(r"[^\w\sçğıöşüİı]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_handle(handle: str) -> str:
    return (handle or "").strip().lower()


def should_exclude_actor(handle: str) -> bool:
    return normalize_handle(handle) in EXCLUDED_HANDLES


def is_milletvekili_flag(value) -> bool:
    return str(value).strip().lower() == "true"


def is_turkish_text(text: str) -> bool:
    t = f" {normalize_text(text)} "
    if len(t.strip()) < 8:
        return False
    if TR_CHAR_PATTERN.search(t):
        return True
    if any(w in t for w in TR_FUNCTION_WORDS):
        return True
    if " turkiye " in t or " türkiye " in t or " istanbul " in t or " ankara " in t:
        return True
    return False


def political_keyword_score(text: str, extra_terms: Iterable[str] | None = None) -> int:
    t = f" {normalize_text(text)} "
    score = 0

    for term in HIGH_SIGNAL_TERMS:
        if f" {term} " in t:
            score += 3
    for term in MEDIUM_SIGNAL_TERMS:
        if f" {term} " in t:
            score += 1

    if extra_terms:
        for term in extra_terms:
            term = normalize_text(term)
            if term and f" {term} " in t:
                score += 2

    # Hashtag-based political signals
    if any(tag in t for tag in (" secim ", " protesto ", " meclis ", " tbmm ", " imamoğlu ", " imamoglu ")):
        score += 2

    return score


def is_political_text(text: str, min_score: int = 2, extra_terms: Iterable[str] | None = None) -> bool:
    score = political_keyword_score(text, extra_terms=extra_terms)
    if score >= min_score:
        return True
    t = f" {normalize_text(text)} "
    # broad agenda fallback to increase recall on current Turkish political agenda
    for kw in AGENDA_2023_2026_KEYWORDS:
        nkw = normalize_text(kw)
        if nkw and f" {nkw} " in t:
            return True
    return False
