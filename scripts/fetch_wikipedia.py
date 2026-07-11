"""Fetch substantial Wikipedia articles and render them as real PDFs.

Builds the Phase 5 eval corpus:

  evals/corpus/                 PDFs to bulk-ingest (default 500)
  evals/heldout/                plain-text articles that are NEVER ingested;
                                the golden-set generator builds unanswerable
                                questions from these (same distribution as
                                the corpus, guaranteed absent from it)
  evals/corpus_manifest.json    title/split/size per article — committed so
                                the eval method is reproducible even though
                                the data dirs stay gitignored

Articles are sampled randomly (namespace 0), filtered to >= MIN_WIKITEXT
bytes of wikitext so stubs are skipped, then fetched as plain-text extracts.
Trailing non-content sections (References, External links, ...) are dropped.

Resumable: already-written files are skipped, the manifest is rewritten from
disk state each run.

Usage:
    python scripts/fetch_wikipedia.py --corpus 500 --heldout 50
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from fpdf import FPDF

API = "https://en.wikipedia.org/w/api.php"
# Wikipedia asks for a descriptive User-Agent with contact info.
USER_AGENT = "rag-business-chatbot-evals/1.0 (contact: garghritikgarg@gmail.com)"

MIN_WIKITEXT_BYTES = 12_000   # skip stubs without fetching their text
MIN_EXTRACT_CHARS = 4_000     # after cleaning: enough to yield ~8+ chunks
MAX_EXTRACT_CHARS = 20_000    # truncate monsters at a paragraph boundary
REQUEST_INTERVAL = 0.4        # seconds between API calls (~2.5 req/s)

# Sections after which nothing useful for QA remains.
TRAILING_SECTIONS = re.compile(
    r"\n==\s*(References|External links|See also|Notes|Further reading|"
    r"Bibliography|Sources|Citations|Footnotes)\s*==.*",
    re.DOTALL | re.IGNORECASE,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = REPO_ROOT / "evals" / "corpus"
HELDOUT_DIR = REPO_ROOT / "evals" / "heldout"
MANIFEST_PATH = REPO_ROOT / "evals" / "corpus_manifest.json"

# A Unicode TTF is required: fpdf2's built-in fonts are latin-1 only and
# Wikipedia text is full of non-latin characters.
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]

_last_request = 0.0


def api_get(params: dict) -> dict:
    """Rate-limited GET against the MediaWiki Action API with retries."""
    global _last_request
    wait = REQUEST_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)

    query = urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(
        f"{API}?{query}", headers={"User-Agent": USER_AGENT}
    )
    for attempt in range(5):
        try:
            _last_request = time.monotonic()
            with urllib.request.urlopen(request, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # network blip, 429, 5xx — back off and retry
            if attempt == 4:
                raise
            delay = 2**attempt
            print(f"  API error ({exc}); retrying in {delay}s", flush=True)
            time.sleep(delay)


def sample_candidates() -> list[dict]:
    """One batch of random main-namespace pages with wikitext length."""
    data = api_get(
        {
            "action": "query",
            "generator": "random",
            "grnnamespace": 0,
            "grnlimit": 20,
            "prop": "info|pageprops",
            "ppprop": "disambiguation",
        }
    )
    pages = data.get("query", {}).get("pages", {})
    return [
        p
        for p in pages.values()
        if p.get("length", 0) >= MIN_WIKITEXT_BYTES
        and "disambiguation" not in p.get("pageprops", {})
        and "List of" not in p["title"]
    ]


def fetch_extract(pageid: int) -> str:
    """Full plain-text extract for one page (API limit: 1 full page/request)."""
    data = api_get(
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "redirects": 1,
            "pageids": pageid,
        }
    )
    page = data["query"]["pages"][str(pageid)]
    return page.get("extract", "")


def clean_extract(text: str) -> str:
    text = TRAILING_SECTIONS.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    # Strip control characters PDF/DB layers should never see.
    text = "".join(c for c in text if c == "\n" or unicodedata.category(c)[0] != "C")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_EXTRACT_CHARS:
        cut = text.rfind("\n\n", 0, MAX_EXTRACT_CHARS)
        text = text[: cut if cut > MIN_EXTRACT_CHARS else MAX_EXTRACT_CHARS]
    return text


def slugify(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
    return slug[:60] or "article"


def find_font() -> Path | None:
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def write_pdf(path: Path, title: str, text: str, font_path: Path) -> None:
    pdf = FPDF()
    pdf.add_font("body", fname=str(font_path))
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("body", size=16)
    pdf.multi_cell(0, 8, title)
    pdf.ln(4)
    pdf.set_font("body", size=11)
    # Break unbreakable tokens (long URLs) so line wrapping never fails.
    safe = re.sub(r"(\S{70})(?=\S)", r"\1 ", text)
    for paragraph in safe.split("\n"):
        if paragraph.strip():
            pdf.multi_cell(0, 6, paragraph.strip())
            pdf.ln(2)
    pdf.output(str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=int, default=500)
    parser.add_argument("--heldout", type=int, default=50)
    args = parser.parse_args()

    font_path = find_font()
    if font_path is None:
        print("No Unicode TTF font found — edit FONT_CANDIDATES.", file=sys.stderr)
        return 1

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    HELDOUT_DIR.mkdir(parents=True, exist_ok=True)

    have_corpus = {p.stem for p in CORPUS_DIR.glob("*.pdf")}
    have_heldout = {p.stem for p in HELDOUT_DIR.glob("*.txt")}
    seen_pageids = {
        int(stem.split("_", 1)[0])
        for stem in have_corpus | have_heldout
        if stem.split("_", 1)[0].isdigit()
    }
    manifest: list[dict] = []
    if MANIFEST_PATH.exists():
        manifest = [
            e
            for e in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            if e["file"].split("_", 1)[0].isdigit()
            and int(e["file"].split("_", 1)[0]) in seen_pageids
        ]

    started = time.monotonic()
    rejected = 0
    while len(have_corpus) < args.corpus or len(have_heldout) < args.heldout:
        for page in sample_candidates():
            if len(have_corpus) >= args.corpus and len(have_heldout) >= args.heldout:
                break
            pageid, title = page["pageid"], page["title"]
            if pageid in seen_pageids:
                continue

            text = clean_extract(fetch_extract(pageid))
            if len(text) < MIN_EXTRACT_CHARS:
                rejected += 1
                continue

            seen_pageids.add(pageid)
            stem = f"{pageid}_{slugify(title)}"
            # Fill the corpus first; overflow becomes the held-out split.
            if len(have_corpus) < args.corpus:
                split = "corpus"
                filename = f"{stem}.pdf"
                write_pdf(CORPUS_DIR / filename, title, text, font_path)
                have_corpus.add(stem)
            else:
                split = "heldout"
                filename = f"{stem}.txt"
                (HELDOUT_DIR / filename).write_text(
                    f"{title}\n\n{text}", encoding="utf-8"
                )
                have_heldout.add(stem)

            manifest.append(
                {"title": title, "pageid": pageid, "split": split,
                 "file": filename, "chars": len(text)}
            )
            done = len(have_corpus) + len(have_heldout)
            if done % 25 == 0:
                elapsed = time.monotonic() - started
                print(
                    f"{done}/{args.corpus + args.heldout} articles "
                    f"({len(have_corpus)} corpus, {len(have_heldout)} heldout, "
                    f"{rejected} rejected, {elapsed:.0f}s)",
                    flush=True,
                )
            MANIFEST_PATH.write_text(
                json.dumps(manifest, indent=1, ensure_ascii=False),
                encoding="utf-8",
            )

    print(
        f"Done: {len(have_corpus)} corpus PDFs, {len(have_heldout)} held-out "
        f"texts, manifest at {MANIFEST_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
