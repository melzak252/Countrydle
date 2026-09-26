# Raport z Badań i Testów Adversarialnych: QA Playground dla Modeli Countrydle

Data: 2026-09-27  
Środowisko: `server/scripts/qa_playground.py` (model bazowy: `gemini-2.5-flash-lite`, wersja kontraktu: 26)  
Zakres: Wszystkie 4 tryby gry (`countrydle`, `wojewodztwodle`, `powiatdle`, `us_statedle`)

---

## 1. Podsumowanie Wykonawcze (Executive Summary)

W ramach eksperymentu uruchomiono armię 5 wyspecjalizowanych subagentów audytorskich, którzy wygenerowali i przetestowali łącznie **165 trudnych pytań brzegowych (adversarial edge cases)** w języku polskim i angielskim.

Wszystkie zapytania, wygenerowane plany AST, odpowiedzi, wyjaśnienia i kategoryzacje defektów zostały utrwalone w formacie JSONL w pliku `server/test_reports/qa_playground_findings.jsonl`.

### Wyniki ilościowe:
| Kategoria testów | Liczba przypadków | PASS | FAIL_LOGIC | FAIL_FALLTHROUGH | FAIL_INVALID | FAIL_CRASH |
|---|---|---|---|---|---|---|
| **Geografia państw (CountryGeo)** | 35 | 28 | 6 | 1 | 0 | 0 |
| **Polityka, unie, języki, flagi (CountryCiv)** | 35 | 22 | 6 | 7 | 0 | 0 |
| **Województwa (Wojewodztwodle)** | 30 | 16 | 6 | 5 | 3 | 0 |
| **Powiaty (Powiatdle)** | 35 | 17 | 4 | 3 | 11 | 0 |
| **Stany USA (USStatedle)** | 30 | 13 | 10 | 2 | 5 | 0 |
| **ŁĄCZNIE** | **165** | **96 (58.2%)** | **31 (18.8%)** | **18 (10.9%)** | **19 (11.5%)** | **1 (0.6%)** |

---

## 2. Siedem Głównych Klas Błędów Modelu (Defect Taxonomy)

Audyt ujawnił 7 powtarzalnych, systemowych klas błędów popełnianych przez model Gemini i silnik wykonawczy:

### Klasa 1: Odrzucanie pytań z nazwanym podmiotem (Named Subject False Rejection)
- **Mechanizm błędu**: Gdy gracz zadaje pytanie z zaimkiem (np. *„Czy to miasto na prawach powiatu?”* lub *„Does it use the euro?”*), model poprawnie generuje plan. Jednak gdy gracz użyje konkretnej nazwy podmiotu (np. *„Czy Kraków jest miastem na prawach powiatu?”*, *„Does Czechia use the euro?”*, *„Czy Małopolskie graniczy ze Słowacją?”*), model odrzuca pytanie jako `valid=false` lub `route=clarify`, twierdząc:
  > *„This question is about a specific entity (Poznań) and not the hidden target entity.”*
- **Wpływ na grę**: Gracze naturalnie wymieniają nazwy swoich podejrzeń w pytaniach. Odrzucanie ich jako niepoprawne pytania frustruje graczy.
- **Rekomendacja**: W prompcie planera we wszystkich trybach należy wyraźnie pouczyć model: *„Gdy gracz pyta o właściwość konkretnego nazwanego podmiotu (np. 'Czy Kraków to miasto na prawach powiatu?'), zinterpretuj to jako sprawdzenie tej właściwości dla kandydata lub pytanie o tożsamość.”*

---

### Klasa 2: Pomyłka operatorów: Skalar vs Lista (`equals` zamiast `contains_exact`)
- **Mechanizm błędu**:
  - W **Wojewodztwodle**: relacja `borders_country` jest listą (np. `['Czechy', 'Słowacja']`). Dla pytania *„Czy Małopolskie graniczy ze Słowacją?”* model wygenerował:
    `{"operator": "equals", "left": "borders_country", "right": "Słowacja"}` zamiast `contains_exact`! W efekcie ewaluator porównał listę z napisem operatorem `==` i zwrócił `False`!
  - W **USStatedle**: dla pytania *„Does Maine border only one state?”* model wygenerował:
    `{"operator": "word_count_equals", "left": "borders_state", "right": 1}`! Operator `word_count` służy do liczenia słów w tekście, a nie elementów na liście.
- **Rekomendacja**: W ewaluatorze `local_kb_question.py`, jeśli operator `equals` trafi na relację listową (`borders_country`, `borders_state`, `borders_voivodeship`), automatycznie potraktować go jako `contains_exact`.

---

### Klasa 3: Niezgodność etykiet i brak synonimów wartości (Label Mismatch)
- **Mechanizm błędu**:
  - **Waluty**: Model generuje `value: "US Dollar"` lub `value: "US dollar"`. W bazie SQLite w tabeli `country_currencies` waluta nazywa się `"United States dollar"`. Porównanie `contains` dało `False` dla Panamy i Salwadoru, mimo że system w wyjaśnieniu sam napisał, że walutą jest USD!
  - **Półkule**: Model generuje `value: "Northern Hemisphere"`. W tabeli `country_hemispheres` wartość to `"Northern"`. Ewaluator zwrócił kuriozalne wyjaśnienie: *„Kiribati is not located in the Northern Hemisphere Hemisphere”*.
  - **Województwa**: Model generuje nazwę stolicy `"Łódź"` zamiast `"Łódzkie"` dla `borders_voivodeship` (rozwiązane w poprzedniej poprawce przez `resolve_voivodeship_name`).
