"""Enrich and rebuild Powiatdle local facts with authoritative geographical data.

Fixes and enriches:
1. `powiat_borders_countries`: Exact, verified international borders for Poland's 7 neighbors.
   Completely removes false positives (e.g. Podlaskie/interior counties bordering Germany).
2. `powiat_major_rivers`: Complete coverage of Poland's major rivers (Wisła, Odra, Warta, Bug,
   Narew, San, Pilica, Dunajec, Brda, etc.) across all traversed counties.
3. `powiat_major_roads`: Complete coverage of Poland's Motorways (A1, A2, A4, A8, A18) and
   Expressways (S1, S2, S3, S5, S6, S7, S8, S10, S11, S12, S14, S16, S17, S19, S51, S52, S61, S74, S79, S86).
4. `powiat_water_access`: Baltic Sea (Morze Bałtyckie) access for all 19 coastal and maritime counties.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "powiat_facts.sqlite"

# 1. BORDER COUNTIES FOR POLAND'S 7 NEIGHBORS
# Maps country_name -> list of exact canonical powiat names or search substrings
COUNTRY_BORDERS: dict[str, list[str]] = {
    "Niemcy": [
        "Świnoujście",
        "Powiat policki",
        "Powiat gryfiński",
        "Powiat myśliborski",
        "Powiat gorzowski",
        "Powiat sulęciński",
        "Powiat słubicki",
        "Powiat krośnieński (województwo lubuskie)",
        "Powiat żarski",
        "Powiat żagański",
        "Powiat zgorzelecki",
    ],
    "Czechy": [
        "Powiat zgorzelecki",
        "Powiat lubański",
        "Powiat lwówecki",
        "Powiat karkonoski",
        "Powiat kamiennogórski",
        "Powiat wałbrzyski",
        "Powiat kłodzki",
        "Powiat ząbkowicki",
        "Powiat nyski",
        "Powiat prudnicki",
        "Powiat głubczycki",
        "Powiat raciborski",
        "Powiat wodzisławski",
        "Jastrzębie-Zdrój",
        "Powiat cieszyński",
        "Powiat żywiecki",
    ],
    "Słowacja": [
        "Powiat żywiecki",
        "Powiat nowotarski",
        "Powiat tatrzański",
        "Powiat nowosądecki",
        "Powiat gorlicki",
        "Powiat jasielski",
        "Powiat krośnieński (województwo podkarpackie)",
        "Powiat sanocki",
        "Powiat leski",
        "Powiat bieszczadzki",
    ],
    "Ukraina": [
        "Powiat bieszczadzki",
        "Powiat przemyski",
        "Powiat jarosławski",
        "Powiat lubaczowski",
        "Powiat tomaszowski (województwo lubelskie)",
        "Powiat hrubieszowski",
        "Powiat chełmski",
        "Powiat włodawski",
    ],
    "Białoruś": [
        "Powiat włodawski",
        "Powiat bialski",
        "Powiat siemiatycki",
        "Powiat hajnowski",
        "Powiat białostocki",
        "Powiat sokólski",
        "Powiat augustowski",
    ],
    "Litwa": [
        "Powiat sejneński",
        "Powiat suwalski",
    ],
    "Rosja": [
        "Powiat nowodworski (województwo pomorskie)",
        "Powiat braniewski",
        "Powiat bartoszycki",
        "Powiat kętrzyński",
        "Powiat węgorzewski",
        "Powiat gołdapski",
        "Powiat suwalski",
    ],
}

# 2. COASTAL POWIATS WITH BALTIC SEA ACCESS (Morze Bałtyckie)
BALTIC_COASTAL_POWIATS: list[str] = [
    "Świnoujście",
    "Powiat kamieński",
    "Powiat gryficki",
    "Powiat kołobrzeski",
    "Powiat koszaliński",
    "Koszalin",
    "Powiat sławieński",
    "Powiat słupski",
    "Słupsk",
    "Powiat lęborski",
    "Powiat wejherowski",
    "Powiat pucki",
    "Gdynia",
    "Sopot",
    "Gdańsk",
    "Powiat nowodworski (województwo pomorskie)",
    "Powiat elbląski",
    "Powiat braniewski",
    "Powiat policki",
    "Szczecin",
]

# 3. MAJOR RIVERS IN POLAND AND TRAVERSED COUNTIES
RIVERS_TO_POWIATS: dict[str, list[str]] = {
    "Wisła": [
        "Powiat cieszyński", "Powiat bielski (województwo śląskie)", "Bielsko-Biała", "Powiat pszczyński", "Powiat bieruńsko-lędziński",
        "Powiat oświęcimski", "Powiat chrzanowski", "Powiat krakowski", "Kraków", "Powiat wielicki", "Powiat proszowicki",
        "Powiat bocheński", "Powiat brzeski (województwo małopolskie)", "Powiat tarnowski", "Powiat dąbrowski",
        "Powiat kazimierski", "Powiat buski", "Powiat staszowski", "Powiat sandomierski", "Powiat opatowski",
        "Powiat mielecki", "Powiat tarnobrzeski", "Tarnobrzeg", "Powiat stalowowolski",
        "Powiat kraśnicki", "Powiat opolski (województwo lubelskie)", "Powiat puławski", "Powiat rycki",
        "Powiat lipski", "Powiat kozienicki", "Powiat garwoliński", "Powiat otwocki", "Powiat piaseczyński",
        "Warszawa", "Powiat warszawski zachodni", "Powiat legionowski", "Powiat nowodworski (województwo mazowieckie)",
        "Powiat płoński", "Powiat sochaczewski", "Powiat płocki", "Płock", "Powiat gostyniński",
        "Powiat włocławski", "Włocławek", "Powiat aleksandrowski", "Powiat toruński", "Toruń", "Powiat bydgoski",
        "Bydgoszcz", "Powiat chełmiński", "Powiat świecki", "Powiat grudziądzki", "Grudziądz",
        "Powiat kwidzyński", "Powiat sztumski", "Powiat tczewski", "Powiat malborski", "Powiat gdański", "Gdańsk",
        "Powiat nowodworski (województwo pomorskie)",
    ],
    "Odra": [
        "Powiat wodzisławski", "Powiat raciborski",
        "Powiat kędzierzyńsko-kozielski", "Powiat krapkowicki", "Opole", "Powiat opolski (województwo opolskie)", "Powiat brzeski (województwo opolskie)",
        "Powiat oławski", "Powiat wrocławski", "Wrocław", "Powiat średzki (województwo dolnośląskie)", "Powiat trzebnicki",
        "Powiat wołowski", "Powiat legnicki", "Powiat lubiński", "Powiat głogowski", "Powiat górowski",
        "Powiat wschowski", "Powiat nowosolski", "Powiat zielonogórski", "Zielona Góra", "Powiat krośnieński (województwo lubuskie)",
        "Powiat słubicki", "Powiat gorzowski",
        "Powiat myśliborski", "Powiat gryfiński", "Szczecin", "Powiat policki",
    ],
    "Warta": [
        "Powiat zawierciański", "Powiat myszkowski", "Powiat częstochowski", "Częstochowa", "Powiat kłobucki",
        "Powiat pajęczański", "Powiat wieluński", "Powiat sieradzki", "Powiat zduńskowolski", "Powiat poddębicki",
        "Powiat kolski", "Powiat koniński", "Konin", "Powiat słupecki", "Powiat wrzesiński", "Powiat średzki (województwo wielkopolskie)",
        "Powiat poznański", "Poznań", "Powiat szamotulski", "Powiat obornicki", "Powiat czarnkowsko-trzcianecki", "Powiat międzychodzki",
        "Powiat strzelecko-drezdenecki", "Powiat gorzowski", "Gorzów Wielkopolski", "Powiat sulęciński", "Powiat słubicki",
    ],
    "Bug": [
        "Powiat tomaszowski (województwo lubelskie)", "Powiat hrubieszowski", "Powiat chełmski", "Chełm", "Powiat włodawski",
        "Powiat bialski", "Biała Podlaska",
        "Powiat siemiatycki",
        "Powiat łosicki", "Powiat siedlecki", "Powiat sokołowski", "Powiat ostrowski (województwo mazowieckie)", "Powiat węgrowski",
        "Powiat wyszkowski", "Powiat wołomiński", "Powiat legionowski", "Powiat nowodworski (województwo mazowieckie)",
    ],
    "Narew": [
        "Powiat hajnowski", "Powiat bielski (województwo podlaskie)", "Powiat białostocki", "Białystok", "Powiat moniecki",
        "Powiat łomżyński", "Łomża", "Powiat kolneński",
        "Powiat ostrołęcki", "Ostrołęka", "Powiat makowski", "Powiat pułtuski", "Powiat legionowski", "Powiat nowodworski (województwo mazowieckie)",
    ],
    "San": [
        "Powiat bieszczadzki", "Powiat leski", "Powiat sanocki", "Powiat brzozowski", "Powiat przemyski", "Przemyśl",
        "Powiat jarosławski", "Powiat przeworski", "Powiat leżajski", "Powiat niżański", "Powiat stalowowolski",
    ],
    "Noteć": [
        "Powiat mogileński", "Powiat inowrocławski", "Powiat żniński", "Powiat nakielski",
        "Powiat pilski", "Powiat chodzieski", "Powiat czarnkowsko-trzcianecki",
        "Powiat strzelecko-drezdenecki", "Powiat gorzowski",
    ],
    "Pilica": [
        "Powiat zawierciański",
        "Powiat włoszczowski", "Powiat konecki",
        "Powiat radomszczański", "Powiat piotrkowski", "Piotrków Trybunalski", "Powiat tomaszowski (województwo łódzkie)", "Powiat opoczyński",
        "Powiat grójecki", "Powiat białobrzeski", "Powiat kozienicki",
    ],
    "Wieprz": [
        "Powiat tomaszowski (województwo lubelskie)", "Powiat zamojski", "Powiat krasnostawski", "Powiat świdnicki (województwo lubelskie)",
        "Powiat łęczyński", "Powiat lubartowski", "Powiat puławski", "Powiat rycki",
    ],
    "Bóbr": [
        "Powiat kamiennogórski", "Powiat karkonoski", "Jelenia Góra", "Powiat lwówecki", "Powiat bolesławiecki",
        "Powiat żagański", "Powiat żarski", "Powiat krośnieński (województwo lubuskie)",
    ],
    "Dunajec": [
        "Powiat nowotarski", "Powiat tatrzański", "Powiat nowosądecki", "Nowy Sącz", "Powiat brzeski (województwo małopolskie)",
        "Powiat tarnowski", "Tarnów", "Powiat dąbrowski",
    ],
    "Brda": [
        "Powiat bytowski", "Powiat człuchowski", "Powiat chojnicki",
        "Powiat tucholski", "Powiat bydgoski", "Bydgoszcz",
    ],
    "Drwęca": [
        "Powiat ostródzki", "Powiat nowomiejski",
        "Powiat brodnicki", "Powiat rypiński", "Powiat golubsko-dobrzyński", "Powiat toruński", "Toruń",
    ],
    "Gwda": [
        "Powiat człuchowski", "Powiat złotowski", "Powiat pilski",
    ],
    "Nysa Łużycka": [
        "Powiat zgorzelecki", "Powiat żarski", "Powiat krośnieński (województwo lubuskie)",
    ],
    "Nysa Kłodzka": [
        "Powiat kłodzki", "Powiat ząbkowicki", "Powiat nyski", "Powiat brzeski (województwo opolskie)",
    ],
    "Pasłęka": [
        "Powiat olsztyński", "Powiat ostródzki", "Powiat lidzbarski", "Powiat braniewski",
    ],
    "Łyna": [
        "Powiat nidzicki", "Powiat olsztyński", "Olsztyn", "Powiat lidzbarski", "Powiat bartoszycki",
    ],
    "Prosna": [
        "Powiat oleski", "Powiat wieruszowski", "Powiat ostrzeszowski", "Powiat ostrowski (województwo wielkopolskie)",
        "Powiat kaliski", "Kalisz", "Powiat pleszewski", "Powiat wrzesiński",
    ],
    "Bzura": [
        "Powiat zgierski", "Powiat łęczycki", "Powiat łowicki", "Powiat sochaczewski",
    ],
    "Wkra": [
        "Powiat nidzicki", "Powiat działdowski", "Powiat mławski", "Powiat żuromiński", "Powiat płoński", "Powiat nowodworski (województwo mazowieckie)",
    ],
    "Drawa": [
        "Powiat drawski", "Powiat choszczeński", "Powiat czarnkowsko-trzcianecki", "Powiat strzelecko-drezdenecki",
    ],
    "Ina": [
        "Powiat stargardzki", "Powiat goleniowski",
    ],
    "Parsęta": [
        "Powiat szczecinecki", "Powiat białogardzki", "Powiat kołobrzeski",
    ],
    "Rega": [
        "Powiat świdwiński", "Powiat łobeski", "Powiat gryficki",
    ],
    "Słupia": [
        "Powiat bytowski", "Powiat słupski", "Słupsk",
    ],
    "Radunia": [
        "Powiat kartuski", "Powiat gdański", "Gdańsk",
    ],
    "Biebrza": [
        "Powiat sokólski", "Powiat augustowski", "Powiat moniecki", "Powiat grajewski", "Powiat łomżyński",
    ],
    "Czarna Hańcza": [
        "Powiat suwalski", "Suwałki", "Powiat sejneński", "Powiat augustowski",
    ],
    "Wisłok": [
        "Powiat krośnieński (województwo podkarpackie)", "Krosno", "Powiat strzyżowski", "Powiat rzeszowski", "Rzeszów",
        "Powiat łańcucki", "Powiat przeworski",
    ],
    "Wisłoka": [
        "Powiat jasielski", "Powiat dębicki", "Powiat mielecki",
    ],
    "Poprad": [
        "Powiat nowosądecki",
    ],
    "Raba": [
        "Powiat nowotarski", "Powiat myślenicki", "Powiat bocheński",
    ],
    "Skawa": [
        "Powiat nowotarski", "Powiat suski", "Powiat wadowicki", "Powiat oświęcimski",
    ],
    "Soła": [
        "Powiat żywiecki", "Żywiec", "Powiat bielski (województwo śląskie)", "Powiat oświęcimski",
    ],
    "Olza": [
        "Powiat cieszyński", "Powiat wodzisławski",
    ],
    "Kłodnica": [
        "Katowice", "Ruda Śląska", "Zabrze", "Gliwice", "Powiat gliwicki", "Powiat strzelecki", "Powiat kędzierzyńsko-kozielski",
    ],
    "Bystrzyca": [
        "Powiat kraśnicki", "Powiat lubelski", "Lublin", "Powiat łęczyński",
        "Powiat wałbrzyski", "Wałbrzych", "Powiat świdnicki (województwo dolnośląskie)", "Powiat wrocławski", "Wrocław",
    ],
    "Kamienna": [
        "Powiat szydłowiecki", "Powiat lipski", "Powiat skarżyski", "Powiat starachowicki", "Powiat ostrowiecki", "Powiat opatowski",
    ],
    "Nida": [
        "Powiat jędrzejowski", "Powiat kielecki", "Powiat pińczowski", "Powiat buski", "Powiat kazimierski",
    ],
    "Krzna": [
        "Powiat łukowski", "Powiat radzyński", "Powiat bialski", "Biała Podlaska",
    ],
    "Liwiec": [
        "Powiat siedlecki", "Siedlce", "Powiat węgrowski", "Powiat wołomiński", "Powiat wyszkowski",
    ],
}

# 4. MAJOR MOTORWAYS & EXPRESSWAYS ACROSS TRAVERSED POWIATS
ROADS_TO_POWIATS: dict[str, list[str]] = {
    "A1": [
        "Gdańsk", "Powiat gdański", "Powiat tczewski", "Powiat starogardzki", "Powiat świecki", "Powiat chełmiński",
        "Powiat toruński", "Toruń", "Powiat aleksandrowski", "Powiat włocławski", "Włocławek", "Powiat kutnowski",
        "Powiat zgierski", "Powiat łódzki wschodni", "Łódź", "Powiat piotrkowski", "Piotrków Trybunalski",
        "Powiat radomszczański", "Powiat częstochowski", "Częstochowa", "Powiat kłobucki", "Powiat tarnogórski",
        "Piekary Śląskie", "Bytom", "Zabrze", "Gliwice", "Powiat gliwicki", "Powiat rybnicki", "Żory", "Powiat wodzisławski",
    ],
    "A2": [
        "Powiat słubicki", "Powiat sulęciński", "Powiat świebodziński", "Powiat nowotomyski", "Powiat poznański", "Poznań",
        "Powiat wrzesiński", "Powiat słupecki", "Powiat koniński", "Konin", "Powiat kolski", "Powiat poddębicki",
        "Powiat zgierski", "Powiat brzeziński", "Powiat skierniewicki", "Powiat łowicki", "Powiat żyrardowski",
        "Powiat grodziski (województwo mazowieckie)", "Powiat pruszkowski", "Warszawa", "Powiat miński", "Powiat siedlecki",
    ],
    "A4": [
        "Powiat zgorzelecki", "Powiat bolesławiecki", "Powiat złotoryjski", "Powiat legnicki", "Legnica", "Powiat jaworski",
        "Powiat średzki (województwo dolnośląskie)", "Powiat wrocławski", "Wrocław", "Powiat oławski",
        "Powiat brzeski (województwo opolskie)", "Powiat opolski (województwo opolskie)", "Powiat strzelecki", "Powiat krapkowicki",
        "Powiat gliwicki", "Gliwice", "Zabrze", "Ruda Śląska", "Chorzów", "Katowice", "Mysłowice", "Jaworzno",
        "Powiat chrzanowski", "Powiat krakowski", "Kraków", "Powiat wielicki", "Powiat bocheński",
        "Powiat brzeski (województwo małopolskie)", "Powiat tarnowski", "Tarnów", "Powiat dębicki",
        "Powiat ropczycko-sędziszowski", "Powiat rzeszowski", "Rzeszów", "Powiat łańcucki", "Powiat przeworski",
        "Powiat jarosławski", "Powiat przemyski",
    ],
    "A8": [
        "Wrocław", "Powiat wrocławski",
    ],
    "A18": [
        "Powiat żarski", "Powiat żagański", "Powiat bolesławiecki",
    ],
    "S1": [
        "Powiat będziński", "Dąbrowa Górnicza", "Sosnowiec", "Mysłowice", "Tychy", "Powiat bieruńsko-lędziński",
        "Powiat pszczyński", "Bielsko-Biała", "Powiat bielski (województwo śląskie)", "Powiat żywiecki",
    ],
    "S2": [
        "Powiat pruszkowski", "Warszawa", "Powiat otwocki",
    ],
    "S3": [
        "Świnoujście", "Powiat kamieński", "Powiat goleniowski", "Szczecin", "Powiat gryfiński", "Powiat myśliborski",
        "Powiat gorzowski", "Gorzów Wielkopolski", "Powiat międzyrzecki", "Powiat świebodziński", "Powiat zielonogórski",
        "Zielona Góra", "Powiat nowosolski", "Powiat polkowicki", "Powiat lubiński", "Powiat legnicki", "Legnica",
        "Powiat jaworski", "Powiat kamiennogórski",
    ],
    "S5": [
        "Powiat ostródzki", "Powiat grudziądzki", "Grudziądz", "Powiat świecki", "Powiat bydgoski", "Bydgoszcz",
        "Powiat nakielski", "Powiat żniński", "Powiat gnieźnieński", "Powiat poznański", "Poznań", "Powiat kościański",
        "Powiat leszczyński", "Leszno", "Powiat rawicki", "Powiat trzebnicki", "Powiat wrocławski", "Wrocław",
    ],
    "S6": [
        "Szczecin", "Powiat goleniowski", "Powiat kołobrzeski", "Powiat koszaliński", "Koszalin", "Powiat sławieński",
        "Powiat słupski", "Słupsk", "Powiat lęborski", "Powiat wejherowski", "Gdynia", "Gdańsk",
    ],
    "S7": [
        "Gdańsk", "Powiat gdański", "Powiat nowodworski (województwo pomorskie)", "Powiat elbląski", "Elbląg",
        "Powiat ostródzki", "Powiat olsztyński", "Powiat nidzicki", "Powiat mławski", "Powiat płoński",
        "Powiat nowodworski (województwo mazowieckie)", "Warszawa", "Powiat piaseczyński", "Powiat grójecki",
        "Powiat białobrzeski", "Powiat radomski", "Radom", "Powiat szydłowiecki", "Powiat skarżyski",
        "Powiat starachowicki", "Powiat kielecki", "Kielce", "Powiat jędrzejowski", "Powiat miechowski",
        "Powiat krakowski", "Kraków", "Powiat myślenicki", "Powiat nowotarski",
    ],
    "S8": [
        "Powiat kłodzki", "Powiat ząbkowicki", "Powiat dzierżoniowski", "Powiat wrocławski", "Wrocław",
        "Powiat oleśnicki", "Powiat kępiński", "Powiat wieruszowski", "Powiat sieradzki", "Powiat łaski",
        "Powiat pabianicki", "Łódź", "Powiat piotrkowski", "Piotrków Trybunalski", "Powiat tomaszowski (województwo łódzkie)",
        "Powiat rawski", "Powiat żyrardowski", "Powiat grodziski (województwo mazowieckie)", "Powiat pruszkowski",
        "Warszawa", "Powiat wołomiński", "Powiat wyszkowski", "Powiat ostrowski (województwo mazowieckie)",
        "Powiat zambrowski", "Powiat białostocki", "Białystok",
    ],
    "S10": [
        "Szczecin", "Powiat stargardzki", "Powiat choszczeński", "Powiat wałecki", "Powiat pilski", "Powiat nakielski",
        "Powiat bydgoski", "Bydgoszcz", "Powiat toruński", "Toruń", "Powiat lipnowski", "Powiat sierpecki", "Powiat płoński",
    ],
    "S11": [
        "Powiat kołobrzeski", "Powiat koszaliński", "Koszalin", "Powiat szczecinecki", "Powiat złotowski", "Powiat pilski",
        "Powiat chodzieski", "Powiat obornicki", "Powiat poznański", "Poznań", "Powiat średzki (województwo wielkopolskie)",
        "Powiat jarociński", "Powiat pleszewski", "Powiat ostrowski (województwo wielkopolskie)",
        "Powiat ostrzeszowski", "Powiat kępiński", "Powiat oleski", "Powiat lubliniecki", "Powiat tarnogórski",
    ],
    "S12": [
        "Piotrków Trybunalski", "Powiat tomaszowski (województwo łódzkie)", "Powiat opoczyński", "Powiat radomski", "Radom",
        "Powiat puławski", "Powiat lubelski", "Lublin", "Powiat świdnicki (województwo lubelskie)", "Powiat chełmski", "Chełm",
    ],
    "S14": [
        "Łódź", "Powiat zgierski", "Powiat pabianicki",
    ],
    "S16": [
        "Olsztyn", "Powiat olsztyński", "Powiat mrągowski", "Powiat ełcki",
    ],
    "S17": [
        "Warszawa", "Powiat otwocki", "Powiat garwoliński", "Powiat rycki", "Powiat puławski", "Powiat lubelski", "Lublin",
        "Powiat świdnicki (województwo lubelskie)", "Powiat krasnostawski", "Powiat zamojski", "Zamość", "Powiat tomaszowski (województwo lubelskie)",
    ],
    "S19": [
        "Powiat sokólski", "Powiat białostocki", "Białystok", "Powiat bielski (województwo podlaskie)", "Powiat siemiatycki",
        "Powiat łosicki", "Powiat radzyński", "Powiat lubartowski", "Powiat lubelski", "Lublin", "Powiat kraśnicki",
        "Powiat janowski", "Powiat niżański", "Powiat leżajski", "Powiat rzeszowski", "Rzeszów", "Powiat strzyżowski",
        "Powiat krośnieński (województwo podkarpackie)", "Krosno", "Powiat sanocki",
    ],
    "S51": [
        "Powiat olsztyński", "Olsztyn",
    ],
    "S52": [
        "Powiat cieszyński", "Powiat bielski (województwo śląskie)", "Bielsko-Biała", "Powiat krakowski", "Kraków",
    ],
    "S61": [
        "Powiat ostrowski (województwo mazowieckie)", "Powiat łomżyński", "Łomża", "Powiat kolneński", "Powiat grajewski",
        "Powiat ełcki", "Powiat olecki", "Powiat suwalski", "Suwałki",
    ],
    "S74": [
        "Powiat piotrkowski", "Powiat opoczyński", "Powiat konecki", "Powiat kielecki", "Kielce", "Powiat opatowski",
        "Powiat sandomierski", "Powiat stalowowolski",
    ],
    "S79": [
        "Warszawa",
    ],
    "S86": [
        "Katowice", "Sosnowiec", "Powiat będziński",
    ],
}

PARKS_TO_POWIATS: dict[str, list[str]] = {
    "Tatrzański Park Narodowy": ["Powiat tatrzański"],
    "Białowieski Park Narodowy": ["Powiat hajnowski"],
    "Bieszczadzki Park Narodowy": ["Powiat bieszczadzki", "Powiat leski"],
    "Karkonoski Park Narodowy": ["Powiat karkonoski", "Jelenia Góra"],
    "Słowiński Park Narodowy": ["Powiat słupski", "Powiat lęborski"],
    "Kampinoski Park Narodowy": ["Powiat warszawski zachodni", "Powiat nowodworski (województwo mazowieckie)", "Powiat sochaczewski"],
    "Ojcowski Park Narodowy": ["Powiat krakowski"],
    "Pieniński Park Narodowy": ["Powiat nowotarski"],
    "Biebrzański Park Narodowy": ["Powiat moniecki", "Powiat augustowski", "Powiat grajewski", "Powiat sokólski"],
    "Woliński Park Narodowy": ["Powiat kamieński", "Świnoujście"],
    "Wigierski Park Narodowy": ["Powiat suwalski", "Powiat sejneński"],
    "Roztoczański Park Narodowy": ["Powiat zamojski", "Powiat biłgorajski"],
    "Świętokrzyski Park Narodowy": ["Powiat kielecki", "Powiat ostrowiecki", "Powiat starachowicki"],
    "Bory Tucholskie": ["Powiat chojnicki"],
    "Drawieński Park Narodowy": ["Powiat choszczeński", "Powiat wałecki", "Powiat strzelecko-drezdenecki"],
    "Gorczański Park Narodowy": ["Powiat limanowski", "Powiat nowotarski"],
    "Park Narodowy Gór Stołowych": ["Powiat kłodzki"],
    "Magurski Park Narodowy": ["Powiat jasielski", "Powiat gorlicki", "Powiat krośnieński (województwo podkarpackie)"],
    "Narwiański Park Narodowy": ["Powiat białostocki", "Powiat wysokomazowiecki"],
    "Poleski Park Narodowy": ["Powiat włodawski", "Powiat łęczyński", "Powiat parczewski"],
    "Babiogórski Park Narodowy": ["Powiat suski", "Powiat nowotarski"],
    "Park Narodowy Ujście Warty": ["Powiat słubicki", "Powiat gorzowski", "Powiat sulęciński"],
    "Wielkopolski Park Narodowy": ["Powiat poznański"],
}

LAKES_TO_POWIATS: dict[str, list[str]] = {
    "Śniardwy": ["Powiat piski"],
    "Mamry": ["Powiat węgorzewski", "Powiat giżycki"],
    "Jeziorak": ["Powiat iławski"],
    "Dąbie": ["Szczecin", "Powiat goleniowski"],
    "Miedwie": ["Powiat stargardzki", "Powiat gryfiński"],
    "Łebsko": ["Powiat słupski", "Powiat lęborski"],
    "Gardno": ["Powiat słupski"],
    "Jamno": ["Koszalin", "Powiat koszaliński"],
    "Gopło": ["Powiat inowrocławski", "Powiat mogileński", "Powiat koniński"],
    "Wigry": ["Powiat suwalski", "Powiat sejneński"],
    "Hańcza": ["Powiat suwalski"],
    "Morskie Oko": ["Powiat tatrzański"],
    "Czarny Staw": ["Powiat tatrzański"],
    "Solina": ["Powiat leski", "Powiat bieszczadzki"],
    "Zalew Zegrzyński": ["Powiat legionowski"],
    "Zbiornik Włocławski": ["Powiat włocławski", "Włocławek", "Powiat płocki", "Płock"],
    "Zbiornik Sulejowski": ["Powiat tomaszowski (województwo łódzkie)", "Powiat piotrkowski", "Powiat opoczyński"],
    "Zbiornik Jeziorsko": ["Powiat sieradzki", "Powiat poddębicki", "Powiat turecki"],
    "Jezioro Rożnowskie": ["Powiat nowosądecki"],
    "Jezioro Czorsztyńskie": ["Powiat nowotarski"],
    "Jezioro Żywieckie": ["Powiat żywiecki"],
    "Jezioro Otmuchowskie": ["Powiat nyski"],
    "Jezioro Nyskie": ["Powiat nyski"],
    "Drawsko": ["Powiat drawski"],
    "Wdzydze": ["Powiat kościerski"],
    "Charzykowskie": ["Powiat chojnicki"],
    "Powidzkie": ["Powiat słupecki"],
}

UNESCO_TO_POWIATS: dict[str, list[str]] = {
    "Historyczne centrum Krakowa": ["Kraków"],
    "Kopalnia soli w Wieliczce": ["Powiat wielicki"],
    "Kopalnia soli w Bochni": ["Powiat bocheński"],
    "Auschwitz-Birkenau": ["Powiat oświęcimski"],
    "Puszcza Białowieska": ["Powiat hajnowski"],
    "Historyczne centrum Warszawy": ["Warszawa"],
    "Stare Miasto w Zamościu": ["Zamość"],
    "Zamek w Malborku": ["Powiat malborski"],
    "Średniowieczny zespół miejski Torunia": ["Toruń"],
    "Kalwaria Zebrzydowska": ["Powiat wadowicki"],
    "Kościoły Pokoju w Jaworze i Świdnicy": ["Powiat jaworski", "Powiat świdnicki (województwo dolnośląskie)"],
    "Drewniane kościoły południowej Małopolski": ["Powiat gorlicki", "Powiat nowotarski", "Powiat tarnowski", "Powiat brzozowski"],
    "Park Mużakowski": ["Powiat żarski"],
    "Hala Stulecia we Wrocławiu": ["Wrocław"],
    "Drewniane cerkwie w Karpatach": ["Powiat bieszczadzki", "Powiat leski", "Powiat sanocki", "Powiat przemyski", "Powiat gorlicki", "Powiat nowosądecki"],
    "Kopalnia rud ołowiu, srebra i cynku w Tarnowskich Górach": ["Powiat tarnogórski", "Bytom"],
    "Krzemionki Opatowskie": ["Powiat ostrowiecki", "Powiat opatowski"],
    "Lasy bukowe w Bieszczadach": ["Powiat bieszczadzki"],
}

SPAS_TO_POWIATS: dict[str, list[str]] = {
    "Ciechocinek": ["Powiat aleksandrowski"],
    "Kołobrzeg": ["Powiat kołobrzeski"],
    "Krynica-Zdrój": ["Powiat nowosądecki"],
    "Muszyna": ["Powiat nowosądecki"],
    "Piwniczna-Zdrój": ["Powiat nowosądecki"],
    "Żegiestów-Zdrój": ["Powiat nowosądecki"],
    "Szczawnica": ["Powiat nowotarski"],
    "Rabka-Zdrój": ["Powiat nowotarski"],
    "Zakopane": ["Powiat tatrzański"],
    "Wapienne": ["Powiat gorlicki"],
    "Wysowa-Zdrój": ["Powiat gorlicki"],
    "Busko-Zdrój": ["Powiat buski"],
    "Solec-Zdrój": ["Powiat buski"],
    "Nałęczów": ["Powiat puławski"],
    "Krasnobród": ["Powiat zamojski"],
    "Horyniec-Zdrój": ["Powiat lubaczowski"],
    "Iwonicz-Zdrój": ["Powiat krośnieński (województwo podkarpackie)"],
    "Rymanów-Zdrój": ["Powiat krośnieński (województwo podkarpackie)"],
    "Polańczyk": ["Powiat leski"],
    "Sopot": ["Sopot"],
    "Ustka": ["Powiat słupski"],
    "Dąbki": ["Powiat sławieński"],
    "Kamień Pomorski": ["Powiat kamieński"],
    "Połczyn-Zdrój": ["Powiat świdwiński"],
    "Świnoujście": ["Świnoujście"],
    "Augustów": ["Powiat augustowski"],
    "Supraśl": ["Powiat białostocki"],
    "Gołdap": ["Powiat gołdapski"],
    "Konstancin-Jeziorna": ["Powiat piaseczyński"],
    "Uniejów": ["Powiat poddębicki"],
    "Cieplice Śląskie-Zdrój": ["Jelenia Góra"],
    "Świeradów-Zdrój": ["Powiat lubański"],
    "Czerniawa-Zdrój": ["Powiat lubański"],
    "Szczawno-Zdrój": ["Powiat wałbrzyski"],
    "Jedlina-Zdrój": ["Powiat wałbrzyski"],
    "Duszniki-Zdrój": ["Powiat kłodzki"],
    "Kudowa-Zdrój": ["Powiat kłodzki"],
    "Polanica-Zdrój": ["Powiat kłodzki"],
    "Lądek-Zdrój": ["Powiat kłodzki"],
    "Długopole-Zdrój": ["Powiat kłodzki"],
    "Przerzeczyn-Zdrój": ["Powiat dzierżoniowski"],
    "Goczałkowice-Zdrój": ["Powiat pszczyński"],
    "Ustroń": ["Powiat cieszyński"],
    "Jaworze": ["Powiat bielski (województwo śląskie)"],
    "Swoszowice": ["Kraków"],
}



def find_powiat_id(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute("SELECT id FROM powiats WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    row = conn.execute("SELECT id FROM powiats WHERE LOWER(name) = ?", (name.lower(),)).fetchone()
    if row:
        return row[0]
    clean = name.replace("Powiat ", "").strip().lower()
    row = conn.execute("SELECT id FROM powiats WHERE LOWER(name) LIKE ?", (f"%{clean}%",)).fetchone()
    if row:
        return row[0]
    return None


def enrich_database(db_path: Path):
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    with conn:
        # Ensure schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS powiat_water_access (
                powiat_id INTEGER NOT NULL,
                water_name TEXT NOT NULL,
                PRIMARY KEY (powiat_id, water_name),
                FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_powiat_water ON powiat_water_access(water_name)")

        # 1. Clean and Rebuild International Borders
        print("Rebuilding powiat_borders_countries...")
        conn.execute("DELETE FROM powiat_borders_countries")
        border_inserts = []
        for country, powiat_names in COUNTRY_BORDERS.items():
            for p_name in powiat_names:
                pid = find_powiat_id(conn, p_name)
                if pid is None:
                    print(f"  WARNING: Could not find powiat '{p_name}' for country '{country}'")
                    continue
                border_inserts.append((pid, country))
        conn.executemany("INSERT OR IGNORE INTO powiat_borders_countries (powiat_id, country_name) VALUES (?, ?)", border_inserts)
        print(f"  -> Inserted {len(border_inserts)} country border records.")

        # 2. Clean and Rebuild Water Access (Baltic Sea)
        print("Populating powiat_water_access (Morze Bałtyckie)...")
        conn.execute("DELETE FROM powiat_water_access")
        coast_inserts = []
        for p_name in BALTIC_COASTAL_POWIATS:
            pid = find_powiat_id(conn, p_name)
            if pid is None:
                print(f"  WARNING: Could not find coastal powiat '{p_name}'")
                continue
            coast_inserts.append((pid, "Morze Bałtyckie"))
        conn.executemany("INSERT OR IGNORE INTO powiat_water_access (powiat_id, water_name) VALUES (?, ?)", coast_inserts)
        print(f"  -> Inserted {len(coast_inserts)} coastal water access records.")

        # 3. Clean and Rebuild Major Rivers
        print("Rebuilding powiat_major_rivers...")
        conn.execute("DELETE FROM powiat_major_rivers")
        river_inserts = []
        for river, powiat_names in RIVERS_TO_POWIATS.items():
            for p_name in powiat_names:
                pid = find_powiat_id(conn, p_name)
                if pid is None:
                    print(f"  WARNING: Could not find powiat '{p_name}' for river '{river}'")
                    continue
                river_inserts.append((pid, river))
        conn.executemany("INSERT OR IGNORE INTO powiat_major_rivers (powiat_id, river_name) VALUES (?, ?)", river_inserts)
        print(f"  -> Inserted {len(river_inserts)} river records across {len(RIVERS_TO_POWIATS)} major rivers.")

        # 4. Clean and Rebuild Major Roads (A and S)
        print("Rebuilding powiat_major_roads...")
        conn.execute("DELETE FROM powiat_major_roads")
        road_inserts = []
        for road, powiat_names in ROADS_TO_POWIATS.items():
            for p_name in powiat_names:
                pid = find_powiat_id(conn, p_name)
                if pid is None:
                    print(f"  WARNING: Could not find powiat '{p_name}' for road '{road}'")
                    continue
                road_inserts.append((pid, road))
        conn.executemany("INSERT OR IGNORE INTO powiat_major_roads (powiat_id, road_name) VALUES (?, ?)", road_inserts)
        print(f"  -> Inserted {len(road_inserts)} road records across {len(ROADS_TO_POWIATS)} motorways and expressways.")

        # 5. Populate Historical Regions and Partitions for All 380 Powiats
        print("Populating historical regions and partitions for all powiats...")
        conn.execute("CREATE TABLE IF NOT EXISTS powiat_historical_regions (powiat_id INTEGER NOT NULL, region_name TEXT NOT NULL, PRIMARY KEY (powiat_id, region_name))")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_powiat_hist_reg ON powiat_historical_regions(region_name)")
        conn.execute("CREATE TABLE IF NOT EXISTS powiat_historical_partitions (powiat_id INTEGER NOT NULL, partition_name TEXT NOT NULL, PRIMARY KEY (powiat_id, partition_name))")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_powiat_hist_part ON powiat_historical_partitions(partition_name)")
        conn.execute("DELETE FROM powiat_historical_regions")
        conn.execute("DELETE FROM powiat_historical_partitions")

        hist_reg_inserts = []
        hist_part_inserts = []
        landform_inserts = []

        all_powiats = conn.execute("SELECT id, name, voivodeship FROM powiats").fetchall()
        for p in all_powiats:
            pid = p["id"]
            pname = p["name"]
            woj = p["voivodeship"].lower()

            regions = set()
            partitions = set()

            # Partitions (Zabory & Ziemie Odzyskane)
            if woj in {"dolnośląskie", "zachodniopomorskie", "lubuskie", "opolskie", "warmińsko-mazurskie"}:
                partitions.update(["Ziemie Odzyskane", "Zabór pruski"])
            elif woj in {"wielkopolskie", "pomorskie"}:
                partitions.add("Zabór pruski")
            elif woj == "kujawsko-pomorskie":
                partitions.add("Zabór pruski")
                if any(x in pname.lower() for x in ["włocław", "lipnow", "rypiń", "radziej", "aleksandr"]):
                    partitions.add("Zabór rosyjski")
            elif woj in {"mazowieckie", "łódzkie", "lubelskie", "świętokrzyskie", "podlaskie"}:
                partitions.add("Zabór rosyjski")
            elif woj in {"małopolskie", "podkarpackie"}:
                partitions.update(["Zabór austriacki", "Galicja"])
            elif woj == "śląskie":
                if any(x in pname.lower() for x in ["cieszyn", "bielsk", "żywiec"]):
                    partitions.update(["Zabór austriacki", "Galicja"])
                elif any(x in pname.lower() for x in ["częstochow", "kłobuck", "myszkow", "zawierc", "będziń", "bedzin", "sosnowiec", "dąbrowa", "dabrowa", "jaworzno"]):
                    partitions.add("Zabór rosyjski")
                else:
                    partitions.update(["Ziemie Odzyskane", "Zabór pruski"])

            # Historical Lands (Krainy historyczne)
            if woj == "dolnośląskie":
                regions.update(["Dolny Śląsk", "Śląsk", "Sudety"])
            elif woj == "opolskie":
                regions.update(["Górny Śląsk", "Śląsk"])
            elif woj == "śląskie":
                if any(x in pname.lower() for x in ["cieszyn", "bielsk", "żywiec"]):
                    regions.update(["Górny Śląsk", "Śląsk", "Śląsk Cieszyński", "Małopolska", "Galicja", "Beskidy"])
                elif any(x in pname.lower() for x in ["częstochow", "kłobuck", "myszkow", "zawierc", "będziń", "bedzin", "sosnowiec", "dąbrowa", "dabrowa", "jaworzno"]):
                    regions.update(["Małopolska", "Zagłębie Dąbrowskie"])
                else:
                    regions.update(["Górny Śląsk", "Śląsk"])
            elif woj == "małopolskie":
                regions.update(["Małopolska", "Galicja"])
                if any(x in pname.lower() for x in ["tatrzań", "nowotar", "nowosąd", "gorlic", "suski"]):
                    regions.update(["Karpaty", "Podhale", "Beskidy"])
            elif woj == "podkarpackie":
                regions.update(["Małopolska", "Galicja", "Podkarpacie"])
                if any(x in pname.lower() for x in ["bieszczad", "leski", "sanoc", "krośnień", "jasiel"]):
                    regions.update(["Bieszczady", "Karpaty", "Beskidy"])
            elif woj == "świętokrzyskie":
                regions.update(["Małopolska", "Ziemia sandomierska", "Góry Świętokrzyskie"])
            elif woj == "lubelskie":
                regions.update(["Małopolska", "Lubelszczyzna"])
                if any(x in pname.lower() for x in ["chełm", "włodaw", "bialsk"]):
                    regions.add("Polesie")
            elif woj == "mazowieckie":
                regions.add("Mazowsze")
                if any(x in pname.lower() for x in ["radom", "szydłow", "lipsk", "kozienic"]):
                    regions.update(["Małopolska", "Ziemia radomska"])
            elif woj == "podlaskie":
                regions.add("Podlasie")
                if any(x in pname.lower() for x in ["łomż", "kolneń", "grajew", "zambrow"]):
                    regions.update(["Mazowsze", "Ziemia łomżyńska"])
                if any(x in pname.lower() for x in ["suwal", "sejneń", "augustow"]):
                    regions.add("Suwalszczyzna")
            elif woj == "łódzkie":
                regions.update(["Ziemia łódzka", "Ziemia sieradzka", "Ziemia łęczycka", "Wielkopolska"])
            elif woj == "wielkopolskie":
                regions.add("Wielkopolska")
            elif woj == "lubuskie":
                regions.update(["Ziemia lubuska", "Wielkopolska"])
                if any(x in pname.lower() for x in ["zielonogór", "nowosol", "żar", "żagań"]):
                    regions.update(["Dolny Śląsk", "Śląsk"])
            elif woj == "zachodniopomorskie":
                regions.update(["Pomorze Zachodnie", "Pomorze"])
            elif woj == "pomorskie":
                regions.update(["Pomorze Gdańskie", "Pomorze"])
                if any(x in pname.lower() for x in ["kartuz", "kościers", "wejherow", "puc", "bytow", "chojnic", "lębor", "gdyn", "gdań", "sopot"]):
                    regions.add("Kaszuby")
                if any(x in pname.lower() for x in ["starogard", "tczew"]):
                    regions.add("Kociewie")
            elif woj == "kujawsko-pomorskie":
                if any(x in pname.lower() for x in ["włocław", "inowrocław", "aleksandr", "radziej"]):
                    regions.add("Kujawy")
                if any(x in pname.lower() for x in ["toruń", "chełmiń", "grudziądz", "wąbrzeź"]):
                    regions.add("Ziemia chełmińska")
                if any(x in pname.lower() for x in ["rypiń", "lipnow", "golub"]):
                    regions.add("Ziemia dobrzyńska")
                if any(x in pname.lower() for x in ["świec", "tuchol"]):
                    regions.add("Pomorze")
                if any(x in pname.lower() for x in ["żniń", "mogileń"]):
                    regions.add("Wielkopolska")
                regions.add("Kujawy")
            elif woj == "warmińsko-mazurskie":
                if any(x in pname.lower() for x in ["olsztyn", "lidzbar", "braniew"]):
                    regions.add("Warmia")
                else:
                    regions.add("Mazury")
                regions.add("Pojezierze Mazurskie")

            for reg in regions:
                hist_reg_inserts.append((pid, reg))
                landform_inserts.append((pid, reg))
            for part in partitions:
                hist_part_inserts.append((pid, part))

        conn.executemany("INSERT OR IGNORE INTO powiat_historical_regions (powiat_id, region_name) VALUES (?, ?)", hist_reg_inserts)
        conn.executemany("INSERT OR IGNORE INTO powiat_historical_partitions (powiat_id, partition_name) VALUES (?, ?)", hist_part_inserts)
        conn.executemany("INSERT OR IGNORE INTO powiat_landform_regions (powiat_id, region_name) VALUES (?, ?)", landform_inserts)
        print(f"  -> Inserted {len(hist_reg_inserts)} historical region assignments.")
        print(f"  -> Inserted {len(hist_part_inserts)} historical partition assignments.")
        print(f"  -> Synced into powiat_landform_regions.")

        # 6. Clean and Rebuild National Parks
        print("Rebuilding powiat_national_parks...")
        conn.execute("CREATE TABLE IF NOT EXISTS powiat_national_parks (powiat_id INTEGER NOT NULL, park_name TEXT NOT NULL, PRIMARY KEY (powiat_id, park_name), FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_powiat_parks ON powiat_national_parks(park_name)")
        conn.execute("DELETE FROM powiat_national_parks")
        park_inserts = []
        for park, powiat_names in PARKS_TO_POWIATS.items():
            for p_name in powiat_names:
                pid = find_powiat_id(conn, p_name)
                if pid is None:
                    print(f"  WARNING: Could not find powiat '{p_name}' for park '{park}'")
                    continue
                park_inserts.append((pid, park))
        conn.executemany("INSERT OR IGNORE INTO powiat_national_parks (powiat_id, park_name) VALUES (?, ?)", park_inserts)
        print(f"  -> Inserted {len(park_inserts)} national park assignments across {len(PARKS_TO_POWIATS)} parks.")

        # 7. Clean and Rebuild Major Lakes
        print("Rebuilding powiat_lakes...")
        conn.execute("CREATE TABLE IF NOT EXISTS powiat_lakes (powiat_id INTEGER NOT NULL, lake_name TEXT NOT NULL, PRIMARY KEY (powiat_id, lake_name), FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_powiat_lakes ON powiat_lakes(lake_name)")
        conn.execute("DELETE FROM powiat_lakes")
        lake_inserts = []
        for lake, powiat_names in LAKES_TO_POWIATS.items():
            for p_name in powiat_names:
                pid = find_powiat_id(conn, p_name)
                if pid is None:
                    print(f"  WARNING: Could not find powiat '{p_name}' for lake '{lake}'")
                    continue
                lake_inserts.append((pid, lake))
        conn.executemany("INSERT OR IGNORE INTO powiat_lakes (powiat_id, lake_name) VALUES (?, ?)", lake_inserts)
        print(f"  -> Inserted {len(lake_inserts)} lake records across {len(LAKES_TO_POWIATS)} major lakes/reservoirs.")

        # 8. Clean and Rebuild UNESCO Sites
        print("Rebuilding powiat_unesco_sites...")
        conn.execute("CREATE TABLE IF NOT EXISTS powiat_unesco_sites (powiat_id INTEGER NOT NULL, site_name TEXT NOT NULL, PRIMARY KEY (powiat_id, site_name), FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_powiat_unesco ON powiat_unesco_sites(site_name)")
        conn.execute("DELETE FROM powiat_unesco_sites")
        unesco_inserts = []
        for site, powiat_names in UNESCO_TO_POWIATS.items():
            for p_name in powiat_names:
                pid = find_powiat_id(conn, p_name)
                if pid is None:
                    print(f"  WARNING: Could not find powiat '{p_name}' for UNESCO site '{site}'")
                    continue
                unesco_inserts.append((pid, site))
        conn.executemany("INSERT OR IGNORE INTO powiat_unesco_sites (powiat_id, site_name) VALUES (?, ?)", unesco_inserts)
        print(f"  -> Inserted {len(unesco_inserts)} UNESCO site assignments across {len(UNESCO_TO_POWIATS)} sites.")

        # 9. Clean and Rebuild Health Resorts / Spas
        print("Rebuilding powiat_health_resorts...")
        conn.execute("CREATE TABLE IF NOT EXISTS powiat_health_resorts (powiat_id INTEGER NOT NULL, resort_name TEXT NOT NULL, PRIMARY KEY (powiat_id, resort_name), FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_powiat_spas ON powiat_health_resorts(resort_name)")
        conn.execute("DELETE FROM powiat_health_resorts")
        spa_inserts = []
        for spa, powiat_names in SPAS_TO_POWIATS.items():
            for p_name in powiat_names:
                pid = find_powiat_id(conn, p_name)
                if pid is None:
                    print(f"  WARNING: Could not find powiat '{p_name}' for health resort '{spa}'")
                    continue
                spa_inserts.append((pid, spa))
        conn.executemany("INSERT OR IGNORE INTO powiat_health_resorts (powiat_id, resort_name) VALUES (?, ?)", spa_inserts)
        print(f"  -> Inserted {len(spa_inserts)} health resort records across {len(SPAS_TO_POWIATS)} statutory spas.")
    print("Database enrichment complete!")

if __name__ == "__main__":
    enrich_database(DB_PATH)
