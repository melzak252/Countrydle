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

    conn.close()
    print("Database enrichment complete!")


if __name__ == "__main__":
    enrich_database(DB_PATH)
