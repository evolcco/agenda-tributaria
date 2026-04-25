from __future__ import annotations

import argparse
import http.client
import re
import ssl
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from agenda_parser import parse_xlsx, write_json

PT_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


RETRYABLE_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _base_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Connection": "close",
    }


def _fetch_with_retry(url: str, timeout: int, retries: int, initial_backoff: float) -> bytes:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        req = Request(url, headers=_base_headers())
        try:
            with urlopen(req, timeout=timeout) as resp:
                data: bytes = resp.read()
                return data
        except HTTPError as exc:
            last_error = exc
            if exc.code not in RETRYABLE_HTTP_STATUS or attempt >= retries:
                raise
        except (URLError, ConnectionResetError, TimeoutError, ssl.SSLError, http.client.RemoteDisconnected) as exc:
            last_error = exc
            if attempt >= retries:
                raise

        sleep_seconds = initial_backoff * (2 ** (attempt - 1))
        print(
            f"Tentativa {attempt}/{retries} falhou para {url}. "
            f"Repetindo em {sleep_seconds:.1f}s...",
        )
        time.sleep(sleep_seconds)

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Falha inesperada ao buscar URL: {url}")


def fetch_text(url: str, retries: int = 5, initial_backoff: float = 1.0) -> str:
    data = _fetch_with_retry(url, timeout=30, retries=retries, initial_backoff=initial_backoff)
    return data.decode("utf-8", errors="ignore")


def fetch_bytes(url: str, retries: int = 6, initial_backoff: float = 1.0) -> bytes:
    return _fetch_with_retry(url, timeout=60, retries=retries, initial_backoff=initial_backoff)


def extract_xlsx_link(page_url: str, html: str) -> str:
    hrefs = re.findall(r'href=["\']([^"\']+\.xlsx(?:\?[^"\']*)?)["\']', html, flags=re.IGNORECASE)
    if not hrefs:
        raise ValueError("Nao foi encontrado link .xlsx na pagina informada")

    candidates = [urljoin(page_url, href) for href in hrefs]

    def score(link: str) -> tuple[int, int]:
        low = link.lower()
        s = 0
        if "anexo" in low:
            s += 2
        if "agenda" in low:
            s += 1
        return (s, -len(link))

    best: str = sorted(candidates, key=score, reverse=True)[0]
    return best


def infer_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = Path(path).name
    if name.lower().endswith(".xlsx"):
        return name
    return "agenda-tributaria.xlsx"


def _build_output_name(year: int | None, month: int | None) -> str:
    if year and month:
        return f"agenda-{year:04d}-{month:02d}.json"
    return "agenda-latest.json"


def infer_period_from_page_url(page_url: str) -> tuple[int, int] | None:
    match = re.search(r"/(20\d{2})/([A-Za-zÀ-ÿ-]+)(?:/|$)", page_url)
    if not match:
        return None

    year = int(match.group(1))
    slug = (
        match.group(2)
        .lower()
        .replace("ç", "c")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("-", " ")
    )
    token = slug.split(" ")[0]
    month = PT_MONTHS.get(token)
    if month is None:
        return None
    return (year, month)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atualiza agenda tributaria a partir da pagina mensal da Receita"
    )
    parser.add_argument("--page-url", required=True, help="URL da pagina mensal")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Pasta de saida")
    parser.add_argument("--output-file", type=Path, help="Arquivo .json de saida")
    parser.add_argument("--year", type=int, help="Ano de competencia")
    parser.add_argument("--month", type=int, help="Mes de competencia")
    parser.add_argument("--retries", type=int, default=6, help="Numero de tentativas por download")
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=1.0,
        help="Backoff inicial em segundos (exponencial)",
    )
    args = parser.parse_args()

    html = fetch_text(args.page_url, retries=max(1, args.retries), initial_backoff=args.retry_backoff)
    xlsx_url = extract_xlsx_link(args.page_url, html)
    xlsx_bytes = fetch_bytes(xlsx_url, retries=max(1, args.retries), initial_backoff=args.retry_backoff)

    page_period = infer_period_from_page_url(args.page_url)

    with tempfile.TemporaryDirectory() as tmp:
        xlsx_name = infer_filename_from_url(xlsx_url)
        xlsx_path = Path(tmp) / xlsx_name
        xlsx_path.write_bytes(xlsx_bytes)

        payload = parse_xlsx(
            xlsx_path,
            competence_year=args.year,
            competence_month=args.month,
            agenda_year=page_period[0] if page_period else None,
            agenda_month=page_period[1] if page_period else None,
            monthly_page_url=args.page_url,
            xlsx_url=xlsx_url,
        )

    output_path = args.output_file
    if output_path is None:
        if page_period is not None:
            output_name = _build_output_name(page_period[0], page_period[1])
        else:
            output_name = _build_output_name(
                payload.get("competence", {}).get("year"),
                payload.get("competence", {}).get("month"),
            )
        output_path = args.output_dir / output_name

    write_json(output_path, payload)
    print(output_path)


if __name__ == "__main__":
    main()
