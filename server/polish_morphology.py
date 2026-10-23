"""Deterministic Polish morphological normalizer and token lemmatizer.

Operates on ASCII-folded Polish stems to reliably handle accented and unaccented Polish
(<0.1ms per query) with zero external NLP dependencies.
"""
from __future__ import annotations
from functools import lru_cache
import itertools
import re
import unicodedata
from typing import Any, Iterable


@lru_cache(maxsize=2048)
def norm_pl(text: str) -> str:
    """Case-folded, diacritic-free, alphanumeric text with single spaces."""
    folded = text.casefold().replace("ł", "l")
    normalized = unicodedata.normalize("NFKD", folded)
    clean = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    clean = re.sub(r"[^\w\s-]", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


PLURALIA_TANTUM: frozenset[str] = frozenset({
    "balkany", "karaiby", "indochiny", "pasy", "niemcy", "wlochy", "wegry", "czechy",
    "chiny", "indie", "filipiny", "malediwy", "bahamy", "komory", "seszele",
    "niderlandy", "hawaje", "alpy", "karpaty", "sudety", "tatry", "bieszczady",
    "karkonosze", "beskidy", "mazury", "kujawy", "ameryki",
})


def expand_polish_word_forms(word: str) -> set[str]:
    """Generate inflected case forms for a single Polish word in ASCII-folded form."""
    w = norm_pl(word)
    if len(w) <= 2:
        return {w}

    # Pluralia tantum nouns
    if w in PLURALIA_TANTUM:
        stem = w[:-1]
        forms = {w, stem, stem + "ow", stem + "om", stem + "ami", stem + "ach", stem + "ech"}
        if stem.endswith("c"):
            forms.add(stem[:-1] + "czech")  # niemcy -> niemczech
        if stem.endswith("r"):
            forms.add(stem + "zech")        # wegry -> wegrzech
        return forms

    # Adjectives ending in -y or -i
    if w.endswith(("y", "i")):
        stem = w[:-1]
        suffixes = (
            "y", "i", "a", "e", "ie", "ego", "iego", "ej", "iej",
            "ym", "im", "ych", "ich", "ymi", "imi",
        )
        return {stem + suf for suf in suffixes}

    # Feminine nouns ending in -a
    if w.endswith("a") and len(w) > 3:
        stem = w[:-1]
        forms = {
            w, stem, stem + "e", stem + "i", stem + "y", stem + "ie",
            stem + "o", stem + "om", stem + "ami", stem + "ach",
        }
        # Palatalization for Dative / Locative singular
        if stem.endswith("sl"):
            forms.add(stem[:-2] + "sle")
        elif stem.endswith("sn"):
            forms.add(stem[:-2] + "sni")
        elif stem.endswith("k"):
            forms.add(stem[:-1] + "ce")
        elif stem.endswith("g"):
            forms.add(stem[:-1] + "dze")
        elif stem.endswith("r"):
            forms.add(stem[:-1] + "rze")
        elif stem.endswith("l"):
            forms.update({stem[:-1] + "le", stem[:-1] + "li", stem + "e", stem + "i"})
        elif stem.endswith("t"):
            forms.add(stem[:-1] + "cie")
        elif stem.endswith("d"):
            forms.add(stem[:-1] + "dzie")
        elif stem.endswith("c"):
            forms.add(stem[:-1] + "cy")
        return forms

    # Neuter nouns ending in -o or -e
    if w.endswith(("o", "e")) and len(w) > 3:
        stem = w[:-1]
        return {
            w, stem, stem + "o", stem + "e", stem + "a", stem + "u", stem + "em",
            stem + "iem", stem + "ie", stem + "iu", stem + "om", stem + "ami", stem + "ach",
        }

    # Masculine consonant nouns
    if len(w) > 2 and not w.endswith(("a", "e", "o", "i", "y", "u")):
        forms = {
            w, w + "u", w + "a", w + "em", w + "iem", w + "ie",
            w + "owi", w + "ow", w + "om", w + "ami", w + "ach",
        }
        if w.endswith("t"):
            forms.add(w[:-1] + "cie")
            forms.add(w[:-1] + "ciem")
        elif w.endswith("d"):
            forms.add(w[:-1] + "dzie")
            forms.add(w[:-1] + "dziem")
        elif w.endswith("r"):
            forms.add(w[:-1] + "rze")
            forms.add(w[:-1] + "rzem")
        elif w.endswith("k"):
            forms.add(w[:-1] + "ce")
            forms.add(w[:-1] + "ku")
        elif w.endswith("g"):
            forms.add(w[:-1] + "dze")
            forms.add(w[:-1] + "gu")
        elif w.endswith("ch"):
            forms.add(w[:-2] + "sze")
            forms.add(w[:-2] + "szem")
        return forms

    return {w}


def expand_polish_phrase_forms(phrase: str, *, reversible: bool = False) -> set[str]:
    """Generate inflected case forms for multi-word phrases."""
    norm = norm_pl(phrase)
    tokens = norm.split()
    if not tokens:
        return set()
    if len(tokens) == 1:
        return expand_polish_word_forms(tokens[0])
    if len(tokens) == 2:
        f1 = expand_polish_word_forms(tokens[0])
        f2 = expand_polish_word_forms(tokens[1])
        res = {f"{a} {b}" for a in f1 for b in f2}
        if reversible:
            res.update(f"{b} {a}" for a in f1 for b in f2)
        return res

    res = {norm}
    for w0 in expand_polish_word_forms(tokens[0]):
        res.add(" ".join([w0, *tokens[1:]]))
    for w_last in expand_polish_word_forms(tokens[-1]):
        res.add(" ".join([*tokens[:-1], w_last]))
    for w1 in expand_polish_word_forms(tokens[1]):
        res.add(" ".join([tokens[0], w1, *tokens[2:]]))
    if len(tokens) == 3 and tokens[1] == "i":
        for a in expand_polish_word_forms(tokens[0]):
            for b in expand_polish_word_forms(tokens[2]):
                res.add(f"{a} i {b}")
    return res


DOMAIN_BASE_WORDS: tuple[str, ...] = (
    # Geographical nouns
    "kraj", "panstwo", "wojewodztwo", "powiat", "stan", "kontynent", "region",
    "czesc", "stolica", "wyspa", "archipelag", "morze", "ocean", "rzeka",
    "wybrzeze", "plaza", "jezioro", "zatoka", "rownik", "poludnik", "polkula",
    "greenwich", "granica", "sasiad", "mieszkaniec", "populacja", "ludnosc",
    "powierzchnia", "flaga", "kolor", "herb", "symbol", "gwiazda", "krzyz",
    "polksiezyc", "slonce", "pasy", "kolo", "orzel", "jezyk", "monarchia",
    "republika", "myslnik", "czlon", "litera", "tablica", "wyroznik", "unia",
    "sojusz", "organizacja", "miasto", "gmina", "kolonia", "wojna",
    "uklad", "pakt", "zwiazek", "cesarstwo", "imperium", "polwysep", "rog",
    # Continents, regions, and neighbor countries
    "europa", "azja", "afryka", "ameryka", "australia", "antarktyda", "eurazja",
    "baltyk", "pacyfik", "atlantyk", "niemcy", "czechy", "slowacja", "ukraina",
    "bialorus", "litwa", "rosja",
    # Entity and geographic adjectives
    "europejski", "azjatycki", "afrykanski", "amerykanski", "radziecki", "sowiecki",
    "warszawski", "osmanski", "brytyjski", "hiszpanski", "francuski", "portugalski",
    "austro-wegierski", "zerowy", "meksykanski", "karaibski", "srodziemny", "adriatycki",
    # Adjectives and road terms
    "polnocny", "poludniowy", "wschodni", "zachodni", "srodkowy", "centralny",
    "nadmorski", "srodladowy", "wyspiarski", "czerwony", "bialy", "niebieski",
    "zielony", "zolty", "czarny", "pomaranczowy", "prawostronny", "lewostronny",
    "urzedowy", "dwuczlonowy", "trzyczlonowy", "dwuliterowy", "trzyliterowy",
    "grodzki", "ziemski", "wiekszy", "mniejszy", "wielki", "maly", "calkowity",
    "skandynawski", "baltycki", "slowianski", "arabski", "bezposredni", "obcy",
    "lewy", "prawy", "strona", "droga", "jezdnia", "ulica",
)

VERB_AND_IRREGULAR_LEMMAS: dict[str, str] = {
    # Location verbs -> lezec
    "lezy": "lezec",
    "leza": "lezec",
    "lezacy": "lezec",
    "lezaca": "lezec",
    "lezace": "lezec",
    "polozony": "lezec",
    "polozona": "lezec",
    "polozone": "lezec",
    "polozonego": "lezec",
    "polozonej": "lezec",
    "polozonych": "lezec",
    "zlokalizowany": "lezec",
    "zlokalizowana": "lezec",
    "zlokalizowane": "lezec",
    "znajduje": "znajdowac",
    "znajduja": "znajdowac",
    "znajdowac": "znajdowac",
    "miesci": "miescic",
    "mieszcza": "miescic",
    "miescic": "miescic",
    "styka": "stykac",
    "stykaja": "stykac",
    "stykac": "stykac",

    # Copula -> byc
    "jest": "byc",
    "sa": "byc",
    "bedzie": "byc",
    "beda": "byc",
    "byc": "byc",

    # Past copula -> bylo_past
    "byl": "bylo_past",
    "byla": "bylo_past",
    "bylo": "bylo_past",
    "byli": "bylo_past",
    "byly": "bylo_past",

    # Possession verbs -> miec
    "ma": "miec",
    "maja": "miec",
    "posiada": "miec",
    "posiadaja": "miec",
    "posiadac": "miec",
    "dysponuje": "miec",
    "dysponuja": "miec",
    "miec": "miec",

    # Present border verbs -> graniczyc
    "graniczy": "graniczyc",
    "granicza": "graniczyc",
    "sasiaduje": "graniczyc",
    "sasiaduja": "graniczyc",
    "graniczacy": "graniczyc",
    "graniczaca": "graniczyc",
    "graniczace": "graniczyc",
    "graniczyc": "graniczyc",

    # Past border verbs -> graniczyc_past
    "graniczyl": "graniczyc_past",
    "graniczyla": "graniczyc_past",
    "graniczylo": "graniczyc_past",
    "sasiadowal": "graniczyc_past",
    "sasiadowala": "graniczyc_past",
    "sasiadowalo": "graniczyc_past",

    # Membership verbs -> nalezec
    "nalezy": "nalezec",
    "naleza": "nalezec",
    "nalezec": "nalezec",

    # Past membership -> nalezec_past
    "nalezal": "nalezec_past",
    "nalezala": "nalezec_past",
    "nalezalo": "nalezec_past",
    "nalezaly": "nalezec_past",
    "wchodzil": "nalezec_past",
    "wchodzila": "nalezec_past",
    "wchodzilo": "nalezec_past",
    "wchodzily": "nalezec_past",

    # River flow verbs -> plynac
    "plynie": "plynac",
    "przeplywa": "plynac",
    "plyna": "plynac",
    "przeplywaja": "plynac",
    "plynac": "plynac",

    # Crossing verbs -> przecinac
    "przecina": "przecinac",
    "przechodzi": "przecinac",
    "przecinaja": "przecinac",
    "przechodza": "przecinac",
    "przecinac": "przecinac",

    # Driving verbs -> jezdzic
    "jezdzi": "jezdzic",
    "jezdza": "jezdzic",
    "jezdzi_sie": "jezdzic",
    "jezdzic": "jezdzic",
    "obowiazuje": "obowiazywac",
    "obowiazuja": "obowiazywac",
    "obowiazywac": "obowiazywac",

    # Vocalized prepositions
    "ze": "z",
    "we": "w",
    "ode": "od",

    # Irregular plurals and genitives
    "mieszkancow": "mieszkaniec",
    "mieszkancy": "mieszkaniec",
    "mieszkancami": "mieszkaniec",
    "mieszkancach": "mieszkaniec",
    "mieszkanca": "mieszkaniec",
    "ludzi": "mieszkaniec",
    "ludzmi": "mieszkaniec",
    "osob": "mieszkaniec",
    "osoba": "mieszkaniec",
    "osoby": "mieszkaniec",
    "sasiadow": "sasiad",
    "sasiada": "sasiad",
    "sasiadami": "sasiad",
    "sasiedzi": "sasiad",
    "sasiadach": "sasiad",
    "stolic": "stolica",
    "stolice": "stolica",
    "stolicy": "stolica",
    "stolica": "stolica",
    "stolicom": "stolica",
    "stolicami": "stolica",
    "stolicach": "stolica",

    # Numbers
    "dwie": "2",
    "dwa": "2",
    "dwoma": "2",
    "dwoch": "2",
    "dwu": "2",
    "trzy": "3",
    "trzech": "3",
    "trzema": "3",
    "jedna": "1",
    "jeden": "1",
    "jednym": "1",
    "jednego": "1",

    # Border noun (CRITICAL: keep distinct from graniczyc verb!)
    "granica": "granica",
    "granice": "granica",
    "granicy": "granica",
    "granicom": "granica",
    "granicami": "granica",
    "granicach": "granica",
    "granic": "granica",
    "czescia": "czesc",
    "czesci": "czesc",
    "zwiazku": "zwiazek",
    "zwiazkiem": "zwiazek",
    "wegier": "wegry",
    "wegrow": "wegry",
    "wegrami": "wegry",
    "wegrzech": "wegry",
    "poludniowo": "poludniowy",
    "polnocno": "polnocny",

    # Comparatives
    "wiecej": "wiecej",
    "mniej": "mniej",
    "wiekszy": "wiekszy",
    "wieksza": "wiekszy",
    "wieksze": "wiekszy",
    "wiekszego": "wiekszy",
    "wiekszej": "wiekszy",
    "wiekszym": "wiekszy",
    "wiekszych": "wiekszy",
    "wiekszymi": "wiekszy",
    "mniejszy": "mniejszy",
    "mniejsza": "mniejszy",
    "mniejsze": "mniejszy",
    "mniejszego": "mniejszy",
    "mniejszej": "mniejszy",
    "mniejszym": "mniejszy",
    "mniejszych": "mniejszy",
    "mniejszymi": "mniejszy",
}


def _build_token_lemma_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for base in DOMAIN_BASE_WORDS:
        lemma = norm_pl(base)
        for form in expand_polish_word_forms(base):
            mapping[form] = lemma
    # Overrides and verbs
    mapping.update(VERB_AND_IRREGULAR_LEMMAS)
    return mapping


TOKEN_LEMMA_MAP: dict[str, str] = _build_token_lemma_map()


def lemmatize_pl_tokens(text: str) -> str:
    """Normalize and lemmatize whitespace-separated tokens."""
    norm = norm_pl(text)
    tokens = norm.split()
    lemmas = [TOKEN_LEMMA_MAP.get(t, t) for t in tokens]
    return " ".join(lemmas)


_FORBIDDEN_CHARS = frozenset({"/", "\\", ";", "<", ">"})


@lru_cache(maxsize=2048)
def canonicalize_pl_clause(
    raw_query: str,
    *,
    target_nouns: tuple[str, ...] = ("kraj", "panstwo"),
) -> str | None:
    """Canonicalize a single-clause Polish query by lemmatizing and stripping filler syntax."""
    if not isinstance(raw_query, str) or not raw_query.strip():
        return None
    raw_query = re.sub(r"\b(morz\w*)\s*/\s*(ocean\w*)\b", r"\1 lub \2", raw_query, flags=re.IGNORECASE)
    if any(ch in raw_query for ch in _FORBIDDEN_CHARS):
        return None
    # Check for invalid non-Latin combining marks
    nfkd = unicodedata.normalize("NFKD", raw_query)
    for ch in nfkd:
        if unicodedata.category(ch).startswith("M"):
            if ch not in ("\u0301", "\u0328", "\u0307", "\u0300", "\u0302", "\u0303", "\u0308", "\u030a"):
                return None

    norm = norm_pl(raw_query).replace("-", " ")

    # Normalize prepositional neuter target pronoun before lemmatization so "przez nie"
    # is never treated as the negation token "nie".
    norm = re.sub(r"\bprzez (?:nie|to wojewodztwo|ten powiat|wojewodztwo|powiat)\b", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    lemmatized = lemmatize_pl_tokens(norm)

    # Collapse multi-word verbal idioms
    clause = re.sub(r"\b(?:znajdowac sie|miescic sie|znajdowac|miescic|lezec sie)\b", "lezec", lemmatized)
    clause = re.sub(r"\b(?:stykac sie|miec granica|dzielic granica|miec wspolny granica)\b", "graniczyc", clause)
    clause = re.sub(r"\blinia brzegowy\b", "wybrzeze", clause)
    clause = re.sub(r"\bpo lewy strona(?!\s+od\b)(?:\s+(?:droga|jezdnia|ulica))?\b", "ruch lewostronny", clause)
    clause = re.sub(r"\bpo prawy strona(?!\s+od\b)(?:\s+(?:droga|jezdnia|ulica))?\b", "ruch prawostronny", clause)
    clause = re.sub(r"\bna mapie\b", " ", clause)
    clause = re.sub(r"\b(?:jezdzic sie|obowiazywac)\b", "byc", clause)

    # Strip locative target filler
    clause = re.sub(r"\bw tym (?:kraj|panstwo|wojewodztwo|powiat|stan)\b", " ", clause)

    # Strip leading question particle
    clause = re.sub(r"^czy\s+", "", clause.strip())

    # Strip target subject noun phrases while keeping prepositional objects and classified predicates
    nouns_pattern = "|".join(re.escape(n) for n in target_nouns)
    target_subject_pattern = (
        rf"(?<!\bz )(?<!\bod )(?<!\bniz )(?<!\bw )(?<!\bna )(?<!\binny )(?<!\bobcy )"
        rf"\b(?:ten |to |tego |ukryty |szukany )?(?:{nouns_pattern})(?: ten| to)?\b"
        rf"(?!\s+(?:baltycki|skandynawski|slowianski|arabski|ziemski|grodzki))"
    )
    clause = re.sub(target_subject_pattern, " ", clause)

    # Strip leading copula 'to' and collapse 'to byc' / 'byc to'
    clause = re.sub(r"^(?:byc\s+)?to\b\s*", "", clause.strip())
    clause = re.sub(r"\b(?:to byc|byc to)\b", "byc", clause)

    clean_clause = re.sub(r"\s+", " ", clause).strip()
    return clean_clause if clean_clause else None
