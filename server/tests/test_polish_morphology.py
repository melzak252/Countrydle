"""Tests for Polish morphological normalizer and clause canonicalizer."""

import pytest

from polish_morphology import (
    canonicalize_pl_clause,
    expand_polish_phrase_forms,
    expand_polish_word_forms,
    lemmatize_pl_tokens,
    norm_pl,
)


def test_norm_pl_diacritics_and_symbols():
    assert norm_pl("Czy leży w Europie?") == "czy lezy w europie"
    assert norm_pl("Gdańsk, Łódź & Kraków!") == "gdansk lodz krakow"
    assert norm_pl("Zażółć gęślą jaźń") == "zazolc gesla jazn"
    assert norm_pl("   wielokrotne    spacje  ") == "wielokrotne spacje"


def test_expand_polish_word_forms_categories():
    # Pluralia tantum
    niemcy_forms = expand_polish_word_forms("Niemcy")
    assert "niemczech" in niemcy_forms
    assert "niemcami" in niemcy_forms
    assert "niemcow" in niemcy_forms

    wegry_forms = expand_polish_word_forms("Węgry")
    assert "wegrzech" in wegry_forms
    assert "wegrami" in wegry_forms

    # Adjectives
    polnocny_forms = expand_polish_word_forms("północny")
    assert "polnocnego" in polnocny_forms
    assert "polnocnej" in polnocny_forms
    assert "polnocnym" in polnocny_forms
    assert "polnocnych" in polnocny_forms

    # Feminine nouns
    polska_forms = expand_polish_word_forms("Polska")
    assert "polsce" in polska_forms
    assert "polski" in polska_forms
    assert "polske" in polska_forms
    assert "polsk" in polska_forms

    kanada_forms = expand_polish_word_forms("Kanada")
    assert "kanadzie" in kanada_forms

    wisla_forms = expand_polish_word_forms("Wisła")
    assert "wisle" in wisla_forms
    assert "wisly" in wisla_forms

    # Neuter nouns
    morze_forms = expand_polish_word_forms("morze")
    assert "morzem" in morze_forms
    assert "morzu" in morze_forms
    assert "morza" in morze_forms

    panstwo_forms = expand_polish_word_forms("państwo")
    assert "panstwem" in panstwo_forms
    assert "panstwie" in panstwo_forms
    assert "panstwa" in panstwo_forms

    # Masculine consonant nouns
    ocean_forms = expand_polish_word_forms("ocean")
    assert "oceanu" in ocean_forms
    assert "oceanem" in ocean_forms
    assert "oceanie" in ocean_forms


def test_expand_polish_phrase_forms():
    forms = expand_polish_phrase_forms("Ocean Atlantycki", reversible=True)
    assert "ocean atlantycki" in forms
    assert "oceanu atlantyckiego" in forms
    assert "atlantycki ocean" in forms
    assert "atlantyckim oceanem" in forms


def test_lemmatize_pl_tokens():
    assert lemmatize_pl_tokens("leży w europie") == "lezec w europa"
    assert lemmatize_pl_tokens("jest w azji") == "byc w azja"
    assert lemmatize_pl_tokens("ma dostęp do morza") == "miec dostep do morze"
    # Border distinction: graniczy (verb) vs granic (noun)
    assert lemmatize_pl_tokens("graniczy z niemcami") == "graniczyc z niemcy"
    assert lemmatize_pl_tokens("wiecej granic niz niemcy") == "wiecej granica niz niemcy"


def test_canonicalize_pl_clause_countrydle():
    # Direct questions
    assert canonicalize_pl_clause("Czy ten kraj leży w Europie?") == "lezec w europa"
    assert canonicalize_pl_clause("Czy to państwo znajduje się w Azji?") == "lezec w azja"
    assert canonicalize_pl_clause("Czy graniczy z Niemcami?") == "graniczyc z niemcy"
    assert canonicalize_pl_clause("Czy z Tadżykistanem graniczy ten kraj?") == "z tadzykistanem graniczyc"

    # Preserving prepositional objects and classified nouns
    clause_comp = canonicalize_pl_clause("Czy graniczy z krajem większym od Polski?")
    assert "z kraj" in clause_comp  # 'kraj' not stripped because of 'z '
    assert clause_comp == "graniczyc z kraj wiekszy od polski"

    clause_baltic = canonicalize_pl_clause("Czy to jest kraj bałtycki?")
    assert "kraj baltycki" in clause_baltic  # 'kraj' not stripped because of 'baltycki'

    # Driving side idiom
    assert canonicalize_pl_clause("Czy w tym kraju jeździ się po lewej stronie drogi?") == "byc ruch lewostronny"

    # Prepositional neuter target pronoun 'przez nie'
    assert canonicalize_pl_clause("Czy płynie przez nie Wisła?", target_nouns=("powiat",)) == "plynac wisla"

    # Rejection of forbidden characters
    assert canonicalize_pl_clause("Czy leży w Europie/Azji?") is None
    assert canonicalize_pl_clause("Czy leży w Europie; azji?") is None
