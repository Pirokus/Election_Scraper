# Elections Scraper – PS 2017 (volby.cz)

Projekt slouží ke stažení výsledků parlamentních voleb 2017 z webu **volby.cz** pro zvolený územní celek a jejich uložení do CSV souboru.

Skript stahuje:
- seznam obcí v daném územním celku,
- souhrnné údaje o hlasování v obci,
- počet hlasů pro jednotlivé kandidující strany.

---

## Instalace

1. Vytvořte a aktivujte virtuální prostředí:

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate       # Windows
```

2. Nainstalujte potřebné knihovny:

```bash
pip install -r requirements.txt
```

---

## Spuštění projektu

Program se spouští pomocí **dvou argumentů z příkazové řádky**:

```bash
python main.py <URL_uzemniho_celku> <vystupni_soubor.csv>
```

### Příklad

```bash
python main.py "https://volby.cz/pls/ps2017nss/ps32?xjazyk=CZ&xkraj=2&xnumnuts=2101" vysledky.csv
```

- **1. argument** – odkaz na územní celek z webu volby.cz  
  (získaný z hlavního rozcestníku:  
  https://volby.cz/pls/ps2017nss/ps3?xjazyk=CZ )
- **2. argument** – název výstupního CSV souboru

Pokud nejsou zadány oba argumenty nebo jsou zadány chybně, program se ukončí s chybovou hláškou.

---

## Výstup

Výstupem je CSV soubor, kde **každý řádek odpovídá jedné obci**.

### Struktura CSV souboru

| Sloupec | Popis |
|------|------|
| code | kód obce |
| location | název obce |
| registered | voliči v seznamu |
| envelopes | vydané obálky |
| valid | platné hlasy |
| <název strany> | počet hlasů pro danou stranu |

Počet sloupců se liší podle počtu kandidujících stran.

---

## Použité knihovny

- requests
- beautifulsoup4

Seznam knihoven je uložen v souboru `requirements.txt`.

---

## Autor

Projekt vytvořen jako součást studia **Python Akademie – Engeto**.