- **Rekomendacja**: Dodać normalizację wartości przed ewaluacją:
  - dla walut: synonimy kodów ISO (USD $\rightarrow$ United States dollar, EUR $\rightarrow$ Euro),
  - dla półkul: automatyczne obcięcie słowa `Hemisphere` / `półkula`.

---

### Klasa 4: Kraje transkontynentalne i luki w kategoryzacji kontynentów
- **Mechanizm błędu**:
  - **Egipt**: w bazie `country_continents` ma tylko `Africa`. Pytanie *„Does Egypt have territory in both Africa and Asia?”* dostało odpowiedź `False` (brak Półwyspu Synaj w Azji).
  - **Kazachstan**: w bazie ma tylko `Asia`. Pytanie *„Czy Kazachstan leży częściowo w Europie?”* dostało `False` (brak ziem na zachód od rzeki Ural).
  - **Gruzja / Azerbejdżan**: przypisane wyłącznie do Azji.
- **Rekomendacja**: Dodać transkontynentalne wpisy do `country_continents` dla Kazachstanu (Europa), Egiptu (Azja) oraz Turcji i Rosji (które już tam są).

---

### Klasa 5: Mylenie Unii Historycznej z Ustrojem Politycznym (Semantic Conflation)
- **Mechanizm błędu**: Pytanie: *„Was Poland a constituent republic of the Soviet Union?”* (Czy Polska była republiką radziecką w ZSRR?).
  Model zobaczył słowo *„republic”* i wygenerował plan:
  `{"operator": "equals", "left": "government_type", "right": "Republic"}`!
  Odpowiedział `Prawda` (bo Polska jest republiką), kompletnie ignorując kontekst ZSRR!
- **Rekomendacja**: Dodać do promptu regułę: pytania o ZSRR / republiki radzieckie muszą sprawdzać relację `historical_union: "USSR"`, a nie ustrój.

---

### Klasa 6: Homonimy powiatów i rozróżnienie miast od powiatów ziemskich
- **Mechanizm błędu**: W Powiatdle pytania o powiaty o tej samej nazwie (np. *powiat brzeski* w Małopolsce vs Opolskiem) generują plan `name == "Powiat brzeski"`. Ponieważ w bazie nazwa to `"Powiat brzeski (opolskie)"`, dokładne porównanie stringów daje `False`.
- **Rekomendacja**: W `resolve_powiat_name` uwzględniać dopisek województwa lub porównywać bazowy człon przymiotnikowy.

---

### Klasa 7: Kontakt punktowy (Four Corners) vs Krawędź graniczna
- **Mechanizm błędu**: W USA stany Utah, Kolorado, Arizona i Nowy Meksyk stykają się w jednym punkcie (*Four Corners*). Pytanie *„Does Utah border New Mexico?”* model zamienia na `borders_state`, co w GIS daje `False` (kontakt punktowy nie jest granicą liniową o dodatniej długości).
- **Rekomendacja**: To zachowanie jest geograficznie poprawne (punkt to nie granica), ale warto dodać precyzyjne wyjaśnienie w `generate_mode_explanation`: *„Utah spotyka się z Nowym Meksykiem jedynie w punkcie Four Corners, ale nie dzieli z nim linii granicznej.”*

---

## 3. Przykłady Kluczowych Awarii i Błędów Logicznych

| Tryb | Zadane pytanie | Błędny plan lub wynik | Prawidłowe zachowanie |
|---|---|---|---|
| `countrydle` | *Was Poland a constituent republic of the Soviet Union?* | `government_type == Republic` $\rightarrow$ **True** | Powinno sprawdzić `historical_union == USSR` i zwrócić **False**. |
| `countrydle` | *Is the US dollar an official currency in El Salvador?* | `currency contains "US Dollar"` $\rightarrow$ **False** | Baza ma `"United States dollar"`; powinno zwrócić **True**. |
| `countrydle` | *Does Kiribati have territory in all four hemispheres?* | `hemisphere contains "Northern Hemisphere"` $\rightarrow$ **False** | Baza ma `"Northern"`; powinno zwrócić **True**. |
| `countrydle` | *Does Egypt have territory in both Africa and Asia?* | `continent contains Asia` $\rightarrow$ **False** | Egipt leży też na Synaju (Azja); powinno zwrócić **True**. |
| `wojewodztwodle` | *Czy Małopolskie graniczy ze Słowacją?* | `borders_country == "Słowacja"` $\rightarrow$ **False** | Operator `==` na liście; powinno użyć `contains_exact` i dać **True**. |
| `powiatdle` | *Czy Kraków jest miastem na prawach powiatu?* | `valid=false` (odrzucone za podanie nazwy) | Powinno przetłumaczyć na `is_city_county == 1` $\rightarrow$ **True**. |
| `powiatdle` | *Czy powiat brzeski w Opolskiem należy do woj. opolskiego?* | `name == "Powiat brzeski"` $\rightarrow$ **False** | Baza ma `"Powiat brzeski (opolskie)"`; powinno dać **True**. |
| `us_statedle` | *Does Maine border only one U.S. state, New Hampshire?* | `word_count_equals(borders_state, 1)` $\rightarrow$ **False** | Nieprawidłowy operator tekstu na liście stanów granicznych. |

---

## 4. Wygenerowane Artefakty i Dalsze Kroki

1. **Baza wiedzy o defektach**: Pełny log 165 przypadków w `server/test_reports/qa_playground_findings.jsonl`.
2. **Harness playgroundu**: Gotowe narzędzie wiersza poleceń `server/scripts/qa_playground.py` do testowania dowolnych pytań interaktywnie lub wsadowo.
3. **Kolejny krok**: Przekształcenie wykrytych 31 błędów logicznych w stały zestaw testów regresyjnych w `server/tests/test_qa_playground_regressions.py`.
