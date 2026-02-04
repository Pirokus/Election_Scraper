"""
Elections scraper (PS 2017 NSS, volby.cz)

Usage:
  python main.py <URL_UZEMNIHO_CELKU> <OUTPUT.csv>

Example:
  python main.py "https://www.volby.cz/pls/ps2017nss/ps32?xjazyk=CZ&xkraj=2&xnumnuts=2101" vysledky.csv
"""

from __future__ import annotations

import csv
import sys
from typing import Dict, List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; engeto-elections-scraper/1.0)"}
TIMEOUT = 20


def fetch_soup(url: str) -> BeautifulSoup:
    """Download URL and return parsed HTML."""
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def to_digits(text: str) -> str:
    """Return only digits from text (keeps 0-9)."""
    return "".join(ch for ch in text.replace("\xa0", "").replace(" ", "") if ch.isdigit())


def parse_municipalities(unit_url: str) -> List[Tuple[str, str, str]]:
    """
    Parse municipality list from ps32 page.
    Returns list of (code, name, detail_url).
    """
    soup = fetch_soup(unit_url)
    out: List[Tuple[str, str, str]] = []

    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        a = tds[0].find("a")
        code = (a.get_text(strip=True) if a else tds[0].get_text(strip=True)).strip()
        if not code.isdigit() or not a or not a.get("href"):
            continue

        name = tds[1].get_text(" ", strip=True)
        detail_url = urljoin(unit_url, a["href"])
        out.append((code, name, detail_url))

    if not out:
        raise ValueError("Očekávám odkaz na stránku se seznamem obcí (ps32... v ps2017nss).")
    return out


def parse_summary(soup: BeautifulSoup) -> Dict[str, int]:
    """Parse registered/envelopes/valid from municipality detail page."""
    def get(headers_id: str) -> int:
        td = soup.find("td", attrs={"headers": headers_id})
        return int(to_digits(td.get_text(strip=True))) if td else 0

    return {"registered": get("sa2"), "envelopes": get("sa3"), "valid": get("sa6")}

def parse_parties(soup: BeautifulSoup) -> List[Tuple[int, str, int]]:
    """
    Parse party results from ps311 (ps2017nss) by table structure:
    td[0]=party number, td[1]=party name, td[2]=votes, td[3]=percent
    """
    parties: List[Tuple[int, str, int]] = []

    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        pno_txt = tds[0].get_text(strip=True)
        if not pno_txt.isdigit():
            continue

        pname = tds[1].get_text(" ", strip=True)
        votes_txt = tds[2].get_text(strip=True).replace("\xa0", "").replace(" ", "")

        # votes must be integer; ignore percent like 100,00
        if not pname or not votes_txt.isdigit():
            continue

        parties.append((int(pno_txt), pname, int(votes_txt)))

    # deduplicate (table is split to part 1 and 2)
    uniq: Dict[int, Tuple[str, int]] = {}
    for pno, pname, votes in parties:
        uniq[pno] = (pname, votes)

    return [(pno, uniq[pno][0], uniq[pno][1]) for pno in sorted(uniq)]



def scrape(unit_url: str) -> Tuple[List[str], List[Dict[str, object]]]:
    """Scrape all municipalities for given territorial unit URL."""
    munis = parse_municipalities(unit_url)
    rows: List[Dict[str, object]] = []
    party_cols: List[str] = []

    for i, (code, name, detail_url) in enumerate(munis):
        soup = fetch_soup(detail_url)
        summary = parse_summary(soup)
        parties = parse_parties(soup)

        if i == 0:
            party_cols = [pname for _, pname, _ in parties]

        row: Dict[str, object] = {
            "code": code,
            "location": name,
            "registered": summary["registered"],
            "envelopes": summary["envelopes"],
            "valid": summary["valid"],
        }
        for _, pname, votes in parties:
            row[pname] = votes

        rows.append(row)

    header = ["code", "location", "registered", "envelopes", "valid"] + party_cols
    return header, rows


def write_csv(path: str, header: List[str], rows: List[Dict[str, object]]) -> None:
    """Write CSV output (semicolon delimiter like in Engeto example)."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            for col in header:
                r.setdefault(col, 0)
            w.writerow(r)


def main(argv: List[str]) -> int:
    """CLI entrypoint."""
    if len(argv) != 3:
        print(
            "Chyba: špatné argumenty.\n"
            "Použití: python main.py <URL_UZEMNIHO_CELKU> <VYSTUP.csv>",
            file=sys.stderr,
        )
        return 1

    unit_url, out_csv = argv[1], argv[2]
    if "volby.cz/pls/ps2017nss/ps32" not in unit_url:
        print("Chyba: první argument musí být odkaz na územní celek (ps32... v ps2017nss).", file=sys.stderr)
        return 1

    try:
        header, rows = scrape(unit_url)
        write_csv(out_csv, header, rows)
    except requests.RequestException as e:
        print(f"Chyba při stahování: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 3

    print(f"Hotovo: {len(rows)} obcí -> {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

