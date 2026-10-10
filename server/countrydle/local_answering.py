"""Local SQLite-based answering for Countrydle questions.

This module is intentionally conservative: it only answers questions that can be
mapped with high confidence to one of the local knowledge-base relations. Unknown
facts and ill-typed predicates return no local answer so the caller can use the
general-knowledge fallback without turning missing knowledge into false.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import sqlite3
import unicodedata
from typing import Iterable
from country_fact_provenance import RELATIONS as EVIDENCE_RELATIONS, read_record


APP_DIR = Path(__file__).resolve().parent
# Local dev: <repo>/server/countrydle with data in <repo>/data.
# Docker: /usr/src/app/countrydle with data in /usr/src/app/data.
ROOT_DIR = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR.parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "country_facts.sqlite"


@dataclass(frozen=True)
class LocalAnswer:
    question: str
    answer: bool | None
    explanation: str
    relation: str
    fact_provenance: list[dict] = field(default_factory=list)


POLISH_COUNTRY_ALIASES = {
    # Europe
    "polska": "Poland", "polski": "Poland", "polsce": "Poland", "polskę": "Poland", "polską": "Poland",
    "niemcy": "Germany", "niemiec": "Germany", "niemcom": "Germany", "niemcami": "Germany", "niemczech": "Germany",
    "francja": "France", "francji": "France", "francję": "France", "francją": "France",
    "włochy": "Italy", "włoch": "Italy", "włochom": "Italy", "włochami": "Italy", "włoszech": "Italy", "wlochy": "Italy", "wlochami": "Italy",
    "hiszpania": "Spain", "hiszpanii": "Spain", "hiszpanię": "Spain", "hiszpanią": "Spain",
    "portugalia": "Portugal", "portugalii": "Portugal", "portugalię": "Portugal", "portugalią": "Portugal",
    "wielka brytania": "United Kingdom", "wielkiej brytanii": "United Kingdom", "wielką brytanię": "United Kingdom", "wielką brytanią": "United Kingdom", "anglia": "United Kingdom", "anglii": "United Kingdom", "anglią": "United Kingdom", "uk": "United Kingdom",
    "irlandia": "Ireland", "irlandii": "Ireland", "irlandię": "Ireland", "irlandią": "Ireland",
    "islandia": "Iceland", "islandii": "Iceland", "islandię": "Iceland", "islandią": "Iceland",
    "norwegia": "Norway", "norwegii": "Norway", "norwegię": "Norway", "norwegią": "Norway",
    "szwecja": "Sweden", "szwecji": "Sweden", "szwecję": "Sweden", "szwecją": "Sweden",
    "finlandia": "Finland", "finlandii": "Finland", "finlandię": "Finland", "finlandią": "Finland",
    "dania": "Denmark", "danii": "Denmark", "danię": "Denmark", "danią": "Denmark",
    "holandia": "Netherlands", "holandii": "Netherlands", "holandię": "Netherlands", "holandią": "Netherlands", "niderlandy": "Netherlands", "niderlandów": "Netherlands",
    "belgia": "Belgium", "belgii": "Belgium", "belgię": "Belgium", "belgią": "Belgium",
    "luksemburg": "Luxembourg", "luksemburga": "Luxembourg", "luksemburgiem": "Luxembourg",
    "szwajcaria": "Switzerland", "szwajcarii": "Switzerland", "szwajcarię": "Switzerland", "szwajcarią": "Switzerland",
    "austria": "Austria", "austrii": "Austria", "austrię": "Austria", "austrią": "Austria",
    "czechy": "Czech Republic", "czech": "Czech Republic", "czechom": "Czech Republic", "czechami": "Czech Republic", "czechach": "Czech Republic",
    "słowacja": "Slovakia", "słowacji": "Slovakia", "słowację": "Slovakia", "słowacją": "Slovakia", "slowacja": "Slovakia",
    "węgry": "Hungary", "węgier": "Hungary", "węgrom": "Hungary", "węgrami": "Hungary", "węgrzech": "Hungary", "wegry": "Hungary",
    "rumunia": "Romania", "rumunii": "Romania", "rumunię": "Romania", "rumunią": "Romania",
    "bułgaria": "Bulgaria", "bułgarii": "Bulgaria", "bułgarię": "Bulgaria", "bułgarią": "Bulgaria", "bulgaria": "Bulgaria",
    "grecja": "Greece", "grecji": "Greece", "grecję": "Greece", "grecją": "Greece",
    "albania": "Albania", "albanii": "Albania", "albanię": "Albania", "albanią": "Albania",
    "macedonia": "North Macedonia", "macedonii": "North Macedonia", "macedonię": "North Macedonia", "macedonią": "North Macedonia", "macedonia północna": "North Macedonia", "macedonii północnej": "North Macedonia",
    "kosowo": "Kosovo", "kosowa": "Kosovo", "kosowem": "Kosovo",
    "serbia": "Serbia", "serbii": "Serbia", "serbię": "Serbia", "serbią": "Serbia",
    "czarnogóra": "Montenegro", "czarnogóry": "Montenegro", "czarnogórę": "Montenegro", "czarnogórą": "Montenegro", "czarnogora": "Montenegro",
    "bośnia": "Bosnia and Herzegovina", "bośni": "Bosnia and Herzegovina", "bośnię": "Bosnia and Herzegovina", "bośnią": "Bosnia and Herzegovina", "bośnia i hercegowina": "Bosnia and Herzegovina", "bośni i hercegowiny": "Bosnia and Herzegovina", "bosnia": "Bosnia and Herzegovina", "bosnia i hercegowina": "Bosnia and Herzegovina",
    "chorwacja": "Croatia", "chorwacji": "Croatia", "chorwację": "Croatia", "chorwacją": "Croatia",
    "słowenia": "Slovenia", "słowenii": "Slovenia", "słowenię": "Slovenia", "słowenią": "Slovenia", "slowenia": "Slovenia",
    "mołdawia": "Moldova", "mołdawii": "Moldova", "mołdawię": "Moldova", "mołdawią": "Moldova", "moldawia": "Moldova",
    "ukraina": "Ukraine", "ukrainy": "Ukraine", "ukrainie": "Ukraine", "ukrainę": "Ukraine", "ukrainą": "Ukraine",
    "białoruś": "Belarus", "białorusi": "Belarus", "białorusią": "Belarus", "bialorus": "Belarus",
    "litwa": "Lithuania", "litwy": "Lithuania", "litwie": "Lithuania", "litwę": "Lithuania", "litwą": "Lithuania",
    "łotwa": "Latvia", "łotwy": "Latvia", "łotwie": "Latvia", "łotwę": "Latvia", "łotwą": "Latvia", "lotwa": "Latvia",
    "estonia": "Estonia", "estonii": "Estonia", "estonię": "Estonia", "estonią": "Estonia",
    "rosja": "Russia", "rosji": "Russia", "rosję": "Russia", "rosją": "Russia",
    "andora": "Andorra", "andory": "Andorra", "andorze": "Andorra", "andorą": "Andorra",
    "monako": "Monaco",
    "san marino": "San Marino",
    "watykan": "Vatican City", "watykanu": "Vatican City", "watykanem": "Vatican City",
    "liechtenstein": "Liechtenstein", "liechtensteinu": "Liechtenstein",
    "malta": "Malta", "malty": "Malta", "malcie": "Malta", "maltę": "Malta", "maltą": "Malta",
    "cypr": "Cyprus", "cypru": "Cyprus", "cyprem": "Cyprus",

    # Asia & Middle East
    "turcja": "Turkey", "turcji": "Turkey", "turcję": "Turkey", "turcją": "Turkey",
    "gruzja": "Georgia", "gruzji": "Georgia", "gruzję": "Georgia", "gruzją": "Georgia",
    "armenia": "Armenia", "armenii": "Armenia", "armenię": "Armenia", "armenią": "Armenia",
    "azerbejdżan": "Azerbaijan", "azerbejdżanu": "Azerbaijan", "azerbejdżanem": "Azerbaijan", "azerbejdzan": "Azerbaijan",
    "kazachstan": "Kazakhstan", "kazachstanu": "Kazakhstan", "kazachstanem": "Kazakhstan",
    "uzbekistan": "Uzbekistan", "uzbekistanu": "Uzbekistan", "uzbekistanem": "Uzbekistan",
    "turkmenistan": "Turkmenistan", "turkmenistanu": "Turkmenistan", "turkmenistanem": "Turkmenistan",
    "tadżykistan": "Tajikistan", "tadżykistanu": "Tajikistan", "tadżykistanem": "Tajikistan", "tadzykistan": "Tajikistan",
    "kirgistan": "Kyrgyzstan", "kirgistanu": "Kyrgyzstan", "kirgistanem": "Kyrgyzstan",
    "chiny": "China", "chin": "China", "chinom": "China", "chinami": "China", "chinach": "China",
    "mongolia": "Mongolia", "mongolii": "Mongolia", "mongolię": "Mongolia", "mongolią": "Mongolia",
    "korea północna": "North Korea", "korei północnej": "North Korea", "koreę północną": "North Korea", "koreą północną": "North Korea", "korea polnocna": "North Korea",
    "korea południowa": "South Korea", "korei południowej": "South Korea", "koreę południową": "South Korea", "koreą południową": "South Korea", "korea poludniowa": "South Korea",
    "japonia": "Japan", "japonii": "Japan", "japonję": "Japan", "japonią": "Japan",
    "indie": "India", "indii": "India", "indiom": "India", "indiami": "India", "indiach": "India",
    "pakistan": "Pakistan", "pakistanu": "Pakistan", "pakistanem": "Pakistan",
    "bangladesz": "Bangladesh", "bangladeszu": "Bangladesh", "bangladeszem": "Bangladesh",
    "afganistan": "Afghanistan", "afganistanu": "Afghanistan", "afganistanem": "Afghanistan",
    "iran": "Iran", "iranu": "Iran", "iranem": "Iran",
    "irak": "Iraq", "iraku": "Iraq", "irakiem": "Iraq",
    "syria": "Syria", "syrii": "Syria", "syrię": "Syria", "syrią": "Syria",
    "liban": "Lebanon", "libanu": "Lebanon", "libanem": "Lebanon",
    "izrael": "Israel", "izraela": "Israel", "izraelem": "Israel",
    "palestyna": "Palestine", "palestyny": "Palestine", "palestynę": "Palestine", "palestyną": "Palestine",
    "jordania": "Jordan", "jordanii": "Jordan", "jordanię": "Jordan", "jordanią": "Jordan",
    "arabia saudyjska": "Saudi Arabia", "arabii saudyjskiej": "Saudi Arabia", "arabię saudyjską": "Saudi Arabia", "arabia saudyjską": "Saudi Arabia",
    "jemen": "Yemen", "jemenu": "Yemen", "jemenem": "Yemen",
    "oman": "Oman", "omanu": "Oman", "omanem": "Oman",
    "zea": "United Arab Emirates", "zjednoczone emiraty arabskie": "United Arab Emirates", "emiratów": "United Arab Emirates", "emiratami": "United Arab Emirates", "emiraty": "United Arab Emirates",
    "katar": "Qatar", "kataru": "Qatar", "katarem": "Qatar",
    "bahrajn": "Bahrain", "bahrajnu": "Bahrain", "bahrajnem": "Bahrain",
    "kuwejt": "Kuwait", "kuwejtu": "Kuwait", "kuwejtem": "Kuwait",
    "sri lanka": "Sri Lanka", "sri lanki": "Sri Lanka", "sri lankę": "Sri Lanka", "sri lanką": "Sri Lanka",
    "malediwy": "Maldives", "malediwów": "Maldives", "malediwach": "Maldives",
    "nepal": "Nepal", "nepalu": "Nepal", "nepalem": "Nepal",
    "bhutan": "Bhutan", "bhutanu": "Bhutan", "bhutanem": "Bhutan",
    "birma": "Myanmar", "birmy": "Myanmar", "birmie": "Myanmar", "birmę": "Myanmar", "birmą": "Myanmar", "mjanma": "Myanmar", "mjanmy": "Myanmar", "mjanmą": "Myanmar",
    "tajlandia": "Thailand", "tajlandii": "Thailand", "tajlandię": "Thailand", "tajlandią": "Thailand",
    "kambodża": "Cambodia", "kambodży": "Cambodia", "kambodżę": "Cambodia", "kambodżą": "Cambodia", "kambodza": "Cambodia",
    "laos": "Laos", "laosu": "Laos", "laosem": "Laos",
    "wietnam": "Vietnam", "wietnamu": "Vietnam", "wietnamem": "Vietnam",
    "malezja": "Malaysia", "malezji": "Malaysia", "malezję": "Malaysia", "malezją": "Malaysia",
    "singapur": "Singapore", "singapuru": "Singapore", "singapurem": "Singapore",
    "brunei": "Brunei",
    "indonezja": "Indonesia", "indonezji": "Indonesia", "indonezję": "Indonesia", "indonezją": "Indonesia",
    "filipiny": "Philippines", "filipin": "Philippines", "filipinom": "Philippines", "filipinami": "Philippines", "filipinach": "Philippines",
    "timor wschodni": "East Timor", "timoru wschodniego": "East Timor",

    # Americas
    "stany zjednoczone": "United States", "stanów zjednoczonych": "United States", "stanom zjednoczonym": "United States", "stanami zjednoczonymi": "United States", "stanach zjednoczonych": "United States", "usa": "United States", "ameryka": "United States",
    "kanada": "Canada", "kanady": "Canada", "kanadzie": "Canada", "kanadę": "Canada", "kanadą": "Canada",
    "meksyk": "Mexico", "meksyku": "Mexico", "meksykiem": "Mexico",
    "gwatemala": "Guatemala", "gwatemali": "Guatemala", "gwatemalę": "Guatemala", "gwatemalą": "Guatemala",
    "belize": "Belize",
    "salwador": "El Salvador", "salwadoru": "El Salvador", "salwadorem": "El Salvador",
    "honduras": "Honduras", "hondurasu": "Honduras", "hondurasem": "Honduras",
    "nikaragua": "Nicaragua", "nikaragui": "Nicaragua", "nikaraguę": "Nicaragua", "nikaraguą": "Nicaragua",
    "kostaryka": "Costa Rica", "kostaryki": "Costa Rica", "kostarykę": "Costa Rica", "kostaryką": "Costa Rica",
    "panama": "Panama", "panamy": "Panama", "panamie": "Panama", "panamę": "Panama", "panamą": "Panama",
    "kuba": "Cuba", "kuby": "Cuba", "kubie": "Cuba", "kubę": "Cuba", "kubą": "Cuba",
    "jamajka": "Jamaica", "jamajki": "Jamaica", "jamajce": "Jamaica", "jamajkę": "Jamaica", "jamajką": "Jamaica",
    "haiti": "Haiti",
    "dominikana": "Dominican Republic", "dominikany": "Dominican Republic", "dominikanie": "Dominican Republic", "dominikanę": "Dominican Republic", "dominikaną": "Dominican Republic",
    "bahamy": "Bahamas", "bahamów": "Bahamas", "bahamach": "Bahamas",
    "dominika": "Dominica", "dominiki": "Dominica", "dominikę": "Dominica", "dominiką": "Dominica",
    "barbados": "Barbados", "barbadosu": "Barbados",
    "grenada": "Grenada", "grenady": "Grenada", "grenadą": "Grenada",
    "antigua i barbuda": "Antigua and Barbuda", "antigua": "Antigua and Barbuda",
    "saint kitts i nevis": "Saint Kitts and Nevis", "saint kitts": "Saint Kitts and Nevis",
    "saint lucia": "Saint Lucia",
    "saint vincent i grenadyny": "Saint Vincent and the Grenadines", "saint vincent": "Saint Vincent and the Grenadines",
    "kolumbia": "Colombia", "kolumbii": "Colombia", "kolumbię": "Colombia", "kolumbią": "Colombia",
    "wenezuela": "Venezuela", "wenezueli": "Venezuela", "wenezuelę": "Venezuela", "wenezuelą": "Venezuela",
    "gujana": "Guyana", "gujany": "Guyana", "gujaną": "Guyana",
    "surinam": "Suriname", "surinamu": "Suriname", "surinamem": "Suriname",
    "brazylia": "Brazil", "brazylii": "Brazil", "brazylię": "Brazil", "brazylią": "Brazil",
    "ekwador": "Ecuador", "ekwadoru": "Ecuador", "ekwadorem": "Ecuador",
    "peru": "Peru",
    "boliwia": "Bolivia", "boliwii": "Bolivia", "boliwię": "Bolivia", "bolowią": "Bolivia",
    "paragwaj": "Paraguay", "paragwaju": "Paraguay", "paragwajem": "Paraguay",
    "chile": "Chile",
    "argentyna": "Argentina", "argentyny": "Argentina", "argentynie": "Argentina", "argentynę": "Argentina", "argentyną": "Argentina",
    "urugwaj": "Uruguay", "urugwaju": "Uruguay", "urugwajem": "Uruguay",
    "trynidad i tobago": "Trinidad and Tobago", "trynidad": "Trinidad and Tobago",

    # Africa
    "egipt": "Egypt", "egiptu": "Egypt", "egipcie": "Egypt", "egiptem": "Egypt",
    "libia": "Libya", "libii": "Libya", "libię": "Libya", "libią": "Libya",
    "tunezja": "Tunisia", "tunezji": "Tunisia", "tunezję": "Tunisia", "tunezją": "Tunisia",
    "algieria": "Algeria", "algierii": "Algeria", "algierię": "Algeria", "algierią": "Algeria",
    "maroko": "Morocco", "maroka": "Morocco", "marokiem": "Morocco",
    "mauretania": "Mauritania", "mauretanii": "Mauritania", "mauretanię": "Mauritania", "mauretanią": "Mauritania",
    "sudan": "Sudan", "sudanu": "Sudan", "sudanem": "Sudan",
    "sudan południowy": "South Sudan", "sudanu południowego": "South Sudan", "sudan poludniowy": "South Sudan",
    "czad": "Chad", "czadu": "Chad", "czadem": "Chad",
    "niger": "Niger", "nigru": "Niger", "nigrem": "Niger",
    "mali": "Mali",
    "etiopia": "Ethiopia", "etiopii": "Ethiopia", "etiopię": "Ethiopia", "etiopią": "Ethiopia",
    "somalia": "Somalia", "somalii": "Somalia", "somalię": "Somalia", "somalią": "Somalia",
    "dżibuti": "Djibouti", "dzibuti": "Djibouti",
    "erytrea": "Eritrea", "erytrei": "Eritrea", "erytreę": "Eritrea", "erytreą": "Eritrea",
    "kenia": "Kenya", "kenii": "Kenya", "kenię": "Kenya", "kenią": "Kenya",
    "uganda": "Uganda", "ugandy": "Uganda", "ugandę": "Uganda", "ugandą": "Uganda",
    "tanzania": "Tanzania", "tanzanii": "Tanzania", "tanzanię": "Tanzania", "tanzanią": "Tanzania",
    "rwanda": "Rwanda", "rwandy": "Rwanda", "rwandę": "Rwanda", "rwandą": "Rwanda",
    "burundi": "Burundi",
    "demokratyczna republika konga": "Democratic Republic of the Congo", "drk": "Democratic Republic of the Congo", "drc": "Democratic Republic of the Congo",
    "republika konga": "Republic of the Congo", "kongo": "Republic of the Congo",
    "republika środkowoafrykańska": "Central African Republic", "rca": "Central African Republic", "republika srodkowoafrykanska": "Central African Republic",
    "kamerun": "Cameroon", "kamerunu": "Cameroon", "kamerunem": "Cameroon",
    "nigeria": "Nigeria", "nigerii": "Nigeria", "nigerię": "Nigeria", "nigerią": "Nigeria",
    "benin": "Benin", "beninu": "Benin",
    "togo": "Togo",
    "ghana": "Ghana", "ghany": "Ghana", "ghaną": "Ghana",
    "wybrzeże kości słoniowej": "Ivory Coast", "wybrzeze kosci sloniowej": "Ivory Coast",
    "liberia": "Liberia", "liberii": "Liberia", "liberię": "Liberia", "liberią": "Liberia",
    "sierra leone": "Sierra Leone",
    "gwinea": "Guinea", "gwinei": "Guinea", "gwineę": "Guinea", "gwineą": "Guinea",
    "gwinea bissau": "Guinea-Bissau", "gwinea-bissau": "Guinea-Bissau",
    "senegal": "Senegal", "senegalu": "Senegal", "senegalem": "Senegal",
    "gambia": "Gambia", "gambii": "Gambia", "gambię": "Gambia", "gambią": "Gambia",
    "gwinea równikowa": "Equatorial Guinea", "gwinea rownikowa": "Equatorial Guinea",
    "gabon": "Gabon", "gabonu": "Gabon", "gabonem": "Gabon",
    "angola": "Angola", "angoli": "Angola", "angolę": "Angola", "angolą": "Angola",
    "zambia": "Zambia", "zambii": "Zambia", "zambię": "Zambia", "zambią": "Zambia",
    "zimbabwe": "Zimbabwe",
    "malawi": "Malawi",
    "mozambik": "Mozambique", "mozambiku": "Mozambique", "mozambikiem": "Mozambique",
    "madagaskar": "Madagascar", "madagaskaru": "Madagascar", "madagaskarem": "Madagascar",
    "namibia": "Namibia", "namibii": "Namibia", "namibię": "Namibia", "namibią": "Namibia",
    "botswana": "Botswana", "botswany": "Botswana", "botswanę": "Botswana", "botswaną": "Botswana",
    "rpa": "South Africa", "republika południowej afryki": "South Africa", "południowa afryka": "South Africa", "republika poludniowej afryki": "South Africa", "poludniowa afryka": "South Africa",
    "lesotho": "Lesotho",
    "eswatini": "Eswatini", "suazi": "Eswatini",
    "seszele": "Seychelles", "seszeli": "Seychelles",
    "mauritius": "Mauritius",
    "komory": "Comoros", "komorów": "Comoros",
    "zielony przylądek": "Cape Verde", "republika zielonego przylądka": "Cape Verde", "wyspy zielonego przylądka": "Cape Verde", "zielony przyladek": "Cape Verde",
    "burkina faso": "Burkina Faso",
    "wyspy świętego tomasza i książęca": "São Tomé and Príncipe", "wyspy swietego tomasza i ksiazeca": "São Tomé and Príncipe", "sao tome": "São Tomé and Príncipe",

    # Oceania
    "australia": "Australia", "australii": "Australia", "australię": "Australia", "australią": "Australia",
    "nowa zelandia": "New Zealand", "nowej zelandii": "New Zealand", "nową zelandię": "New Zealand", "nową zelandią": "New Zealand",
    "papua nowa gwinea": "Papua New Guinea", "papua-nowa gwinea": "Papua New Guinea", "papua": "Papua New Guinea",
    "fidżi": "Fiji", "fidzi": "Fiji",
    "wyspy salomona": "Solomon Islands",
    "vanuatu": "Vanuatu",
    "samoa": "Samoa",
    "tonga": "Tonga",
    "kiribati": "Kiribati",
    "tuvalu": "Tuvalu",
    "nauru": "Nauru",
    "palau": "Palau",
    "wyspy marshalla": "Marshall Islands",
    "mikronezja": "Federated States of Micronesia", "mikronezji": "Federated States of Micronesia", "mikronezją": "Federated States of Micronesia", "mikronezję": "Federated States of Micronesia",
}

COUNTRY_NAME_SYNONYMS = {
    "antigua": "Antigua and Barbuda",
    "saint kitts": "Saint Kitts and Nevis",
    "saint vincent": "Saint Vincent and the Grenadines",
    "trinidad": "Trinidad and Tobago",
    "tobago": "Trinidad and Tobago",
    "bosnia": "Bosnia and Herzegovina",
    "bosni": "Bosnia and Herzegovina",
    "bosnie": "Bosnia and Herzegovina",
    "bosnia herzegovina": "Bosnia and Herzegovina",
    "bosnia-herzegovina": "Bosnia and Herzegovina",
    "bosnia i hercegowina": "Bosnia and Herzegovina",
    "drc": "Democratic Republic of the Congo",
    "the drc": "Democratic Republic of the Congo",
    "dr congo": "Democratic Republic of the Congo",
    "democratic republic of congo": "Democratic Republic of the Congo",
    "demokratyczna republika konga": "Democratic Republic of the Congo",
    "drk": "Democratic Republic of the Congo",
    "congo kinshasa": "Democratic Republic of the Congo",
    "congo-kinshasa": "Democratic Republic of the Congo",
    "congo brazzaville": "Republic of the Congo",
    "congo-brazzaville": "Republic of the Congo",
    "congo republic": "Republic of the Congo",
    "republic of the congo": "Republic of the Congo",
    "republic of congo": "Republic of the Congo",
    "republika konga": "Republic of the Congo",
    "czechia": "Czech Republic",
    "czech republic": "Czech Republic",
    "timor-leste": "East Timor",
    "timor leste": "East Timor",
    "east timor": "East Timor",
    "gambia": "Gambia",
    "the gambia": "Gambia",
    "gambia the": "Gambia",
    "bahamas": "Bahamas",
    "the bahamas": "Bahamas",
    "netherlands": "Netherlands",
    "the netherlands": "Netherlands",
    "holland": "Netherlands",
    "philippines": "Philippines",
    "the philippines": "Philippines",
    "usa": "United States",
    "us": "United States",
    "america": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "uae": "United Arab Emirates",
    "the uae": "United Arab Emirates",
    "emirates": "United Arab Emirates",
    "car": "Central African Republic",
    "cote d ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "côte d'ivoire": "Ivory Coast",
    "côte d ivoire": "Ivory Coast",
    "micronesia": "Federated States of Micronesia",
    "fsm": "Federated States of Micronesia",
    "vatican": "Vatican City",
    "vatican city": "Vatican City",
    "holy see": "Vatican City",
    "cabo verde": "Cape Verde",
    "cape verde": "Cape Verde",
    "swaziland": "Eswatini",
    "eswatini": "Eswatini",
    "burma": "Myanmar",
    "myanmar": "Myanmar",
    "macedonia": "North Macedonia",
    "north macedonia": "North Macedonia",
    "sao tome": "São Tomé and Príncipe",
    "sao tome and principe": "São Tomé and Príncipe",
    "são tomé and príncipe": "São Tomé and Príncipe",
    "sao tome & principe": "São Tomé and Príncipe",
    "png": "Papua New Guinea",
    "papua new guinea": "Papua New Guinea",
    "solomons": "Solomon Islands",
    "solomon islands": "Solomon Islands",
    "russian federation": "Russia",
    "russia": "Russia",
    "syrian arab republic": "Syria",
    "syria": "Syria",
    "lao pdr": "Laos",
    "laos": "Laos",
    "brunei darussalam": "Brunei",
    "brunei": "Brunei",
    "viet nam": "Vietnam",
    "vietnam": "Vietnam",
    "south africa": "South Africa",
    "rsa": "South Africa",
    "nz": "New Zealand",
}
CURRENCY_ALIASES = {
    "us dollar": "united states dollar",
    "us dollars": "united states dollar",
    "usd": "united states dollar",
    "dollar": "united states dollar",
    "dolar": "united states dollar",
    "dolar amerykanski": "united states dollar",
    "dolarze": "united states dollar",
    "dolarach": "united states dollar",
    "euro": "euro",
    "eur": "euro",
    "polish zloty": "polish zloty",
    "zloty": "polish zloty",
    "pln": "polish zloty",
    "zlote": "polish zloty",
    "zlotych": "polish zloty",
    "pound": "british pound",
    "british pound": "british pound",
    "gbp": "british pound",
    "funt": "british pound",
}

HEMISPHERE_ALIASES = {
    "northern": "northern",
    "north": "northern",
    "polnocna": "northern",
    "polnocnej": "northern",
    "southern": "southern",
    "south": "southern",
    "poludniowa": "southern",
    "poludniowej": "southern",
    "eastern": "eastern",
    "east": "eastern",
    "wschodnia": "eastern",
    "wschodniej": "eastern",
    "western": "western",
    "west": "western",
    "zachodnia": "western",
    "zachodniej": "western",
}
RELIGION_ALIASES = {
    "catholicism": "catholic",
    "katolicyzm": "catholic",
    "protestantism": "protestant",
    "protestantyzm": "protestant",
    "orthodoxy": "orthodox",
    "prawoslawie": "orthodox",
    "christianity": "christian",
    "chrzescijanstwo": "christian",
    "islam": "islam",
    "sunni": "sunni",
    "shia": "shia",
    "judaism": "jewish",
    "hinduism": "hindu",
    "buddhism": "buddhist",
}

def normalize_hemisphere(val: Any) -> str:
    cleaned = re.sub(r"\b(hemisphere|polkula|polkuli|polkule)\b", "", normalize_value(val)).strip()
    return HEMISPHERE_ALIASES.get(cleaned, cleaned)


def canonical_country_name(name: Any) -> str:
    clean = normalize(str(name or ""))
    mapped = COUNTRY_NAME_SYNONYMS.get(clean, clean)
    return normalize(mapped)


from utils.water_hierarchy import (
    WATER_BODY_PARENT_MAP,
    INLAND_WATER_BODIES,
    is_marine_water_body,
    get_water_body_parents,
    expand_water_bodies,
    is_multi_ocean_question,
    get_distinct_oceans,
)
VALUE_ALIASES = {
    "baltyk": "Baltic Sea",
    "morze baltyckie": "Baltic Sea",
    "morza baltyckiego": "Baltic Sea",
    "baltyckiego": "Baltic Sea",
    "baltykiem": "Baltic Sea",
    "baltyku": "Baltic Sea",
    "adriatyk": "Adriatic Sea",
    "adriatyku": "Adriatic Sea",
    "morze adriatyckie": "Adriatic Sea",
    "morza adriatyckiego": "Adriatic Sea",
    "morzem adriatyckim": "Adriatic Sea",
    "morzu adriatyckim": "Adriatic Sea",
    "srodziemne": "Mediterranean Sea",
    "srodziemnego": "Mediterranean Sea",
    "morze srodziemne": "Mediterranean Sea",
    "morza srodziemnego": "Mediterranean Sea",
    "morzem srodziemnym": "Mediterranean Sea",
    "morzu srodziemnym": "Mediterranean Sea",
    "czarne": "Black Sea",
    "czarnego": "Black Sea",
    "morze czarne": "Black Sea",
    "morza czarnego": "Black Sea",
    "morzem czarnym": "Black Sea",
    "morzu czarnym": "Black Sea",
    "czerwone": "Red Sea",
    "czerwonego": "Red Sea",
    "morze czerwone": "Red Sea",
    "morza czerwonego": "Red Sea",
    "morzem czerwonym": "Red Sea",
    "morzu czerwonym": "Red Sea",
    "polnocne": "North Sea",
    "polnocnego": "North Sea",
    "morze polnocne": "North Sea",
    "morza polnocnego": "North Sea",
    "morzem polnocnym": "North Sea",
    "morzu polnocnym": "North Sea",
    "atlantyk": "Atlantic Ocean",
    "ocean atlantycki": "Atlantic Ocean",
    "pacyfik": "Pacific Ocean",
    "ocean spokojny": "Pacific Ocean",
    "ocean indyjski": "Indian Ocean",
    "wisla": "Vistula",
    "wisle": "Vistula",
    "odra": "Oder",
    "odrze": "Oder",
    "dunaj": "Danube",
    "ren": "Rhine",
    "nil": "Nile",
    "amazonka": "Amazon",
    "euro": "Euro",
    "us dollar": "United States dollar",
    "us dollars": "United States dollar",
    "usd": "United States dollar",
    "dollar": "United States dollar",
    "dollars": "United States dollar",
    "the dollar": "United States dollar",
    "dolar": "United States dollar",
    "dolar amerykanski": "United States dollar",
    "zloty": "Polish złoty",
    "polski": "Polish",
    "po polsku": "Polish",
    "polsku": "Polish",
    "angielski": "English",
    "niemiecki": "German",
    "francuski": "French",
    "hiszpanski": "Spanish",
    "arabski": "Arabic",
    "rosyjski": "Russian",
    "po rosyjsku": "Russian",
    "ukrainski": "Ukrainian",
    "po ukrainsku": "Ukrainian",
    "katalonski": "Catalan",
    "po katalonsku": "Catalan",
    "baskijski": "Basque",
    "po baskijsku": "Basque",
    "galicyjski": "Galician",
    "irlandzki": "Irish",
    "szwedzki": "Swedish",
    "wloski": "Italian",
    "portugalski": "Portuguese",
    "chinski": "Chinese",
    "mandarynski": "Mandarin",
    "czerwony": "red",
    "czerwona": "red",
    "czerwone": "red",
    "czerwonym": "red",
    "bialy": "white",
    "biały": "white",
    "biale": "white",
    "białe": "white",
    "biel": "white",
    "niebieski": "blue",
    "niebieska": "blue",
    "niebieskie": "blue",
    "błękitny": "blue",
    "blekitny": "blue",
    "zielony": "green",
    "zielona": "green",
    "zielone": "green",
    "żółty": "yellow",
    "zolty": "yellow",
    "żółta": "yellow",
    "zolta": "yellow",
    "czarny": "black",
    "czarna": "black",
    "czarne": "black",
    "pomarańczowy": "orange",
    "pomaranczowy": "orange",
    "gwiazda": "star",
    "gwiazdy": "star",
    "gwiazdę": "star",
    "gwiazde": "star",
    "krzyż": "cross",
    "krzyz": "cross",
    "półksiężyc": "crescent",
    "polksiezyc": "crescent",
    "słońce": "sun",
    "slonce": "sun",
    "pasy": "stripes",
    "paski": "stripes",
    "orzeł": "eagle",
    "orzel": "eagle",
    "godło": "coat_of_arms",
    "godlo": "coat_of_arms",
    "koło": "circle",
    "kolo": "circle",
    "zsrr": "USSR",
    "zwiazek radziecki": "USSR",
    "związek radziecki": "USSR",
    "jugoslawia": "Yugoslavia",
    "jugosławia": "Yugoslavia",
    "czechoslowacja": "Czechoslovakia",
    "czechosłowacja": "Czechoslovakia",
    "wielka kolumbia": "Gran Colombia",
    "uklad warszawski": "Warsaw Pact",
    "układ warszawski": "Warsaw Pact",
    "imperium brytyjskie": "British Empire",
    "kolonia brytyjska": "British Empire",
}


ORG_ALIASES = {
    "european union": "EU",
    "the european union": "EU",
    "unia europejska": "EU",
    "ue": "EU",
    "eu": "EU",
    "nato": "NATO",
    "onz": "UN",
    "un": "UN",
    "united nations": "UN",
    "the united nations": "UN",
    "narody zjednoczone": "UN",
    "g7": "G7",
    "the g7": "G7",
    "group of seven": "G7",
    "g20": "G20",
    "the g20": "G20",
    "group of twenty": "G20",
    "oecd": "OECD",
    "the oecd": "OECD",
    "ocde": "OECD",
    "wto": "WTO",
    "the wto": "WTO",
    "schengen": "Schengen",
    "schengen area": "Schengen",
    "schengen zone": "Schengen",
    "strefa schengen": "Schengen",
    "commonwealth": "Commonwealth",
    "commonwealth of nations": "Commonwealth",
    "african union": "AU",
    "the african union": "AU",
    "unia afrykanska": "AU",
    "asean": "ASEAN",
    "opec": "OPEC",
    "brics": "BRICS",
}


RELIGION_ALIASES = {
    "catholicism": "Catholic",
    "katolicyzm": "Catholic",
    "katolicka": "Catholic",
    "katolicki": "Catholic",
    "orthodoxy": "Orthodox",
    "prawoslawie": "Orthodox",
    "protestantism": "Protestant",
    "protestantyzm": "Protestant",
    "chrzescijanstwo": "Christianity",
    "catholic": "Catholic",
    "roman catholic": "Catholic",
    "orthodox": "Orthodox",
    "protestant": "Protestant",
    "christian": "Christianity",
    "christianity": "Christianity",
    "islam": "Islam",
    "muslim": "Islam",
    "judaism": "Judaism",
    "jewish": "Judaism",
    "buddhism": "Buddhism",
    "buddhist": "Buddhism",
    "hinduism": "Hinduism",
    "hindu": "Hinduism",
    "folk religion": "Folk/Traditional religions",
    "traditional religion": "Folk/Traditional religions",
    "no religion": "No religion",
    "atheist": "No religion",
    "atheism": "No religion",
    "mixed": "Mixed",
}


GOVERNMENT_TYPE_ALIASES = {
    "republic": "Republic",
    "parliamentary republic": "Republic",
    "presidential republic": "Republic",
    "federal republic": "Republic",
    "democracy": "Republic",
    "parliamentary democracy": "Republic",
    "federation": "Republic",
    "federal": "Republic",
    "monarchy": "Monarchy",
    "constitutional monarchy": "Monarchy",
    "absolute monarchy": "Monarchy",
    "kingdom": "Monarchy",
    "emirate": "Monarchy",
    "sultanate": "Monarchy",
    "theocracy": "Theocracy",
    "communist": "Communist state",
    "communist state": "Communist state",
    "military junta": "Military junta",
    "junta": "Military junta",
    "transitional": "Transitional government",
}


CONTINENT_ALIASES = {
    "europa": "Europe",
    "europie": "Europe",
    "europe": "Europe",
    "azja": "Asia",
    "azji": "Asia",
    "asia": "Asia",
    "afryka": "Africa",
    "afryce": "Africa",
    "africa": "Africa",
    "ameryka polnocna": "North America",
    "ameryce polnocnej": "North America",
    "north america": "North America",
    "ameryka poludniowa": "South America",
    "ameryce poludniowej": "South America",
    "south america": "South America",
    "ameryki": "Americas",
    "amerykach": "Americas",
    "ameryk": "Americas",
    "ameryce": "Americas",
    "ameryka": "Americas",
    "americas": "Americas",
    "oceania": "Oceania",
    "antarktyda": "Antarctica",
    "antarctica": "Antarctica",
}


REGION_ALIASES = {
    "europe": "Europe",
    "asia": "Asia",
    "africa": "Africa",
    "americas": "Americas",
    "ameryki": "Americas",
    "amerykach": "Americas",
    "ameryk": "Americas",
    "ameryce": "Americas",
    "ameryka": "Americas",
    "north america": "Americas",
    "south america": "Americas",
    "oceania": "Oceania",
}


SUBREGION_ALIASES = {
    "central europe": "Central Europe",
    "eastern europe": "Eastern Europe",
    "western europe": "Western Europe",
    "northern europe": "Northern Europe",
    "southern europe": "Southern Europe",
    "southeast europe": "Southeast Europe",
    "east europe": "Eastern Europe",
    "north europe": "Northern Europe",
    "south europe": "Southern Europe",
    "east asia": "Eastern Asia",
    "west asia": "Western Asia",
    "south asia": "Southern Asia",
    "east africa": "Eastern Africa",
    "north africa": "Northern Africa",
    "west africa": "Western Africa",
    "eastern asia": "Eastern Asia",
    "western asia": "Western Asia",
    "southern asia": "Southern Asia",
    "southeast asia": "South-Eastern Asia",
    "south eastern asia": "South-Eastern Asia",
    "south-eastern asia": "South-Eastern Asia",
    "central asia": "Central Asia",
    "central africa": "Middle Africa",
    "caribean": "Caribbean",
    "caribbean": "Caribbean",
    "central america": "Central America",
    "north america": "North America",
    "south america": "South America",
    "middle east": "Middle East",
    "scandinavia": "Scandinavia",
    "baltic states": "Baltic states",
    "baltics": "Baltic states",
    "balkans": "Balkans",
    "iberia": "Iberia",
    "iberian peninsula": "Iberian Peninsula",
    "mediterranean": "Mediterranean",
    "eastern africa": "Eastern Africa",
    "middle africa": "Middle Africa",
    "northern africa": "Northern Africa",
    "southern africa": "Southern Africa",
    "western africa": "Western Africa",
    "melanesia": "Melanesia",
    "micronesia": "Micronesia",
    "polynesia": "Polynesia",
    "australia and new zealand": "Australia and New Zealand",
    # Polish regional aliases
    "bliski wschod": "Middle East",
    "bliskim wschodzie": "Middle East",
    "bliskiego wschodu": "Middle East",
    "bliskiemu wschodowi": "Middle East",
    "balkany": "Balkans",
    "balkanach": "Balkans",
    "balkanow": "Balkans",
    "balkanami": "Balkans",
    "polwysep balkanski": "Balkans",
    "polwyspie balkanskim": "Balkans",
    "skandynawia": "Scandinavia",
    "skandynawii": "Scandinavia",
    "kraj nordycki": "Nordic countries",
    "kraje nordyckie": "Nordic countries",
    "krajow nordyckich": "Nordic countries",
    "nordycki": "Nordic countries",
    "nordyckie": "Nordic countries",
    "kraj baltycki": "Baltic states",
    "kraje baltyckie": "Baltic states",
    "panstwa baltyckie": "Baltic states",
    "krajach baltyckich": "Baltic states",
    "baltycki": "Baltic states",
    "karaiby": "Caribbean",
    "karaibach": "Caribbean",
    "karaibow": "Caribbean",
    "karaibami": "Caribbean",
    "polwysep iberyjski": "Iberian Peninsula",
    "polwyspie iberyjskim": "Iberian Peninsula",
    "polwyspu iberyjskiego": "Iberian Peninsula",
    "iberii": "Iberian Peninsula",
    "benelux": "Benelux",
    "beneluks": "Benelux",
    "beneluksu": "Benelux",
    "rog afryki": "Horn of Africa",
    "rogu afryki": "Horn of Africa",
    "wyspy brytyjskie": "British Isles",
    "wyspach brytyjskich": "British Isles",
    "ameryka srodkowa": "Central America",
    "ameryce srodkowej": "Central America",
    "ameryki srodkowej": "Central America",
    "ameryka polnocna": "North America",
    "ameryce polnocnej": "North America",
    "ameryki polnocnej": "North America",
    "ameryka poludniowa": "South America",
    "ameryce poludniowej": "South America",
    "ameryki poludniowej": "South America",
    "europa srodkowa": "Central Europe",
    "europie srodkowej": "Central Europe",
    "europy srodkowej": "Central Europe",
    "europa wschodnia": "Eastern Europe",
    "europie wschodniej": "Eastern Europe",
    "europy wschodniej": "Eastern Europe",
    "europa zachodnia": "Western Europe",
    "europie zachodniej": "Western Europe",
    "europy zachodniej": "Western Europe",
    "europa poludniowa": "Southern Europe",
    "europie poludniowej": "Southern Europe",
    "europy poludniowej": "Southern Europe",
    "europa polnocna": "Northern Europe",
    "europie polnocnej": "Northern Europe",
    "europy polnocnej": "Northern Europe",
    "azja poludniowo wschodnia": "South-Eastern Asia",
    "azji poludniowo wschodniej": "South-Eastern Asia",
    "azja poludniowowschodnia": "South-Eastern Asia",
    "azji poludniowowschodniej": "South-Eastern Asia",
    "azja wschodnia": "Eastern Asia",
    "azji wschodniej": "Eastern Asia",
    "azja poludniowa": "Southern Asia",
    "azji poludniowej": "Southern Asia",
    "azja centralna": "Central Asia",
    "azji centralnej": "Central Asia",
    "azja srodkowa": "Central Asia",
    "azji srodkowej": "Central Asia",
}


GEOGRAPHIC_SUBREGION_PARENT_MAP: dict[str, set[str]] = {
    # Middle East
    "Arabian Peninsula": {"Middle East", "Western Asia", "Asia"},
    "Levant": {"Middle East", "Western Asia", "Asia"},
    "Persian Gulf": {"Middle East"},

    # Europe
    "Scandinavia": {"Nordic countries", "Northern Europe", "Europe"},
    "Nordic countries": {"Northern Europe", "Europe"},
    "Baltic states": {"Northern Europe", "Europe"},
    "Benelux": {"Western Europe", "Europe"},
    "British Isles": {"Northern Europe", "Europe"},
    "Iberia": {"Iberian Peninsula", "Southern Europe", "Europe"},
    "Iberian Peninsula": {"Southern Europe", "Europe"},
    "Balkans": {"Southeast Europe", "Southern Europe", "Europe"},
    "Central Europe": {"Europe"},
    "Eastern Europe": {"Europe"},
    "Western Europe": {"Europe"},
    "Northern Europe": {"Europe"},
    "Southern Europe": {"Europe"},
    "Southeast Europe": {"Balkans", "Southern Europe", "Europe"},

    # Americas
    "Central America": {"North America", "Americas"},
    "Caribbean": {"North America", "Americas"},
    "North America": {"Americas"},
    "South America": {"Americas"},

    # Asia
    "South-Eastern Asia": {"Southeast Asia", "Asia"},
    "Southeast Asia": {"Asia"},
    "Eastern Asia": {"East Asia", "Asia"},
    "East Asia": {"Asia"},
    "Southern Asia": {"South Asia", "Asia"},
    "South Asia": {"Asia"},
    "Central Asia": {"Asia"},
    "Western Asia": {"Asia"},
    "Indian subcontinent": {"South Asia", "Asia"},

    # Africa
    "Maghreb": {"Northern Africa", "North Africa", "Africa"},
    "Horn of Africa": {"Eastern Africa", "East Africa", "Africa"},
    "Sahel": {"Africa"},
    "Northern Africa": {"North Africa", "Africa"},
    "Eastern Africa": {"East Africa", "Africa"},
    "Western Africa": {"West Africa", "Africa"},
    "Middle Africa": {"Central Africa", "Africa"},
    "Southern Africa": {"Africa"},
}


def expand_geographic_areas(areas: Iterable[str]) -> set[str]:
    """Compute transitive parent regions and continents for a collection of areas."""
    expanded = set(areas)
    queue = list(areas)
    while queue:
        item = queue.pop(0)
        if item in GEOGRAPHIC_SUBREGION_PARENT_MAP:
            for parent in GEOGRAPHIC_SUBREGION_PARENT_MAP[item]:
                if parent not in expanded:
                    expanded.add(parent)
                    queue.append(parent)
    return expanded


GEOGRAPHIC_AREA_ALIASES = {
    **SUBREGION_ALIASES,
    **REGION_ALIASES,
}


def normalize(text: str, *, preserve_separators: bool = False) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    if preserve_separators:
        return text
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(normalized_question: str, phrase: str) -> bool:
    phrase_norm = normalize(phrase)
    return bool(re.search(rf"(^|\s){re.escape(phrase_norm)}($|\s)", normalized_question))


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def first_mentioned_value(
    normalized_question: str,
    values: Iterable[str],
    aliases: dict[str, str] | None = None,
) -> str | None:
    aliases = aliases or {}
    for alias, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if contains_phrase(normalized_question, alias):
            return canonical
    candidates = sorted(set(values), key=len, reverse=True)
    for value in candidates:
        if value and contains_phrase(normalized_question, value):
            return value
    return None


def yes_no_question(normalized_question: str) -> bool:
    return (
        normalized_question.startswith(("czy ", "is ", "are ", "does ", "do ", "has ", "have ", "can ", "below ", "above ", "over ", "under "))
        or "?" in normalized_question
    )


class LocalCountryFacts:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def try_answer(self, original_question: str, country_name: str) -> LocalAnswer | None:
        if not self.db_path.exists():
            return None

        q = normalize(original_question)
        if not yes_no_question(q):
            return None


        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            country = conn.execute(
                "SELECT * FROM countries WHERE app_country_name = ?", (country_name,)
            ).fetchone()
            if country is None:
                return None

            handlers = (
                self._answer_border,
                self._answer_geographic_area,
                self._answer_subregion,
                self._answer_continent,
                self._answer_region,
                self._answer_water_access,
                self._answer_island,
                self._answer_capital,
                self._answer_currency,
                self._answer_language,
                self._answer_dominant_religion,
                self._answer_government_type,
                self._answer_membership,
                self._answer_population_or_area,
                self._answer_coordinates,
                self._answer_river,
                self._answer_driving_side,
                self._answer_name_pattern,
            )
            for handler in handlers:
                answer = handler(conn, country, original_question, q)
                if answer is not None:
                    return answer
        return None

    def _target_country(self, conn: sqlite3.Connection, q: str) -> str | None:
        names = [r[0] for r in conn.execute("SELECT app_country_name FROM countries")]
        combined_aliases = {**POLISH_COUNTRY_ALIASES, **COUNTRY_NAME_SYNONYMS}
        return first_mentioned_value(q, names, combined_aliases)
    def _answer_border(self, conn, country, original, q):
        if not any(word in q for word in ("border", "borders", "neighbor", "neighbour", "granic", "sasiad")):
            return None
        target = self._target_country(conn, q)
        if not target:
            return None
        if target == country["app_country_name"] or canonical_country_name(target) == canonical_country_name(country["app_country_name"]):
            answer = True
        else:
            borders = {
                canonical_country_name(r[0])
                for r in conn.execute(
                    """
                    SELECT border_country_name FROM country_borders WHERE country_id=?
                    UNION
                    SELECT c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3 WHERE cb.country_id=?
                    """,
                    (country["id"], country["id"]),
                )
            }
            answer = canonical_country_name(target) in borders
        return LocalAnswer(
            question=f"Does the country border {target}?",
            answer=answer,
            explanation=f"{country['app_country_name']} {'borders' if answer else 'does not border'} {target}.",
            relation="borders_country",
        )

    def _answer_continent(self, conn, country, original, q):
        if not any(
            word in q
            for word in (
                "continent",
                "kontynent",
                "europ",
                "europe",
                "azj",
                "asia",
                "afryk",
                "africa",
                "america",
                "americ",
                "oceani",
                "oceania",
            )
        ):
            return None
        target = first_mentioned_value(q, CONTINENT_ALIASES.values(), CONTINENT_ALIASES)
        if not target:
            return None
        continents = {r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id=?", (country["id"],))}
        if target == "Americas":
            answer = bool(continents & {"North America", "South America"})
            explanation = f"{country['app_country_name']} is listed under these continents: {', '.join(sorted(continents))}."
            return LocalAnswer(
                question="Is the country in the Americas?",
                answer=answer,
                explanation=explanation,
                relation="continent",
            )
        answer = target in continents
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"{country['app_country_name']} is listed under these continents: {', '.join(sorted(continents))}.",
            relation="continent",
        )

    def _answer_geographic_area(self, conn, country, original, q):
        region_values = [r[0] for r in conn.execute("SELECT DISTINCT region_name FROM country_regions")]
        subregion_values = [r[0] for r in conn.execute("SELECT DISTINCT subregion_name FROM country_subregions")]
        target = first_mentioned_value(q, [*region_values, *subregion_values], GEOGRAPHIC_AREA_ALIASES)
        if not target:
            return None
        country_regions = {
            r[0]
            for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))
        }
        country_subregions = {
            r[0]
            for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))
        }
        country_areas = country_regions | country_subregions
        all_areas = expand_geographic_areas(country_areas)
        answer = any(normalize(area) == normalize(target) for area in all_areas)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Geographic areas for {country['app_country_name']}: {', '.join(sorted(country_areas))}.",
            relation="geographic_area",
        )

    def _answer_region(self, conn, country, original, q):
        if "subregion" in q:
            return None
        regions = [r[0] for r in conn.execute("SELECT DISTINCT region_name FROM country_regions")]
        target = first_mentioned_value(q, regions, REGION_ALIASES)
        if not target:
            return None
        country_regions = {
            r[0]
            for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))
        }
        answer = any(normalize(region) == normalize(target) for region in country_regions)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Regions for {country['app_country_name']}: {', '.join(sorted(country_regions))}.",
            relation="region",
        )

    def _answer_subregion(self, conn, country, original, q):
        subregions = [r[0] for r in conn.execute("SELECT DISTINCT subregion_name FROM country_subregions")]
        target = first_mentioned_value(q, subregions, SUBREGION_ALIASES)
        if not target:
            return None
        country_subregions = {
            r[0]
            for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))
        }
        all_subregions = expand_geographic_areas(country_subregions)
        answer = any(normalize(subregion) == normalize(target) for subregion in all_subregions)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Subregions for {country['app_country_name']}: {', '.join(sorted(country_subregions))}.",
            relation="subregion",
        )

    def _answer_water_access(self, conn, country, original, q):
        if not any(word in q for word in ("sea", "ocean", "morze", "ocean", "dostep", "coast", "coastline", "wybrzez", "nad ")):
            return None
        direct_waters = {r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))}
        if is_multi_ocean_question(q) or is_multi_ocean_question(original):
            oceans = sorted(get_distinct_oceans(direct_waters))
            count = len(oceans)
            answer = count >= 2
            if count >= 2:
                explanation = f"{country['app_country_name']} has access to {count} oceans: {', '.join(oceans)}."
            elif count == 1:
                explanation = f"{country['app_country_name']} has access to only 1 ocean: {oceans[0]}."
            else:
                if direct_waters:
                    explanation = f"{country['app_country_name']} has no direct open ocean access. Its recorded coastline: {', '.join(sorted(direct_waters))}."
                else:
                    explanation = f"{country['app_country_name']} is completely landlocked with no ocean access."
            return LocalAnswer(
                question="Does the country have access to two or more oceans?",
                answer=answer,
                explanation=explanation,
                relation="water_access",
            )
        waters = expand_water_bodies(direct_waters)
        all_waters = [r[0] for r in conn.execute("SELECT DISTINCT water_body FROM country_water_access")]
        for w in list(all_waters):
            if w in WATER_BODY_PARENT_MAP:
                all_waters.extend(WATER_BODY_PARENT_MAP[w])
        all_waters = list(dict.fromkeys(all_waters))
        target = first_mentioned_value(q, all_waters, VALUE_ALIASES)
        if target == "Ocean":
            answer = "Ocean" in waters
            explanation = (
                f"{country['app_country_name']} has direct coastline access to: "
                f"{', '.join(sorted(direct_waters))}."
                if answer
                else f"{country['app_country_name']} does not have direct coastline access to an ocean."
            )
        elif target:
            answer = target in waters
            via_sub = [w for w in sorted(direct_waters) if w in WATER_BODY_PARENT_MAP and target in WATER_BODY_PARENT_MAP[w]]
            via_str = f" (via the {', '.join(via_sub)})" if via_sub and target not in direct_waters else ""
            explanation = (
                f"{country['app_country_name']} has direct coastline access to: {target}{via_str}."
                if answer
                else f"{country['app_country_name']} does not have direct access to {target}."
            )
        elif any(word in q for word in ("sea access", "dostep do morza", "dostep do wod", "coast", "coastline", "wybrzez")):
            answer = bool(direct_waters)
            explanation = f"Main water bodies for {country['app_country_name']}: {', '.join(sorted(direct_waters)) if direct_waters else 'none'}."
        else:
            return None
        return LocalAnswer(
            question=f"Does the country have direct access to {'an ocean' if target == 'Ocean' else target or 'a sea/ocean'}?",
            answer=answer,
            explanation=explanation,
            relation="water_access",
        )

    def _answer_island(self, conn, country, original, q):
        if not any(word in q for word in ("island", "wyspa", "wyspiars", "archipelag", "archipelago")):
            return None
        answer = bool(country["is_island"])
        return LocalAnswer(
            question="Is the country an island country?",
            answer=answer,
            explanation=f"{country['app_country_name']} is {'an island' if answer else 'not an island'} country.",
            relation="is_island",
        )

    def _answer_capital(self, conn, country, original, q):
        if not any(word in q for word in ("capital", "stolic")):
            return None
        capitals = [r[0] for r in conn.execute("SELECT DISTINCT capital FROM countries WHERE capital IS NOT NULL")]
        capital_aliases = {"warszawa": "Warsaw", "praga": "Prague", "wieden": "Vienna", "rzym": "Rome", "londyn": "London", "paryz": "Paris"}
        target = first_mentioned_value(q, capitals, capital_aliases)
        if not target:
            return None
        answer = normalize(country["capital"] or "") == normalize(target)
        return LocalAnswer(
            question=f"Is the capital {target}?",
            answer=answer,
            explanation=f"The capital of {country['app_country_name']} is {country['capital']}.",
            relation="capital",
        )

    def _answer_currency(self, conn, country, original, q):
        if not any(word in q for word in ("currency", "walut", "euro", "dollar", "dolar", "zlot")):
            return None
        currencies = rows(conn, "SELECT currency_name, currency_code FROM country_currencies WHERE country_id=?", (country["id"],))
        all_values = [r[0] for r in conn.execute("SELECT DISTINCT currency_name FROM country_currencies")] + [r[0] for r in conn.execute("SELECT DISTINCT currency_code FROM country_currencies WHERE currency_code IS NOT NULL")]
        target = first_mentioned_value(q, all_values, VALUE_ALIASES)
        if not target:
            return None
        target_norm = normalize(target)
        answer = any(normalize(r["currency_name"]) == target_norm or normalize(r["currency_code"] or "") == target_norm for r in currencies)
        names = ", ".join(r["currency_name"] for r in currencies)
        return LocalAnswer(
            question=f"Does the country use {target}?",
            answer=answer,
            explanation=f"The currency for {country['app_country_name']} is: {names}.",
            relation="currency",
        )

    def _answer_language(self, conn, country, original, q):
        if not any(word in q for word in ("language", "jezyk", "speak", "spoken", "mowi", "official", "co-official", "coofficial", "wspolurzedow", "urzedow")):
            return None
        langs = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id=?", (country["id"],))]
        all_langs = [r[0] for r in conn.execute("SELECT DISTINCT language_name FROM country_languages")]
        target = first_mentioned_value(q, all_langs, VALUE_ALIASES)
        if not target:
            return None
        answer = normalize(target) in {normalize(x) for x in langs}
        is_spoken_inquiry = any(word in q for word in ("speak", "spoken", "mowi"))
        is_strictly_official_inquiry = any(word in q for word in ("official", "urzedow", "wspolurzedow", "co-official", "coofficial", "state language", "national language"))
        
        # If the language IS in official/co-official records, answer True immediately for both official and spoken inquiries.
        if answer:
            has_multiple = len(langs) > 1
            status_label = "official / co-official" if has_multiple else "official"
            if is_spoken_inquiry and not is_strictly_official_inquiry:
                explanation = f"Yes, {target} is an official/co-official language of {country['app_country_name']} ({', '.join(langs)})."
            else:
                explanation = f"Official/co-official languages for {country['app_country_name']}: {', '.join(langs)}."
            return LocalAnswer(
                question=f"Is {target} an official or spoken language?",
                answer=True,
                explanation=explanation,
                relation="official_language",
            )

        # If the question was strictly about official/co-official status, return False from local DB.
        if is_strictly_official_inquiry:
            return LocalAnswer(
                question=f"Is {target} an official language?",
                answer=False,
                explanation=f"{target} is not an official language of {country['app_country_name']}. Recorded official languages: {', '.join(langs)}.",
                relation="official_language",
            )
        
        # If the question asked broadly whether people speak the language ("do they speak Russian?"),
        # and it's NOT an official language, do NOT return a false negative from the local DB.
        # Return None to let the LLM / RAG examine whether it is widely spoken in practice.
        return None

    def _answer_dominant_religion(self, conn, country, original, q):
        if not any(word in q for word in ("religion", "religious", "catholic", "orthodox", "protestant", "christian", "islam", "muslim", "jewish", "judaism", "buddhist", "buddhism", "hindu", "atheist")):
            return None
        target = first_mentioned_value(q, RELIGION_ALIASES.values(), RELIGION_ALIASES)
        if not target:
            return None
        religion = country["dominant_religion"]
        if not religion:
            return None
        answer = normalize(religion) == normalize(target)
        return LocalAnswer(
            question=f"Is the country's dominant religion {target}?",
            answer=answer,
            explanation=f"The dominant religion category for {country['app_country_name']} is {religion}.",
            relation="dominant_religion",
        )

    def _answer_government_type(self, conn, country, original, q):
        if not any(word in q for word in ("government", "republic", "monarchy", "democracy", "federal", "theocracy", "communist", "dictatorship")):
            return None
        government_type = country["government_type"]
        if not government_type:
            return None
        target = first_mentioned_value(q, GOVERNMENT_TYPE_ALIASES.values(), GOVERNMENT_TYPE_ALIASES)
        if not target:
            return None
        answer = normalize(government_type) == normalize(target)
        return LocalAnswer(
            question=f"Is the country's government type {target}?",
            answer=answer,
            explanation=f"The government type for {country['app_country_name']} is {government_type}.",
            relation="government_type",
        )

    def _answer_membership(self, conn, country, original, q):
        orgs = [r[0] for r in conn.execute("SELECT DISTINCT organization FROM country_memberships")]
        target = first_mentioned_value(q, orgs, ORG_ALIASES)
        if not target:
            return None
        if not any(word in q for word in ("member", "nalezy", "czlon", "w ", "in ", "belongs", "part of")):
            return None
        memberships = {r[0] for r in conn.execute("SELECT organization FROM country_memberships WHERE country_id=?", (country["id"],))}
        answer = target in memberships
        return LocalAnswer(
            question=f"Is the country a member of {target}?",
            answer=answer,
            explanation=f"{country['app_country_name']} {'is' if answer else 'is not'} a member of {target}.",
            relation="membership",
            fact_provenance=[read_record(conn, country["id"], "membership", target if answer else None)],
        )

    def _answer_population_or_area(self, conn, country, original, q):
        relation = None
        field = None
        unit = None
        if any(word in q for word in ("population", "ludnosc", "mieszkanc", "inhabitants", "people", "citizens")):
            relation, field, unit = "population", "population", "people"
        elif any(word in q for word in ("area", "powierzch", "larger", "bigger", "wieksz")):
            relation, field, unit = "area", "area_km2", "km²"
        else:
            return None

        comparator = None
        if any(word in q for word in ("more", "greater", "larger", "bigger", "higher", "over", "wiecej", "wieksz", "ponad", "above")):
            comparator = "gt"
        elif any(word in q for word in ("less", "fewer", "smaller", "lower", "under", "mniej", "mniejsz", "ponizej", "below")):
            comparator = "lt"
        if not comparator:
            return None

        target_country = self._target_country(conn, q)
        target_value = None
        target_label = None
        if target_country and target_country != country["app_country_name"]:
            row = conn.execute(f"SELECT {field} FROM countries WHERE app_country_name=?", (target_country,)).fetchone()
            if row and row[0] is not None:
                target_value = row[0]
                target_label = target_country
        else:
            number_match = re.search(r"(\d+(?:[\s,.]\d+)*)\s*(million|mln|m|tys|thousand|k)?", q)
            if number_match:
                raw = re.sub(r"[\s,]", "", number_match.group(1))
                target_value = float(raw)
                suffix = number_match.group(2) or ""
                if suffix in {"million", "mln", "m"}:
                    target_value *= 1_000_000
                elif suffix in {"tys", "thousand", "k"}:
                    target_value *= 1_000
                target_label = f"{target_value:g} {unit}"
        if target_value is None:
            return None
        value = country[field]
        answer = value > target_value if comparator == "gt" else value < target_value
        sign = "more than" if comparator == "gt" else "less than"
        return LocalAnswer(
            question=f"Does the country have {sign} {target_label}?",
            answer=answer,
            explanation=f"{country['app_country_name']} has {value:g} {unit}; comparison: {sign} {target_label}.",
            relation=relation,
        )

    def _answer_coordinates(self, conn, country, original, q):
        if not any(word in q for word in ("hemisphere", "polkul", "equator", "rownik", "greenwich", "latitude", "longitude")):
            return None
        lat = country["latitude"]
        lon = country["longitude"]
        hemispheres = {r[0] for r in conn.execute("SELECT hemisphere FROM country_hemispheres WHERE country_id=?", (country["id"],))}
        if any(word in q for word in ("cross the equator", "crosses the equator", "crossing the equator", "on the equator", "straddle the equator", "przecina rownik", "lezy na rowniku", "na rowniku")):
            answer = "Northern" in hemispheres and "Southern" in hemispheres
            return LocalAnswer(
                question="Does the country cross the equator?",
                answer=answer,
                explanation=f"{country['app_country_name']} territory spans: {', '.join(sorted(hemispheres))} hemispheres.",
                relation="hemisphere",
            )
        if any(word in q for word in ("cross the prime meridian", "crosses the prime meridian", "crossing the prime meridian", "on the prime meridian", "cross the greenwich", "crosses the greenwich", "przecina poludnik greenwich", "przecina poludnik zerowy", "lezy na poludniku greenwich", "lezy na poludniku zerowym", "na poludniku greenwich", "na poludniku zerowym")):
            answer = "Eastern" in hemispheres and "Western" in hemispheres
            return LocalAnswer(
                question="Does the country cross the prime meridian?",
                answer=answer,
                explanation=f"{country['app_country_name']} territory spans: {', '.join(sorted(hemispheres))} hemispheres.",
                relation="hemisphere",
            )
        if any(word in q for word in ("northern", "polnocn", "north of equator", "north of the equator", "na polnoc od rownika", "nad rownik", "powyzej rownik", "above equator", "above the equator")):
            answer = "Northern" in hemispheres if hemispheres else lat > 0
            target = "Northern Hemisphere"
        elif any(word in q for word in ("southern", "poludn", "south of equator", "south of the equator", "na poludnie od rownika", "pod rownik", "ponizej rownik", "below equator", "below the equator")):
            answer = "Southern" in hemispheres if hemispheres else lat < 0
            target = "Southern Hemisphere"
        elif any(word in q for word in ("eastern", "wschodn", "east of the prime meridian", "east of prime meridian", "east of greenwich", "na wschod od poludnika greenwich", "na wschod od poludnika zerowego")):
            answer = "Eastern" in hemispheres if hemispheres else lon > 0
            target = "Eastern Hemisphere"
        elif any(word in q for word in ("western", "zachodn", "west of the prime meridian", "west of prime meridian", "west of greenwich", "na zachod od poludnika greenwich", "na zachod od poludnika zerowego")):
            answer = "Western" in hemispheres if hemispheres else lon < 0
            target = "Western Hemisphere"
        else:
            return None
        return LocalAnswer(
            question=f"Is the country in the {target}?",
            answer=answer,
            explanation=f"{country['app_country_name']} is located in the {', '.join(sorted(hemispheres)) if hemispheres else f'coordinates {lat:g}, {lon:g}'}.",
            relation="hemisphere" if hemispheres else "coordinates",
        )

    def _answer_river(self, conn, country, original, q):
        if not any(word in q for word in ("river", "rzeka", "rzek")):
            return None
        rivers = {r[0] for r in conn.execute("SELECT river_name FROM country_major_rivers WHERE country_id=?", (country["id"],))}
        all_rivers = [r[0] for r in conn.execute("SELECT DISTINCT river_name FROM country_major_rivers")]
        target = first_mentioned_value(q, all_rivers, VALUE_ALIASES)
        if not target:
            return None
        answer = target in rivers
        return LocalAnswer(
            question=f"Does the country have the {target} river?",
            answer=answer,
            explanation=f"Major rivers for {country['app_country_name']}: {', '.join(sorted(rivers)) if rivers else 'none in the local database'}.",
            relation="major_rivers",
        )

    def _answer_driving_side(self, conn, country, original, q):
        if not any(word in q for word in ("drive", "driving", "left side", "right side")):
            return None
        if "left" in q:
            target = "left"
        elif "right" in q:
            target = "right"
        else:
            return None
        answer = normalize(country["driving_side"] or "") == target
        return LocalAnswer(
            question=f"Does traffic drive on the {target}?",
            answer=answer,
            explanation=f"Traffic in {country['app_country_name']} drives on the {country['driving_side']}.",
            relation="driving_side",
        )

    def _answer_name_pattern(self, conn, country, original, q):
        if not any(word in q for word in ("name", "nazw")):
            return None
        cname = country["app_country_name"]
        cname_lower = cname.lower()
        m_end = re.search(r"(?:name|nazwa)\s+(?:end(?:s)?\s+(?:with|in)|konczy sie na)\s+[\"'\u201c\u201d]?([a-zA-Z]+)[\"'\u201c\u201d]?", q)
        if m_end:
            val = m_end.group(1).lower()
            answer = cname_lower.endswith(val)
            return LocalAnswer(
                question=f"Does the country name end with {val}?",
                answer=answer,
                explanation=f"The country name {cname} {'ends' if answer else 'does not end'} with “{val}”.",
                relation="name",
            )
        m_start = re.search(r"(?:name|nazwa)\s+(?:start(?:s)?\s+(?:with|in)|zaczyna sie na)\s+[\"'\u201c\u201d]?([a-zA-Z]+)[\"'\u201c\u201d]?", q)
        if m_start:
            val = m_start.group(1).lower()
            answer = cname_lower.startswith(val)
            return LocalAnswer(
                question=f"Does the country name start with {val}?",
                answer=answer,
                explanation=f"The country name {cname} {'starts' if answer else 'does not start'} with “{val}”.",
                relation="name",
            )
        m_cont = re.search(r"(?:name|nazwa)\s+(?:contain(?:s)?|zawiera)\s+[\"'\u201c\u201d]?([a-zA-Z]+)[\"'\u201c\u201d]?", q)
        if m_cont:
            val = m_cont.group(1).lower()
            answer = val in cname_lower
            return LocalAnswer(
                question=f"Does the country name contain {val}?",
                answer=answer,
                explanation=f"The country name {cname} {'contains' if answer else 'does not contain'} “{val}”.",
                relation="name",
            )
        return None


def try_answer_locally(question: str, country_name: str) -> LocalAnswer | None:
    return LocalCountryFacts().try_answer(question, country_name)


SCALAR_RELATION_FIELDS = {
    "name": "app_country_name",
    "capital": "capital",
    "population": "population",
    "area": "area_km2",
    "area_km2": "area_km2",
    "is_island": "is_island",
    "driving_side": "driving_side",
    "government_type": "government_type",
    "dominant_religion": "dominant_religion",
    "coordinates.latitude": "latitude",
    "coordinates.longitude": "longitude",
    "latitude": "latitude",
    "longitude": "longitude",
    "min_latitude": "min_latitude",
    "max_latitude": "max_latitude",
    "min_longitude": "min_longitude",
    "max_longitude": "max_longitude",
}

LIST_RELATION_QUERIES = {
    "continent": "SELECT continent FROM country_continents WHERE country_id=?",
    "region": "SELECT region_name FROM country_regions WHERE country_id=?",
    "subregion": "SELECT subregion_name FROM country_subregions WHERE country_id=?",
    "geographic_area": "SELECT region_name FROM country_regions WHERE country_id=? UNION SELECT subregion_name FROM country_subregions WHERE country_id=?",
    "borders_country": "SELECT border_country_name FROM country_borders WHERE country_id=? UNION SELECT c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3 WHERE cb.country_id=?",
    "water_access": "SELECT water_body FROM country_water_access WHERE country_id=?",
    "marine_access": "SELECT water_body FROM country_water_access WHERE country_id=?",
    "currency": "SELECT currency_name FROM country_currencies WHERE country_id=? UNION SELECT currency_code FROM country_currencies WHERE country_id=? AND currency_code IS NOT NULL",
    "official_language": "SELECT language_name FROM country_languages WHERE country_id=?",
    "membership": "SELECT organization FROM country_memberships WHERE country_id=?",
    "major_rivers": "SELECT river_name FROM country_major_rivers WHERE country_id=?",
    "flag_color": "SELECT color FROM country_flag_colors WHERE country_id=?",
    "flag_symbol": "SELECT symbol FROM country_flag_symbols WHERE country_id=?",
    "historical_union": "SELECT union_name FROM country_historical_unions WHERE country_id=?",
    "hemisphere": "SELECT hemisphere FROM country_hemispheres WHERE country_id=?",
}

def _country_name_key(name: str) -> str:
    cleaned = re.sub(r"\bst\.\s*", "saint ", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?<=\b[a-zA-Z])\.(?=[a-zA-Z](\.|\b))", "", cleaned).rstrip(".")
    return re.sub(r"\bst\b", "saint", normalize(cleaned.replace("&", " and ")))


def _one_edit_apart(left: str, right: str) -> bool:
    """One insertion, deletion, substitution or adjacent transposition."""
    if abs(len(left) - len(right)) > 1:
        return False
    for i, (a, b) in enumerate(zip(left, right)):
        if a == b:
            continue
        if len(left) != len(right):
            return left[i + 1:] == right[i:] if len(left) > len(right) else left[i:] == right[i + 1:]
        return left[i + 1:] == right[i + 1:] or (
            i + 1 < len(left)
            and left[i] == right[i + 1] and left[i + 1] == right[i]
            and left[i + 2:] == right[i + 2:]
        )
    return abs(len(left) - len(right)) == 1


def find_country(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    if not isinstance(name, str) or name in {"target_country", "item"}:
        return None
    direct = conn.execute("SELECT * FROM countries WHERE app_country_name=?", (name,)).fetchone()
    if direct:
        return direct
    wanted = _country_name_key(name)
    alias = COUNTRY_NAME_SYNONYMS.get(wanted) or POLISH_COUNTRY_ALIASES.get(wanted)
    if alias:
        direct = conn.execute("SELECT * FROM countries WHERE app_country_name=?", (alias,)).fetchone()
        if direct:
            return direct
    candidates = {}
    rows = {}
    for row in conn.execute("SELECT * FROM countries"):
        country = row["app_country_name"]
        rows[country] = row
        for label in (country, row["official_name"] or ""):
            key = _country_name_key(label)
            if key:
                candidates.setdefault(key, set()).add(country)
    for label, country in (COUNTRY_NAME_SYNONYMS | POLISH_COUNTRY_ALIASES).items():
        if country in rows:
            candidates.setdefault(_country_name_key(label), set()).add(country)
    matches = candidates.get(wanted)
    if matches is None:
        # Short acronyms and shared prefixes are not safe typo candidates.
        matches = set()
        if len(wanted) >= 5:
            for key, countries in candidates.items():
                if len(key) >= 5 and _one_edit_apart(wanted, key):
                    matches.update(countries)
    return rows[next(iter(matches))] if len(matches) == 1 else None


def resolve_entity(
    conn: sqlite3.Connection,
    entity: str,
    target_country: sqlite3.Row,
    item_value: str | None = None,
) -> sqlite3.Row | None:
    if entity == "target_country":
        return target_country
    if entity == "item":
        return find_country(conn, item_value or "")
    return find_country(conn, entity)


def resolve_ref(
    conn: sqlite3.Connection,
    ref: dict,
    target_country: sqlite3.Row,
    item_value: str | None = None,
):
    if not isinstance(ref, dict):
        return None
    if "value" in ref:
        return ref["value"]
    entity_name = ref.get("entity")
    relation = ref.get("relation")
    if not entity_name or not relation:
        return None
    entity = resolve_entity(conn, entity_name, target_country, item_value)
    if entity is None:
        return None
    if relation in SCALAR_RELATION_FIELDS:
        return entity[SCALAR_RELATION_FIELDS[relation]]
    if relation in LIST_RELATION_QUERIES:
        query = LIST_RELATION_QUERIES[relation]
        params = (entity["id"],) * query.count("?")
        res = [row[0] for row in conn.execute(query, params) if row[0] is not None]
        if relation == "marine_access":
            res = [water for water in res if is_marine_water_body(water)]
        if relation in {"water_access", "marine_access"}:
            expanded = expand_water_bodies(res)
            for w in list(expanded):
                w_lower = normalize_value(w)
                if "sea" in w_lower or "ocean" in w_lower or "gulf" in w_lower or "bay" in w_lower or "skagerrak" in w_lower:
                    expanded.add("Sea")
            return list(expanded)
        if relation in {"geographic_area", "subregion"}:
            return list(expand_geographic_areas(res))
        return res
    return None


def normalize_value(value):
    if isinstance(value, str):
        return normalize(value)
    return value


def text_value(value) -> str | None:
    if value is None:
        return None
    return str(value)


def is_self_country_reference(value, target_country: sqlite3.Row) -> bool:
    if value is None:
        return False
    value_norm = normalize(str(value))
    target_norm = normalize(str(target_country["app_country_name"]))
    return value_norm == target_norm or value_norm in {
        "itself",
        "it self",
        "same country",
        "same entity",
        "self",
        "samym soba",
        "samym sobą",
        "sobą",
        "soba",
    }


def word_count(value: str) -> int:
    return len([part for part in re.split(r"\s+", value.strip()) if part])


def char_count(value: str) -> int:
    return len(re.sub(r"[\s\-\u2010\u2011]+", "", value))


def _hyphenated_country_alias(name: str) -> str | None:
    for alias, canonical in COUNTRY_NAME_SYNONYMS.items():
        if canonical == name and any(char in alias for char in "-\u2010\u2011"):
            return alias
    return None


def collect_ref_evidence(conn, ref, target_country, item_value, evidence, *, contains_value=None):
    if evidence is None or not isinstance(ref, dict) or "value" in ref:
        return
    relation = ref.get("relation")
    if relation not in EVIDENCE_RELATIONS:
        return
    entity = resolve_entity(conn, ref.get("entity"), target_country, item_value)
    if entity is None:
        return
    value = None
    if contains_value is not None:
        actual = resolve_ref(conn, ref, target_country, item_value)
        canonical = normalize_hemisphere if relation == "hemisphere" else normalize_value
        value = next((item for item in actual if canonical(item) == canonical(contains_value)), None)
    record = read_record(conn, entity["id"], relation, value)
    if record not in evidence:
        evidence.append(record)


def merge_used_evidence(evidence, results, branches, *, decisive):
    if evidence is None:
        return
    has_decisive = any(result is decisive for result in results)
    for result, branch in zip(results, branches):
        if not has_decisive or result is decisive:
            for record in branch:
                if record not in evidence:
                    evidence.append(record)


def evaluate_plan_node(
    conn: sqlite3.Connection,
    node: dict,
    target_country: sqlite3.Row,
    item_value: str | None = None,
    fact_provenance: list[dict] | None = None,
) -> bool | None:
    if not isinstance(node, dict):
        return None
    operator = node.get("operator")

    if operator == "not":
        result = evaluate_plan_node(conn, node.get("condition"), target_country, item_value, fact_provenance)
        return None if result is None else not result

    if operator in {"and", "or"}:
        conditions = node.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            return None
        branches = [[] for _ in conditions] if fact_provenance is not None else [None] * len(conditions)
        results = [evaluate_plan_node(conn, condition, target_country, item_value, branch)
                   for condition, branch in zip(conditions, branches)]
        merge_used_evidence(fact_provenance, results, branches, decisive=operator == "or")
        if operator == "or":
            if any(result is True for result in results):
                return True
            if any(result is None for result in results):
                return None
            return False
        if any(result is False for result in results):
            return False
        if any(result is None for result in results):
            return None
        return True

    if operator == "exists":
        value = resolve_ref(conn, node.get("left", {}), target_country, item_value)
        if value is None:
            return None
        collect_ref_evidence(conn, node.get("left", {}), target_country, item_value, fact_provenance)
        if isinstance(value, list):
            return bool(value)
        return bool(value)

    if operator in {
        "contains",
        "equals",
        "greater_than",
        "less_than",
        "greater_than_or_equal",
        "less_than_or_equal",
        "west_of",
        "east_of",
        "north_of",
        "south_of",
        "starts_with",
        "ends_with",
        "contains_text",
        "has_space",
        "has_hyphen",
        "word_count_equals",
        "word_count_greater_than",
        "word_count_less_than",
        "char_count_equals",
        "char_count_greater_than",
        "char_count_less_than",
    }:
        left = resolve_ref(conn, node.get("left", {}), target_country, item_value)
        right = resolve_ref(conn, node.get("right", {}), target_country, item_value)
        if left is None or (operator not in {"has_space", "has_hyphen"} and right is None):
            return None
        collect_ref_evidence(conn, node.get("left", {}), target_country, item_value, fact_provenance,
                             contains_value=right if operator == "contains" else None)
        collect_ref_evidence(conn, node.get("right", {}), target_country, item_value, fact_provenance)
        left_ref = node.get("left", {})
        relation = str(left_ref.get("relation") or "") if isinstance(left_ref, dict) else ""
        if operator == "equals" and relation == "currency" and isinstance(left, list):
            c_canon = CURRENCY_ALIASES.get(normalize_value(right), normalize_value(right))
            return any(CURRENCY_ALIASES.get(normalize_value(v), normalize_value(v)) == c_canon for v in left)
        if operator != "contains" and (isinstance(left, list) or isinstance(right, list)):
            if (
                operator in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}
                and isinstance(left, list)
                and type(right) is not bool
                and (isinstance(right, (int, float)) or (isinstance(right, str) and right.isdigit()))
            ):
                if relation == "borders_country":
                    canonical = set()
                    for item in left:
                        c_row = find_country(conn, str(item))
                        canonical.add(c_row["app_country_name"] if c_row is not None else str(item))
                    left_num = float(len(canonical))
                else:
                    left_num = float(len(left))
                right_num = float(right)
                if operator == "equals":
                    return left_num == right_num
                if operator == "greater_than_or_equal":
                    return left_num >= right_num
                if operator == "less_than_or_equal":
                    return left_num <= right_num
                if operator == "greater_than":
                    return left_num > right_num
                if operator == "less_than":
                    return left_num < right_num
            return None
        left_ref = node.get("left", {})
        if (
            operator in {"contains", "equals"}
            and isinstance(left_ref, dict)
            and str(left_ref.get("relation") or "").startswith("borders_")
            and is_self_country_reference(right, target_country)
        ):
            return True
        relation = str(left_ref.get("relation") or "") if isinstance(left_ref, dict) else ""
        if operator == "contains":
            if not isinstance(left, list) or isinstance(right, (list, dict, bool)):
                return None
            right_norm = normalize_value(right)
            if relation == "historical_union" and not conn.execute(
                "SELECT 1 FROM country_historical_unions WHERE union_name = ? COLLATE NOCASE LIMIT 1",
                (right,),
            ).fetchone():
                return None
            if relation == "borders_country":
                resolved = find_country(conn, right)
                if resolved is None:
                    return None
                subject = resolve_entity(conn, left_ref["entity"], target_country, item_value)
                if subject is not None and resolved["id"] == subject["id"]:
                    return True
                r_canon = canonical_country_name(resolved["app_country_name"])
                return any(canonical_country_name(value) == r_canon for value in left)
            if relation == "currency":
                c_canon = CURRENCY_ALIASES.get(right_norm, right_norm)
                return any(CURRENCY_ALIASES.get(normalize_value(value), normalize_value(value)) == c_canon for value in left)
            if relation == "hemisphere":
                h_canon = normalize_hemisphere(right_norm)
                return any(normalize_hemisphere(normalize_value(value)) == h_canon for value in left)
            if relation == "water_access":
                if right_norm == "sea":
                    return "Sea" in left or bool(left)
                if right_norm == "ocean":
                    return "Ocean" in left or any("ocean" in normalize_value(w) for w in left)
                return any(normalize_value(value) == right_norm for value in left)
            return any(normalize_value(value) == right_norm for value in left)
        if operator == "equals":
            refs = (left_ref, node.get("right", {}))
            if (
                any(ref.get("relation") == "name" for ref in refs)
                and all("value" in ref or ref.get("relation") == "name" for ref in refs)
            ):
                left_country = find_country(conn, left)
                right_country = find_country(conn, right)
                if left_country is None or right_country is None:
                    return None
                return left_country["id"] == right_country["id"]
            if relation == "dominant_religion":
                c_left = RELIGION_ALIASES.get(normalize_value(left).lower(), normalize_value(left))
                c_right = RELIGION_ALIASES.get(normalize_value(right).lower(), normalize_value(right))
                return normalize_value(c_left) == normalize_value(c_right)
            if relation == "driving_side":
                c_left = "left" if "left" in str(left).lower() else ("right" if "right" in str(left).lower() else str(left))
                c_right = "left" if "right" not in str(right).lower() and "left" in str(right).lower() else ("right" if "right" in str(right).lower() else str(right))
                return c_left.lower() == c_right.lower()
            return normalize_value(left) == normalize_value(right)
        if operator == "has_space":
            return " " in (text_value(left) or "").strip()
        if operator == "has_hyphen":
            left_text = text_value(left) or ""
            if any(char in left_text for char in "-\u2010\u2011"):
                return True
            return relation == "name" and _hyphenated_country_alias(left_text) is not None
        if operator in {"starts_with", "ends_with", "contains_text"}:
            left_text = normalize(text_value(left) or "", preserve_separators=True)
            right_text = normalize(text_value(right) or "", preserve_separators=True)
            if operator == "starts_with":
                return left_text.startswith(right_text)
            if operator == "ends_with":
                return left_text.endswith(right_text)
            if operator == "contains_text":
                return right_text in left_text
        if operator.startswith("word_count_"):
            left_num = word_count(text_value(left) or "")
            try:
                right_num = int(right)
            except (TypeError, ValueError):
                return None
            if operator == "word_count_equals":
                return left_num == right_num
            if operator == "word_count_greater_than":
                return left_num > right_num
            if operator == "word_count_less_than":
                return left_num < right_num
        if operator.startswith("char_count_"):
            left_num = char_count(text_value(left) or "")
            try:
                right_num = int(right)
            except (TypeError, ValueError):
                return None
            if operator == "char_count_equals":
                return left_num == right_num
            if operator == "char_count_greater_than":
                return left_num > right_num
            if operator == "char_count_less_than":
                return left_num < right_num
        try:
            left_num = float(left)
            right_num = float(right)
        except (TypeError, ValueError):
            return None
        if operator == "greater_than_or_equal":
            return left_num >= right_num
        if operator == "less_than_or_equal":
            return left_num <= right_num
        if operator in {"north_of", "south_of", "west_of", "east_of"}:
            right_entity = node.get("right", {}).get("entity") if isinstance(node.get("right"), dict) else None
            if (
                right_entity in {"target_country", target_country["app_country_name"], target_country["official_name"]}
                or is_self_country_reference(right_entity, target_country)
            ):
                return None
        if operator in {"greater_than", "east_of", "north_of"}:
            return left_num > right_num
        if operator in {"less_than", "west_of", "south_of"}:
            return left_num < right_num

    if operator in {"any", "all"}:
        items = resolve_ref(conn, node.get("items", {}), target_country, item_value)
        condition = node.get("condition")
        if not isinstance(items, list) or condition is None:
            return None
        collect_ref_evidence(conn, node.get("items", {}), target_country, item_value, fact_provenance)
        branches = [[] for _ in items] if fact_provenance is not None else [None] * len(items)
        results = [evaluate_plan_node(conn, condition, target_country, str(item), branch)
                   for item, branch in zip(items, branches)]
        merge_used_evidence(fact_provenance, results, branches, decisive=operator == "any")
        if operator == "any":
            if any(result is True for result in results):
                return True
            if any(result is None for result in results):
                return None
            return False
        if any(result is False for result in results):
            return False
        if any(result is None for result in results):
            return None
        return True

    return None


def plan_relations(node: dict | None) -> set[str]:
    found: set[str] = set()
    if not isinstance(node, dict):
        return found
    for key in ("left", "right", "items"):
        ref = node.get(key)
        if isinstance(ref, dict) and isinstance(ref.get("relation"), str):
            found.add(ref["relation"].split(".")[0])
    found |= plan_relations(node.get("condition"))
    for condition in node.get("conditions", []) if isinstance(node.get("conditions"), list) else []:
        found |= plan_relations(condition)
    return found


_CONTINENT_UNIONS = {
    "america": ("North America", "South America"),
    "americas": ("North America", "South America"),
    "eurasia": ("Europe", "Asia"),
}


def normalize_continent_unions(node: dict | None) -> dict | None:
    """Expand physical continent unions without changing bindings or the input AST."""
    if not isinstance(node, dict):
        return node
    normalized = dict(node)
    if isinstance(normalized.get("condition"), dict):
        normalized["condition"] = normalize_continent_unions(normalized["condition"])
    if isinstance(normalized.get("conditions"), list):
        normalized["conditions"] = [
            normalize_continent_unions(condition) for condition in normalized["conditions"]
        ]
    left = normalized.get("left")
    right = normalized.get("right")
    if (
        normalized.get("operator") == "contains"
        and isinstance(left, dict)
        and left.get("relation") == "continent"
        and isinstance(right, dict)
        and isinstance(right.get("value"), str)
    ):
        continents = _CONTINENT_UNIONS.get(normalize(right["value"]))
        if continents is not None:
            return {
                "operator": "or",
                "conditions": [
                    {
                        **normalized,
                        "left": dict(left),
                        "right": {**right, "value": continent},
                    }
                    for continent in continents
                ],
            }
    return normalized


def normalize_geographic_area_plan(conn: sqlite3.Connection, node: dict | None) -> dict | None:
    """Canonicalize physical continent unions and the stored geographic-area layer."""
    return _normalize_geographic_area_plan(conn, normalize_continent_unions(node))


def _normalize_geographic_area_plan(conn: sqlite3.Connection, node: dict | None) -> dict | None:
    """Treat region and subregion planner output as one geographic-area layer."""
    if not isinstance(node, dict):
        return node

    normalized = dict(node)

    for key in ("left", "right", "items"):
        ref = normalized.get(key)
        if isinstance(ref, dict):
            normalized[key] = dict(ref)
            if ref.get("relation") in {"region", "subregion"}:
                normalized[key]["relation"] = "geographic_area"

    left = normalized.get("left")
    right = normalized.get("right")
    if (
        isinstance(left, dict)
        and left.get("relation") == "geographic_area"
        and isinstance(right, dict)
        and isinstance(right.get("value"), str)
    ):
        value = normalize(right["value"])
        if value in {"north america", "south america"}:
            left["relation"] = "continent"
            canonical_area = value.title()
        else:
            canonical_area = GEOGRAPHIC_AREA_ALIASES.get(value)
            if canonical_area is None:
                canonical_area = next(
                    (
                        row[0]
                        for row in conn.execute(
                            "SELECT region_name FROM country_regions "
                            "UNION SELECT subregion_name FROM country_subregions"
                        )
                        if normalize(row[0]) == value
                    ),
                    None,
                )
        if canonical_area is None:
            return None
        right["value"] = canonical_area
    if isinstance(normalized.get("condition"), dict):
        normalized["condition"] = _normalize_geographic_area_plan(conn, normalized["condition"])
    if isinstance(normalized.get("conditions"), list):
        normalized["conditions"] = [
            _normalize_geographic_area_plan(conn, condition)
            if isinstance(condition, dict)
            else condition
            for condition in normalized["conditions"]
        ]
    return normalized

def generate_factual_explanation(
    conn: sqlite3.Connection,
    country: sqlite3.Row,
    plan: dict,
    answer: bool,
    *,
    item_value: str | None = None,
) -> str:
    def number(value: int | float) -> str:
        return f"{value:,}".removesuffix(".0")

    name = country["app_country_name"]
    node = plan if isinstance(plan, dict) else {}
    op = node.get("operator")
    left = node.get("left")
    right = node.get("right")
    rel = None
    target_val = None
    if isinstance(left, dict) and "relation" in left:
        rel = left["relation"]
    if isinstance(right, dict) and "value" in right:
        target_val = right["value"]
    if op == "not":
        child = node.get("condition")
        return generate_factual_explanation(
            conn, country, child, not answer, item_value=item_value
        )
    if op in {"and", "or"}:
        if op == "or" and answer is True:
            true_facts = []
            for child in node.get("conditions", []):
                if evaluate_plan_node(conn, child, country, item_value) is True:
                    detail = generate_factual_explanation(
                        conn, country, child, True, item_value=item_value
                    )
                    if detail and detail not in true_facts:
                        true_facts.append(detail)
            if true_facts:
                return " ".join(true_facts)
        facts = []
        for child in node.get("conditions", []):
            child_answer = evaluate_plan_node(conn, child, country, item_value)
            if child_answer is not None:
                detail = generate_factual_explanation(
                    conn, country, child, child_answer, item_value=item_value
                )
                if detail and detail not in facts:
                    facts.append(detail)
        if facts:
            return " ".join(facts)
        return ""
    if op in {"any", "all"}:
        items_ref = node.get("items", {})
        items = resolve_ref(conn, items_ref, country, item_value)
        condition = node.get("condition")
        if not isinstance(items, list) or condition is None:
            return ""
        entity = items_ref.get("entity") if isinstance(items_ref, dict) else None
        subject = resolve_entity(conn, entity, country, item_value) if entity else None
        subject_name = subject["app_country_name"] if subject is not None else name
        neighbors = isinstance(items_ref, dict) and items_ref.get("relation") == "borders_country"
        facts = []
        for item in items:
            bound_value = str(item)
            child_answer = evaluate_plan_node(conn, condition, country, bound_value)
            if child_answer is answer:
                facts.append(
                    generate_factual_explanation(
                        conn, country, condition, child_answer, item_value=bound_value
                    )
                )
                if (op == "any" and answer) or (op == "all" and not answer):
                    break
        if facts:
            scope = f"Among {subject_name}'s land-border neighbors: " if neighbors else "Among the listed items: "
            return scope + " ".join(facts)
        if not items:
            return f"{subject_name} has no land-border neighbors." if neighbors else "There are no items to check."
        return ""
    target_country = country
    if isinstance(left, dict) and left.get("entity"):
        subject = resolve_entity(conn, left["entity"], target_country, item_value)
        if subject is not None:
            country = subject
            name = country["app_country_name"]

    if (
        isinstance(right, dict)
        and right.get("entity")
        and right.get("relation")
        and op not in {"north_of", "south_of", "east_of", "west_of"}
    ):
        other = resolve_entity(conn, right["entity"], target_country, item_value)
        if rel == "name" and right["relation"] == "name" and op == "equals" and other is not None:
            if country["id"] == other["id"]:
                role = "target" if country["id"] == target_country["id"] else "referenced"
                return f"{name} is the {role} country."
            return f"{name} and {other['app_country_name']} are different countries."
        value = resolve_ref(conn, right, target_country, item_value)
        if value is not None:
            detail = generate_factual_explanation(
                conn, target_country, {**node, "right": {"value": value}}, answer,
                item_value=item_value,
            )
            other_detail = generate_factual_explanation(
                conn, target_country, {"operator": "exists", "left": right}, bool(value),
                item_value=item_value,
            )
            return " ".join(dict.fromkeys(fact for fact in (detail, other_detail) if fact))

    if (
        rel in LIST_RELATION_QUERIES
        and op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}
        and type(target_val) is not bool
        and (isinstance(target_val, (int, float)) or isinstance(target_val, str) and target_val.isdigit())
    ):
        values = resolve_ref(conn, left, target_country, item_value)
        if isinstance(values, list):
            if rel == "borders_country":
                canonical = set()
                for value in values:
                    neighbor = find_country(conn, str(value))
                    canonical.add(neighbor["app_country_name"] if neighbor is not None else str(value))
                values = sorted(canonical)
            labels = {
                "continent": ("continent", "continents"),
                "region": ("region", "regions"),
                "subregion": ("subregion", "subregions"),
                "geographic_area": ("geographic area", "geographic areas"),
                "borders_country": ("land-border neighbor", "land-border neighbors"),
                "water_access": ("water-access entry", "water-access entries"),
                "marine_access": ("marine-access entry", "marine-access entries"),
                "currency": ("currency name or code", "currency names or codes"),
                "official_language": ("official language", "official languages"),
                "membership": ("membership", "memberships"),
                "major_rivers": ("major river", "major rivers"),
                "flag_color": ("flag color", "flag colors"),
                "flag_symbol": ("flag symbol", "flag symbols"),
                "historical_union": ("historical union", "historical unions"),
                "hemisphere": ("hemisphere", "hemispheres"),
            }
            label = labels[rel][0 if len(values) == 1 else 1]
            listing = f": {', '.join(map(str, values))}" if values else ""
            return f"{name} has {len(values)} {label} recorded{listing}."

    if rel == "borders_country":
        if target_val:
            resolved = find_country(conn, target_val)
            if resolved is not None:
                target_val = resolved["app_country_name"]
                if answer and resolved["id"] == country["id"]:
                    return f"In this game, {name} counts as bordering itself."
            borders = [r[0] for r in conn.execute("SELECT border_country_name FROM country_borders WHERE country_id=?", (country["id"],))]
            if answer:
                return f"{name} shares a land border with {target_val}."
            else:
                b_str = ", ".join(sorted(set(borders))) if borders else "none"
                return f"{name} does not border {target_val}. Its land borders are: {b_str}."
        borders = resolve_ref(conn, left, target_country, item_value)
        if borders:
            return f"{name} shares land borders with {', '.join(sorted(set(borders)))}."
        return f"{name} has no land-border neighbors."

    if rel == "marine_access":
        db_waters = sorted(set(r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))))
        marine_waters = [water for water in db_waters if is_marine_water_body(water)]
        inland_waters = [water for water in db_waters if not is_marine_water_body(water)]
        if target_val:
            if answer:
                return f"{name} has coastline connected to the open sea via {target_val}."
            if not is_marine_water_body(str(target_val)):
                return f"{target_val} is an inland water body and does not connect {name}'s shoreline to the open sea."
            if inland_waters:
                return (
                    f"{name} does not have coastline connected to the open sea via {target_val}. "
                    f"It has inland shoreline on: {', '.join(inland_waters)}."
                )
            return f"{name} does not have coastline connected to the open sea via {target_val}."
        if answer:
            return f"{name} has coastline connected to the open sea via: {', '.join(marine_waters)}."
        if inland_waters:
            return (
                f"{name} has no coastline connected to the open sea. "
                f"It does have inland shoreline on: {', '.join(inland_waters)}."
            )
        return f"{name} has no coastline connected to the open sea."

    if rel == "water_access":
        db_waters = sorted(set(r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))))
        all_waters = expand_water_bodies(db_waters)
        all_waters_sorted = sorted(all_waters - {"Ocean", "Sea"})
        w_str = ", ".join(all_waters_sorted) if all_waters_sorted else ""
        if normalize(str(target_val)) == "sea":
            if answer:
                return f"{name} has direct coastline access to: {', '.join(db_waters)}."
            return f"{name} is completely landlocked with no direct coastline."

        if normalize(str(target_val)) == "ocean":
            if answer:
                return f"{name} has direct coastline access to: {', '.join(db_waters)}."
            if db_waters:
                return f"{name} does not have direct coastline access to an ocean. Its coastline access: {', '.join(db_waters)}."
            return f"{name} is completely landlocked with no direct coastline."
        if target_val:
            via_sub = [w for w in db_waters if w in WATER_BODY_PARENT_MAP and target_val in WATER_BODY_PARENT_MAP[w]]
            via_str = f" (via the {', '.join(via_sub)})"
            if answer:
                sub_note = via_str if via_sub and target_val not in db_waters else ""
                return f"{name} has direct coastline access to: {target_val}{sub_note}."
            else:
                if all_waters_sorted:
                    return f"{name} does not have direct coastline access to: {target_val}. Its coastline access: {w_str}."
                else:
                    return f"{name} is completely landlocked with no direct coastline to any sea or ocean (no access to: {target_val})."
        else:
            if all_waters_sorted:
                return f"{name} has direct coastline access to: {w_str}."
            else:
                return f"{name} is completely landlocked with no direct coastline."

    if rel == "hemisphere":
        db_hemis = [r[0] for r in conn.execute("SELECT hemisphere FROM country_hemispheres WHERE country_id=?", (country["id"],))]
        h_str = " and the ".join(f"{hemisphere} Hemisphere" for hemisphere in sorted(db_hemis))
        if target_val:
            target_display = normalize_hemisphere(str(target_val)).capitalize()
            if answer:
                return f"{name} is located in the {target_display} Hemisphere."
            actual = f" It is located in the {h_str}." if h_str else ""
            return f"{name} is not located in the {target_display} Hemisphere.{actual}"
        return f"{name} is located in the {h_str}." if h_str else f"No hemispheres are recorded for {name}."
    if rel == "is_island":
        if country["is_island"]:
            return f"{name} is an island nation."
        else:
            return f"{name} is not an island nation."

    if rel == "continent":
        conts = [r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id=?", (country["id"],))]
        c_str = ", ".join(conts)
        if not conts:
            return f"No continents are recorded for {name}."
        if target_val and not answer:
            return f"{name} is not located in {target_val}; it is in {c_str}."
        return f"{name} is located in {c_str}."

    if rel in ("geographic_area", "region", "subregion"):
        subregs = [r[0] for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))]
        regs = [r[0] for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))]
        all_areas = sorted(set(subregs + regs))
        areas_str = ", ".join(all_areas)
        if target_val:
            if answer:
                return f"{name} is located in {target_val}."
            return f"{name} is not located in {target_val}. Its geographic regions are {areas_str or 'not recorded'}."
        return f"The geographic regions recorded for {name} are {areas_str}." if all_areas else f"No geographic regions are recorded for {name}."

    if rel == "currency":
        curr_rows = conn.execute("SELECT currency_name, currency_code FROM country_currencies WHERE country_id=?", (country["id"],)).fetchall()
        if not curr_rows:
            return f"No official currencies are recorded for {name}."
        currs_str = ", ".join(f"{r[0]} ({r[1]})" if r[1] else r[0] for r in curr_rows)
        label = "currency" if len(curr_rows) == 1 else "currencies"
        verb = "is" if len(curr_rows) == 1 else "are"
        actual = f"The official {label} of {name} {verb} {currs_str}."
        return actual if answer or target_val is None else f"{target_val} is not an official currency of {name}. {actual}"

    if rel == "official_language":
        langs = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id=?", (country["id"],))]
        if not langs:
            return f"No official languages are recorded for {name}."
        langs_str = ", ".join(langs)
        label = "language" if len(langs) == 1 else "languages"
        verb = "is" if len(langs) == 1 else "are"
        actual = f"The official {label} of {name} {verb} {langs_str}."
        return actual if answer or target_val is None else f"{target_val} is not an official language of {name}. {actual}"

    if rel == "major_rivers":
        rivers = [r[0] for r in conn.execute("SELECT river_name FROM country_major_rivers WHERE country_id=?", (country["id"],))]
        if target_val:
            if answer:
                return f"The river {target_val} flows through {name}."
            actual = f" Major rivers include {', '.join(rivers)}." if rivers else ""
            return f"The river {target_val} does not flow through {name}.{actual}"
        return f"Major rivers in {name} include {', '.join(rivers)}." if rivers else f"No major rivers are recorded for {name}."

    if rel in ("historical_union", "membership"):
        if target_val:
            if rel == "membership":
                return f"{name} {'is' if answer else 'is not'} a member of {target_val}."
            return f"{name} {'was historically part' if answer else 'was not part'} of {target_val}."
        values = resolve_ref(conn, left, target_country, item_value)
        if values:
            listing = ", ".join(values)
            return f"{name} is a member of {listing}." if rel == "membership" else f"{name} was historically part of {listing}."
        label = "memberships" if rel == "membership" else "historical unions"
        return f"No {label} are recorded for {name}."

    if rel == "flag_color":
        colors = [r[0] for r in conn.execute("SELECT color FROM country_flag_colors WHERE country_id=?", (country["id"],))]
        if not colors:
            return f"No flag colors are recorded for {name}."
        actual = f"The flag of {name} contains {', '.join(colors)}."
        return actual if answer or target_val is None else f"The flag of {name} does not include {target_val}. {actual}"

    if rel == "flag_symbol":
        symbols = [r[0] for r in conn.execute("SELECT symbol FROM country_flag_symbols WHERE country_id=?", (country["id"],))]
        if target_val and answer:
            return f"The flag of {name} features {target_val}."
        actual = f"The flag of {name} features {', '.join(symbols)}." if symbols else f"No flag symbols are recorded for {name}."
        return actual if target_val is None else f"The flag of {name} does not feature {target_val}. {actual}"

    if rel == "driving_side":
        side_en = "left" if country["driving_side"] == "left" else "right"
        return f"Traffic in {name} drives on the {side_en} side."


    if rel == "population":
        pop = country["population"]
        if target_val is not None and op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}:
            try:
                val_num = float(target_val)
                comparison = "equal to" if pop == val_num else "more than" if pop > val_num else "fewer than"
                return f"{name} has a population of approximately {number(pop)} ({comparison} {number(val_num)})."
            except (ValueError, TypeError):
                pass
        return f"{name} has a population of approximately {number(pop)}."

    if rel in ("area_km2", "area"):
        area = country["area_km2"]
        if target_val is not None and op in {"equals", "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal"}:
            try:
                val_num = float(target_val)
                comparison = "equal to" if area == val_num else "larger than" if area > val_num else "smaller than"
                return f"The area of {name} is approximately {number(area)} km², {comparison} {number(val_num)} km²."
            except (ValueError, TypeError):
                pass
        return f"The area of {name} is approximately {number(area)} km²."

    if rel == "dominant_religion":
        relig = country["dominant_religion"]
        if target_val and not answer:
            return f"The dominant religion in {name} is {relig}, not {target_val}."
        return f"The dominant religion in {name} is {relig}."

    if rel == "government_type":
        gov = country["government_type"]
        if target_val and not answer:
            return f"The government type of {name} is {gov}, not {target_val}."
        return f"The government type of {name} is {gov}."

    if op in ("north_of", "south_of", "east_of", "west_of"):
        other_entity_name = right.get("entity") if isinstance(right, dict) else None
        other_country = resolve_entity(conn, other_entity_name, target_country, item_value) if other_entity_name else None
        if other_country is not None:
            axis = "latitude" if op in ("north_of", "south_of") else "longitude"
            coordinate = country[axis]
            other_coordinate = other_country[axis]
            positive, negative = ("N", "S") if axis == "latitude" else ("E", "W")
            cardinal = positive if coordinate >= 0 else negative
            other_cardinal = positive if other_coordinate >= 0 else negative
            coordinate_text = f"{number(abs(coordinate))}°{cardinal}"
            other_text = f"{number(abs(other_coordinate))}°{other_cardinal}"
            other_name = other_country["app_country_name"]
            if coordinate == other_coordinate:
                return f"{name} and {other_name} have the same recorded {axis} ({coordinate_text})."
            directions = ("north", "south") if axis == "latitude" else ("east", "west")
            direction = directions[0 if coordinate > other_coordinate else 1]
            return (
                f"By the recorded coordinates, {name} ({coordinate_text}) is {direction} "
                f"of {other_name} ({other_text})."
            )

    if rel in {
        "coordinates.latitude", "coordinates.longitude", "latitude", "longitude",
        "min_latitude", "max_latitude", "min_longitude", "max_longitude",
    }:
        coordinate = resolve_ref(conn, left, target_country, item_value)
        if coordinate is not None:
            axis = "latitude" if "latitude" in rel else "longitude"
            positive, negative = ("N", "S") if axis == "latitude" else ("E", "W")
            cardinal = positive if coordinate >= 0 else negative
            label = rel.removeprefix("coordinates.").replace("min_", "minimum ").replace("max_", "maximum ")
            return f"The recorded {label} of {name} is {number(abs(coordinate))}°{cardinal}."

    if rel in {"name", "capital"}:
        text = name if rel == "name" else country["capital"]
        intro = "" if rel == "name" else f"The capital of {name} is {text}. "
        label = f"The name {text}" if rel == "name" else "Its name"
        if op in {"has_space", "has_hyphen"}:
            present = " " in text.strip() if op == "has_space" else any(
                char in text for char in "-\u2010\u2011"
            )
            if op == "has_hyphen" and rel == "name" and not present:
                alias = _hyphenated_country_alias(text)
                if alias is not None:
                    return f"The accepted alias “{alias}” for {name} contains a hyphen."
            mark = "a space" if op == "has_space" else "a hyphen"
            return intro + f"{label} {'contains' if present else 'does not contain'} {mark}."
        if op and op.startswith("word_count"):
            count = word_count(text)
            return intro + f"{label} consists of {count} {'words' if count != 1 else 'word'}."
        if op and op.startswith("char_count"):
            count = char_count(text)
            return intro + f"{label} has {count} characters, excluding spaces and hyphens."
        if op in {"starts_with", "ends_with", "contains_text"} and target_val is not None:
            positive, negative = {
                "starts_with": ("starts with", "does not start with"),
                "ends_with": ("ends with", "does not end with"),
                "contains_text": ("contains", "does not contain"),
            }[op]
            return intro + f"{label} {positive if answer else negative} “{target_val}”."
        if rel == "name":
            role = "target" if country["id"] == target_country["id"] else "referenced"
            return f"{name} is the {role} country."
        return intro.strip()

    left_value = resolve_ref(conn, left, target_country, item_value)
    right_value = resolve_ref(conn, right, target_country, item_value)
    if op == "exists":
        return f"The provided value is {'nonempty' if bool(left_value) else 'empty'}."
    if isinstance(left_value, str):
        if op and op.startswith("word_count"):
            count = word_count(left_value)
            return f"The text “{left_value}” consists of {count} {'words' if count != 1 else 'word'}."
        if op and op.startswith("char_count"):
            return f"The text “{left_value}” has {char_count(left_value)} characters, excluding spaces and hyphens."
        if op in {"has_space", "has_hyphen"}:
            present = " " in left_value.strip() if op == "has_space" else any(
                char in left_value for char in "-\u2010\u2011"
            )
            mark = "a space" if op == "has_space" else "a hyphen"
            return f"The text “{left_value}” {'contains' if present else 'does not contain'} {mark}."
        if op in {"starts_with", "ends_with", "contains_text"}:
            positive, negative = {
                "starts_with": ("starts with", "does not start with"),
                "ends_with": ("ends with", "does not end with"),
                "contains_text": ("contains", "does not contain"),
            }[op]
            return f"The text “{left_value}” {positive if answer else negative} “{right_value}”."
    if op in {"greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal", "north_of", "south_of", "east_of", "west_of"}:
        try:
            left_number = float(left_value)
            right_number = float(right_value)
            comparison = "equal to" if left_number == right_number else "greater than" if left_number > right_number else "less than"
            return f"{number(left_number)} is {comparison} {number(right_number)}."
        except (TypeError, ValueError):
            return ""
    if op == "equals":
        def display(value) -> str:
            if isinstance(value, str):
                return f"“{value}”"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return number(value)
            return "an empty value" if value is None else "a provided value"

        return f"{display(left_value)} is {'equal' if answer else 'not equal'} to {display(right_value)}."
    if op == "contains" and isinstance(left_value, list):
        return f"The provided list {'contains' if answer else 'does not contain'} “{right_value}”."
    return ""


def execute_local_plan(
    plan: dict | list,
    country_name: str,
    improved_question: str,
) -> LocalAnswer | None:
    if not DEFAULT_DB_PATH.exists():
        return None
    if isinstance(plan, list):
        if not plan:
            return None
        if len(plan) == 1 and isinstance(plan[0], dict) and "args" not in plan[0]:
            plan = plan[0]
        else:
            try:
                from planner_protocol import compile_planner_response, PLANNER_OPERATORS
                from countrydle.local_planner import SUPPORTED_RELATIONS
                relations = set(SUPPORTED_RELATIONS) | {"coordinates.latitude", "coordinates.longitude", "region", "subregion", "hemisphere"}
                operators = PLANNER_OPERATORS | {"any", "all"}
                plan = compile_planner_response(
                    {"route": "local", "plan": plan},
                    relations=relations,
                    operators=operators,
                    target_entity="target_country",
                    allow_named_entities=True,
                )
            except Exception:
                plan = plan[-1] if isinstance(plan[-1], dict) else None
    if not isinstance(plan, dict):
        return None
    with sqlite3.connect(DEFAULT_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        country = find_country(conn, country_name)
        if country is None:
            return None
        plan = normalize_geographic_area_plan(conn, plan)
        if plan is None:
            return None
        fact_provenance = []
        answer = evaluate_plan_node(conn, plan, country, fact_provenance=fact_provenance)
        if answer is None:
            return None
        relations = sorted(plan_relations(plan)) or ["local_plan"]
        explanation = generate_factual_explanation(
            conn, country, plan, answer
        )
        return LocalAnswer(
            question=improved_question,
            answer=answer,
            explanation=explanation,
            relation="+".join(relations),
            fact_provenance=fact_provenance,
        )
