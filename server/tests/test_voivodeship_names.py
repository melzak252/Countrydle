import pytest
from voivodeship_names import CANONICAL_VOIVODESHIPS, resolve_voivodeship_name


@pytest.mark.parametrize("canonical", CANONICAL_VOIVODESHIPS)
def test_all_canonical_voivodeships_resolve_identically(canonical):
    assert resolve_voivodeship_name(canonical) == canonical
    assert resolve_voivodeship_name(canonical.lower()) == canonical
    assert resolve_voivodeship_name(f"województwo {canonical.lower()}") == canonical
    assert resolve_voivodeship_name(f"woj. {canonical.lower()}") == canonical


@pytest.mark.parametrize("input_name, expected", [
    ("łódzkim", "Łódzkie"),
    ("lodzkim", "Łódzkie"),
    ("województwie łódzkim", "Łódzkie"),
    ("województwem łódzkim", "Łódzkie"),
    ("Łódź", "Łódzkie"),
    ("lodz", "Łódzkie"),
    ("małopolskim", "Małopolskie"),
    ("malopolskim", "Małopolskie"),
    ("Kraków", "Małopolskie"),
    ("krakow", "Małopolskie"),
    ("śląskim", "Śląskie"),
    ("slaskim", "Śląskie"),
    ("Katowice", "Śląskie"),
    ("mazowieckim", "Mazowieckie"),
    ("Warszawa", "Mazowieckie"),
    ("wielkopolskim", "Wielkopolskie"),
    ("Poznań", "Wielkopolskie"),
    ("dolnośląskim", "Dolnośląskie"),
    ("Wrocław", "Dolnośląskie"),
    ("pomorskim", "Pomorskie"),
    ("Gdańsk", "Pomorskie"),
    ("podlaskim", "Podlaskie"),
    ("Białystok", "Podlaskie"),
    ("podkarpackim", "Podkarpackie"),
    ("Rzeszów", "Podkarpackie"),
    ("świętokrzyskim", "Świętokrzyskie"),
    ("Kielce", "Świętokrzyskie"),
    ("lubelskim", "Lubelskie"),
    ("Lublin", "Lubelskie"),
    ("kujawsko-pomorskim", "Kujawsko-Pomorskie"),
    ("Bydgoszcz", "Kujawsko-Pomorskie"),
    ("Toruń", "Kujawsko-Pomorskie"),
    ("warmińsko-mazurskim", "Warmińsko-Mazurskie"),
    ("Olsztyn", "Warmińsko-Mazurskie"),
    ("lubuskim", "Lubuskie"),
    ("Zielona Góra", "Lubuskie"),
    ("Gorzów", "Lubuskie"),
    ("opolskim", "Opolskie"),
    ("Opole", "Opolskie"),
    ("zachodniopomorskim", "Zachodniopomorskie"),
    ("Szczecin", "Zachodniopomorskie"),
])
def test_inflections_and_capitals_resolve_to_canonical(input_name, expected):
    assert resolve_voivodeship_name(input_name) == expected


@pytest.mark.parametrize("invalid", [
    None, 123, "", "   ", "Narnia", "Polska", "Berlin", "powiat krakowski",
])
def test_invalid_and_unknown_names_return_none(invalid):
    assert resolve_voivodeship_name(invalid) is None
