"""
Elections scraper (PS 2017 NSS, volby.cz)

Run:
  python main.py <URL_UZEMNIHO_CELKU> <OUTPUT.csv>

Example (tvůj odkaz "sem"):
  python main.py "https://volby.cz/pls/ps2017nss/ps32?xjazyk=CZ&xkraj=2&xnumnuts=2101" vysledky.csv
"""

from __future__ import annotations

import csv
import sys
from typing import Dict, List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; elections-scraper/1.0)"}
TIMEOUT = 20


def fetch_soup(url: str) -> BeautifulSoup:
    """Download URL and return BeautifulSoup."""
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def clean_int(text: str) -> int:
    """Convert numbers like '1 234', '1\xa0234' or '100,00' to int."""
    s = text.replace("\xa0", "").replace(" ", "").strip()
    if not s:
        return 0
    # handle european decimals like 100,00
    if "," in s and s.replace(",", "").isdigit():
        s = s.split(",", 1)[0]
        return int(s) if s else 0
    # handle unexpected non-digits safely
    s = "".join(ch for ch in s if ch.isdigit())
    return int(s) if s else 0



def find_muni_link(tr: BeautifulSoup, base_url: str) -> str:
    """
    Find link to municipality results from row:
    - prefer link in column "Číslo" (usually first TD with digit link)
    - fallback: link in column "Výběr okrsku" (X)
    """
    tds = tr.find_all("td")
    if not tds:
        return ""

    # Prefer: first <a> whose text is municipality code (digits)
    for td in tds[:2]:
        a = td.find("a")
        if a and a.get_text(strip=True).isdigit() and a.get("href"):
            return urljoin(base_url, a["href"])

    # Fallback: any "X" link in the row (Výběr okrsku)
    for a in tr.find_all("a"):
        if a.get_text(strip=True).upper() == "X" and a.get("href"):
            return urljoin(base_url, a["href"])

    # Last fallback: any link that looks like municipality results
    for a in tr.find_all("a"):
        href = a.get("href", "")
        if href and ("ps311" in href or "ps32" in href):
            return urljoin(base_url, href)

    return ""


def parse_municipalities(unit_url: str) -> List[Tuple[str, str, str]]:
    """
    From a selected territorial unit page (typically ps32?...),
    parse municipalities: (code, name, results_url).
    """
    soup = fetch_soup(unit_url)
    out: List[Tuple[str, str, str]] = []

    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        # code + name are typically first two columns
        code_a = tds[0].find("a")
        code = code_a.get_text(strip=True) if code_a else tds[0].get_text(strip=True)
        if not code.isdigit():
            continue

        name = tds[1].get_text(" ", strip=True)
        link = find_muni_link(tr, unit_url)
        if not link:
            continue

        out.append((code, name, link))

    if not out:
        raise ValueError(
            "Nepodařilo se najít obce. Zadej odkaz na územní celek, "
            "který obsahuje tabulku obcí (typicky ps32?... v /ps2017nss/)."
        )
    return out


def parse_summary(soup: BeautifulSoup) -> Dict[str, int]:
    """Parse registered/envelopes/valid from municipality detail page."""
    def get(headers_id: str) -> int:
        td = soup.find("td", attrs={"headers": headers_id})
        return clean_int(td.get_text(strip=True)) if td else 0

    # Volby.cz PS stránky běžně používají tyto identifikátory:
    return {"registered": get("sa2"), "envelopes": get("sa3"), "valid": get("sa6")}


def parse_parties(soup: BeautifulSoup) -> List[Tuple[int, str, int]]:
    """
    Parse party results robustly for ps2017nss pages.
    Uses 'headers' attribute (which is a LIST).
    """
    parties: List[Tuple[int, str, int]] = []
    seen = set()

    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        pno = None
        pname = None
        votes = None

        for td in tds:
            headers = td.get("headers")
            if not headers:
                continue

            # headers is a list, e.g. ['t1sa2']
            for h in headers:
                # číslo strany
                if h.endswith("sa1"):
                    txt = td.get_text(strip=True)
                    if txt.isdigit():
                        pno = int(txt)

                # název strany
                if h.endswith("sb1"):
                    pname = td.get_text(" ", strip=True)

                # hlasy (POZOR: ne procenta!)
                if h.endswith("sa2"):
                    votes = clean_int(td.get_text(strip=True))

        if pno is None or not pname or votes is None:
            continue

        if pno in seen:
            continue
        seen.add(pno)

        parties.append((pno, pname, votes))

    parties.sort(key=lambda x: x[0])
    return parties

def scrape(unit_url: str) -> Tuple[List[str], List[Dict[str, object]]]:
    """Scrape all municipalities for a given territorial unit URL."""
    munis = parse_municipalities(unit_url)

    party_cols: List[str] = []
    party_seen: Dict[str, bool] = {}
    rows: List[Dict[str, object]] = []

    for code, name, detail_url in munis:
        soup = fetch_soup(detail_url)
        summary = parse_summary(soup)
        parties = parse_parties(soup)

        row: Dict[str, object] = {
            "code": code,
            "location": name,
            "registered": summary["registered"],
            "envelopes": summary["envelopes"],
            "valid": summary["valid"],
        }

        for _, pname, votes in parties:
            row[pname] = votes
            if pname not in party_seen:
                party_seen[pname] = True
                party_cols.append(pname)

        rows.append(row)

    header = ["code", "location", "registered", "envelopes", "valid"] + party_cols
    return header, rows


def write_csv(path: str, header: List[str], rows: List[Dict[str, object]]) -> None:
    """Write CSV with missing party values filled with 0."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
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
