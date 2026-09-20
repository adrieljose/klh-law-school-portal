"""Build the static KLH portal from the parsed syllabus and verified sources.

The downloaded source cache is intentionally excluded from git. Generated case
pages keep the source URL and retrieval date beside the reproduced decision.
"""
from __future__ import annotations

import copy
import hashlib
import html as html_lib
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CACHE = ROOT / ".research" / "source-cache"
RETRIEVED = "2026-09-20"
SSL_CONTEXT = ssl._create_unverified_context()

OVERRIDES = {
    "eugenio-v-csc": ("https://lawphil.net/judjuris/juri1995/mar1995/gr_115863_1995.html", "G.R. No. 115863, March 31, 1995"),
    "miaa-v-ca": ("https://lawphil.net/judjuris/juri2006/jul2006/gr_155650_2006.html", "G.R. No. 155650, July 20, 2006"),
    "cir-v-ca": ("https://lawphil.net/judjuris/juri1996/aug1996/gr_119761_1996.html", "G.R. No. 119761, August 29, 1996"),
    "chung-fu-industries-v-ca": ("https://lawphil.net/judjuris/juri1992/feb1992/gr_96283_1992.html", "G.R. No. 96283, February 25, 1992"),
    "land-bank-of-the-philippines-v-ca": ("https://lawphil.net/judjuris/juri1999/nov1999/gr_126332_1999.html", "G.R. No. 126332, November 16, 1999"),
    "gsis-v-csc": ("https://lawphil.net/judjuris/juri1995/jun1995/gr_98395_1995.html", "G.R. No. 98395, June 8, 1995"),
    "republic-v-sereno": ("https://lawphil.net/judjuris/juri2018/may2018/gr_237428_2018.html", "G.R. No. 237428, May 11, 2018"),
    "shopping-center-management-corp-v-galutera": ("https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/70529", "G.R. No. E-02121, February 10, 2026"),
    "torrosa-v-singson": ("https://lawphil.net/judjuris/juri1994/may1994/gr_111243_1994.html", "G.R. No. 111243, May 25, 1994"),
    "de-rama-v-coa": ("https://lawphil.net/judjuris/juri2001/feb2001/gr_131136_2001.html", "G.R. No. 131136, February 28, 2001"),
    "tsunami-management-corp-v-ombudsman": ("https://legaldex.com/jurisprudence/tsunami-management-corp-v-ombudsman", "G.R. No. 232712, September 29, 2021"),
    "secretary-of-justice-v-lantion": ("https://lawphil.net/judjuris/juri2000/jan2000/gr_139465_2000.html", "G.R. No. 139465, January 18, 2000"),
    "central-bank-employees-association-v-bsp": ("https://lawphil.net/judjuris/juri2004/dec2004/gr_148208_2004.html", "G.R. No. 148208, December 15, 2004; 446 SCRA 299"),
    "cir-v-central-luzon-drug-corp": ("https://lawphil.net/judjuris/juri2005/apr2005/gr_159647_2005.html", "G.R. No. 159647, April 15, 2005; 456 SCRA 414"),
    "tayko-v-capistrano": ("https://elibrary.judiciary.gov.ph/assets/pdf/philrep_ebooks/Volume_53.pdf", "G.R. No. L-30188, October 2, 1928; 53 Phil. 866"),
    "poindexter-v-greenhow": ("https://www.govinfo.gov/content/pkg/USREPORTS-114/pdf/USREPORTS-114-270.pdf", "114 U.S. 270 (1885)"),
}

TEXT_URLS = {
    # Volume 53 is an image-only official scan. This transcription is used for
    # reading while the prominent original-source link remains the official PDF.
    "tayko-v-capistrano": "https://chanrobles.com/scdecisions/jurisprudence1928/oct1928/gr_l-30188_1928.php",
}

ALIASES = {
    "torrosa-v-singson": ["Tarrosa v. Singson"],
    "de-rama-v-coa": ["De Rama v. Court of Appeals", "De Rama v. CA"],
    "miaa-v-ca": ["Manila International Airport Authority v. Court of Appeals"],
    "cir-v-ca": ["Commissioner of Internal Revenue v. Court of Appeals"],
    "gsis-v-csc": ["Government Service Insurance System v. Civil Service Commission"],
}

CITATION_NOTES = {
    "central-bank-employees-association-v-bsp": "The syllabus citation 307 SCRA 443 identifies a different case. The named case is reported at 446 SCRA 299.",
    "torrosa-v-singson": "The official decision spells the petitioner’s surname “Tarrosa.”",
    "de-rama-v-coa": "The official decision is De Rama v. Court of Appeals, G.R. No. 131136. The syllabus lists COA and G.R. No. 131135.",
    "executive-secretary-v-southwing-heavy-industries": "The official decision date is February 20, 2006.",
}

PDF_CASES = {"tayko-v-capistrano", "poindexter-v-greenhow"}
ALLOWED = {"a", "abbr", "b", "blockquote", "br", "center", "cite", "div", "em", "h2", "h3", "h4", "h5", "hr", "i", "li", "ol", "p", "pre", "small", "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul"}


def fetch(url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    suffix = Path(urllib.parse.urlsplit(url).path).suffix or ".html"
    target = CACHE / (hashlib.sha256(url.encode()).hexdigest() + suffix)
    if target.exists() and target.stat().st_size > 300:
        return target.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 KLH-Law-School-Portal/1.0"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=50, context=SSL_CONTEXT) as response:
                content = response.read()
            target.write_bytes(content)
            return content
        except Exception as exc:
            last = exc
            time.sleep(1 + attempt)
    raise last  # type: ignore[misc]


def sanitize(node, base_url: str, prefix: str = "") -> str:
    node = copy.deepcopy(node)
    for bad in node.xpath(".//script|.//style|.//noscript|.//iframe|.//object|.//embed|.//form|.//input|.//button|.//select|.//textarea|.//svg|.//canvas|.//img"):
        bad.drop_tree()
    for element in list(node.iter()):
        if not isinstance(element.tag, str):
            continue
        tag = element.tag.lower().split("}")[-1]
        element.tag = tag
        if tag not in ALLOWED and element is not node:
            try:
                element.drop_tag()
            except Exception:
                pass
            continue
        attrs = dict(element.attrib)
        element.attrib.clear()
        for key in ("colspan", "rowspan"):
            if key in attrs and attrs[key].isdigit():
                element.set(key, attrs[key])
        for key in ("id", "name"):
            if key in attrs and re.match(r"^[\w:.-]+$", attrs[key]):
                element.set(key, prefix + attrs[key])
        if tag == "a" and "href" in attrs:
            href = attrs["href"].strip()
            if href.startswith("#"):
                element.set("href", "#" + prefix + href[1:])
            elif not re.match(r"(?i)^(?:javascript|data):", href):
                element.set("href", urllib.parse.urljoin(base_url, href))
                if element.get("href", "").startswith("http"):
                    element.set("rel", "noopener")
                    element.set("target", "_blank")
    return html.tostring(node, encoding="unicode", method="html")


def lawphil_content(raw: bytes, url: str, prefix: str = "") -> str:
    doc = html.fromstring(raw)
    if "chanrobles.com" in url:
        nodes = doc.xpath("//*[contains(concat(' ',normalize-space(@class),' '),' content ')]")
        if nodes:
            return sanitize(max(nodes, key=lambda n: len(n.text_content())), url, prefix)
    candidates = doc.xpath("//td|//blockquote|//article|//main")
    candidates = [n for n in candidates if len(" ".join(n.text_content().split())) > 1200]
    if not candidates:
        raise ValueError("No substantial decision body found")
    node = max(candidates, key=lambda n: len(n.text_content()))
    return sanitize(node, url, prefix)


def elibrary_content(raw: bytes, url: str) -> str:
    doc = html.fromstring(raw)
    nodes = doc.xpath("//*[contains(concat(' ',normalize-space(@class),' '),' single_content ') or contains(@class,'case-content')]")
    if not nodes:
        raise ValueError("No E-Library decision body found")
    return sanitize(max(nodes, key=lambda n: len(n.text_content())), url)


def legaldex_content(raw: bytes, url: str) -> str:
    doc = html.fromstring(raw)
    nodes = doc.xpath("//article|//main|//*[contains(@class,'jurisprudence') or contains(@class,'content')]")
    nodes = [n for n in nodes if len(" ".join(n.text_content().split())) > 2000]
    if not nodes:
        raise ValueError("No Legaldex decision body found")
    return sanitize(max(nodes, key=lambda n: len(n.text_content())), url)


def text_to_html(text: str) -> str:
    text = text.replace("\x00", "").replace("\r", "")
    blocks = re.split(r"\n\s*\n", text)
    out = []
    for block in blocks:
        block = "\n".join(line.rstrip() for line in block.splitlines()).strip()
        if not block:
            continue
        compact = " ".join(block.split())
        if len(compact) < 120 and (compact.isupper() or re.match(r"^(?:MR\.|MRS\.|THE |No\.|\d+\.)", compact)):
            out.append(f"<h3>{html_lib.escape(compact)}</h3>")
        else:
            out.append(f"<p>{html_lib.escape(compact)}</p>")
    return "".join(out)


def pdf_content(slug: str, raw: bytes) -> str:
    from pypdf import PdfReader
    pdf_path = CACHE / (slug + ".pdf")
    pdf_path.write_bytes(raw)
    reader = PdfReader(str(pdf_path))
    if slug == "tayko-v-capistrano":
        needles, ranges = ("TAYKO", "CAPISTRANO"), range(max(0, len(reader.pages) - 140), len(reader.pages))
    else:
        needles, ranges = ("POINDEXTER", "GREENHOW"), range(0, len(reader.pages))
    start = None
    for i in ranges:
        text = reader.pages[i].extract_text() or ""
        upper = text.upper()
        if all(n in upper for n in needles):
            start = i
            break
    if start is None:
        raise ValueError(f"Could not locate {slug} in official PDF")
    pages = []
    max_pages = 18 if slug == "tayko-v-capistrano" else len(reader.pages)
    for i in range(start, min(len(reader.pages), start + max_pages)):
        txt = reader.pages[i].extract_text() or ""
        if i > start + 1:
            upper = txt.upper()
            if slug == "tayko-v-capistrano" and re.search(r"\n\s*G\.R\. No\. [^\n]+\n", txt) and not all(n in upper for n in needles):
                break
            if slug == "poindexter-v-greenhow" and re.search(r"\n\s*\d+ U\.S\. \d+", txt) and not all(n in upper for n in needles):
                break
        pages.append(txt)
    body = "\n\n".join(pages)
    if len(body) < 3000:
        raise ValueError(f"Official PDF extraction for {slug} was unexpectedly short")
    return text_to_html(body)


def citation_from_index(value: str) -> str:
    value = re.sub(r"(?<=\d)(?=[A-Z])", " ", " ".join(value.split()))
    months = r"January|February|March|April|May|June|July|August|September|October|November|December"
    m = re.match(rf"^(.*?\b(?:{months})\s+\d{{1,2}},?\s+(?:19|20)\d{{2}})", value, re.I)
    if m:
        return m.group(1).strip()
    # Some indexes omit the date. Keep only the docket portion rather than
    # allowing a four-digit sequence inside a six-digit docket to look like a year.
    m = re.match(r"^((?:G\.?\s*R\.?|A\.?\s*M\.?|A\.?\s*C\.?)\s*Nos?\.?\s*[A-Z0-9&., /-]+)", value, re.I)
    return m.group(1).strip() if m else value[:180]


def source_name(url: str) -> str:
    if "elibrary.judiciary.gov.ph" in url:
        return "Supreme Court E-Library"
    if "lawphil.net" in url:
        return "The Lawphil Project"
    if "govinfo.gov" in url:
        return "U.S. Government Publishing Office"
    if "legaldex.com" in url:
        return "LegalDex"
    return urllib.parse.urlsplit(url).netloc


def page_shell(title: str, body: str, description: str = "KLH Law School Portal") -> str:
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"description\" content=\"{html_lib.escape(description, quote=True)}\"><title>{html_lib.escape(title)} · KLH Law School Portal</title><link rel=\"icon\" href=\"/favicon.ico?v=2\" sizes=\"any\"><link rel=\"icon\" type=\"image/png\" href=\"/assets/klh-favicon.png?v=2\"><link rel=\"apple-touch-icon\" href=\"/assets/apple-touch-icon.png?v=2\"><script src=\"/theme.js\"></script><link rel=\"stylesheet\" href=\"/styles.css\"></head><body><a class=\"skip\" href=\"#main\">Skip to content</a>{body}<script src=\"/case.js\"></script></body></html>"""


def case_page(case: dict, decision_html: str) -> str:
    syllabus = " · ".join(case["syllabusCitations"])
    status = case["status"]
    label = "Official or court-published source" if status == "verified" else "Secondary full-text source; official page was not located"
    note = f'<aside class="citation-alert"><strong>Citation check</strong><p>{html_lib.escape(case["citationNote"])}</p></aside>' if case.get("citationNote") else ""
    transcription = f'<span>Reading text: <a href="{html_lib.escape(case["textSourceUrl"], quote=True)}" target="_blank" rel="noopener">{html_lib.escape(case["textSourceName"])}</a></span>' if case.get("textSourceUrl") else ""
    topics = " · ".join(case.get("topicTitles", []))
    body = f"""<header class=\"reader-topbar\"><a class=\"brand\" href=\"/\"><img src=\"/assets/klh-logo.png\" alt=\"KLH Law Firm\" width=\"48\" height=\"48\"><span>KLH <b>Law School Portal</b></span></a><nav><a href=\"/\">Case library</a><a href=\"/syllabus/\">Syllabus</a><button class=\"theme-button\" type=\"button\" data-theme-toggle aria-pressed=\"false\"><span class=\"theme-symbol\" aria-hidden=\"true\"></span><span class=\"theme-label\">Dark</span></button></nav></header>
<main id=\"main\" class=\"reader-shell\"><article class=\"decision-card\"><a class=\"back-link\" href=\"/\">← Back to case library</a><div class=\"case-kicker\">{html_lib.escape(topics)}</div><h1>{html_lib.escape(case['title'])}</h1><p class=\"verified-citation\">{html_lib.escape(case['citation'])}</p><p class=\"syllabus-citation\"><strong>Syllabus citation:</strong> {html_lib.escape(syllabus)}</p>{note}<div class=\"reader-actions\"><button class=\"study-button\" data-action=\"bookmarks\" data-id=\"{case['id']}\">Bookmark</button><button class=\"study-button\" data-action=\"read\" data-id=\"{case['id']}\">Mark as read</button><a class=\"source-button\" href=\"{html_lib.escape(case['sourceUrl'], quote=True)}\" target=\"_blank\" rel=\"noopener\">View original source ↗</a></div><div class=\"source-meta\"><span>{html_lib.escape(case['sourceName'])}</span><span>{label}</span>{transcription}<span>Retrieved {RETRIEVED}</span></div><section class=\"decision-text\" aria-label=\"Full decision\">{decision_html}</section></article><aside class=\"reader-note\"><strong>Study progress</strong><p>Bookmarks and reading status are saved in this browser. Reading remains available if storage is unavailable.</p><a href=\"/?view=bookmarks\">View bookmarked cases</a></aside></main>
<footer class=\"reader-footer\">KLH LAW SCHOOL PORTAL <span>For academic use · Source linked above</span></footer>"""
    return page_shell(case["title"], body, f"Full text and source for {case['title']}")


def syllabus_page(data: dict) -> str:
    esc = html_lib.escape
    policies = "".join(f"<li>{esc(x)}</li>" for x in data["policies"])
    grades = []
    for i, rows in enumerate(data["gradingTables"], 1):
        tr = "".join(f"<tr><th>{esc(a.strip())}</th><td>{esc(b.replace(' ', ''))}</td></tr>" for a, b in rows if a.strip() or b.strip())
        grades.append(f"<table><caption>Grading table {i}</caption><tbody>{tr}</tbody></table>")
    parts = []
    case_map = {c["id"]: c for c in data["cases"]}
    topic_map = {t["id"]: t for t in data["topics"]}
    for part in data["parts"]:
        topics = []
        for tid in part["topics"]:
            t = topic_map[tid]
            descriptions = "".join(f"<li>{esc(x)}</li>" for x in t["description"])
            refs = [r for r in data["references"] if r["topicId"] == tid]
            current = None
            cases = []
            for r in refs:
                if r.get("section") and r["section"] != current:
                    current = r["section"]
                    cases.append(f"<h4>{esc(current)}</h4>")
                c = case_map[r["caseId"]]
                cases.append(f'<li><a href="/cases/{c["id"]}/">{esc(r["citation"])}</a></li>')
            topics.append(f'<section id="{tid}"><h3>{esc(t["title"])}</h3><ul>{descriptions}</ul><ol class="syllabus-cases">{"".join(cases)}</ol></section>')
        parts.append(f'<div class="syllabus-part"><h2>{esc(part["title"])}</h2>{"".join(topics)}</div>')
    body = f"""<header class=\"reader-topbar\"><a class=\"brand\" href=\"/\"><img src=\"/assets/klh-logo.png\" alt=\"KLH Law Firm\" width=\"48\" height=\"48\"><span>KLH <b>Law School Portal</b></span></a><nav><a href=\"/\">Case library</a><a aria-current=\"page\" href=\"/syllabus/\">Syllabus</a><button class=\"theme-button\" type=\"button\" data-theme-toggle aria-pressed=\"false\"><span class=\"theme-symbol\" aria-hidden=\"true\"></span><span class=\"theme-label\">Dark</span></button></nav></header><main id=\"main\" class=\"syllabus-page\"><p class=\"eyebrow\">COMPLETE COURSE SYLLABUS</p><h1>{esc(data['course'])}</h1><p class=\"syllabus-lead\">{esc(data['school'])}<br>{esc(data['professor'])} · {esc(data['academicYear'])}</p><section><h2>Class policies</h2><ol>{policies}</ol></section><section><h2>Grading system</h2><div class=\"grading-grid\">{"".join(grades)}</div><p>{esc(data['recitationNote'])}</p></section><section><h2>Consultation</h2><p>{esc(data['consultation'])}</p></section>{"".join(parts)}</main><footer class=\"reader-footer\">KLH LAW SCHOOL PORTAL <span>Administrative Law and Law on Public Officers</span></footer>"""
    return page_shell("Syllabus", body, data["course"])


def build() -> None:
    data = json.loads((ROOT / "content" / "syllabus.json").read_text(encoding="utf-8"))
    matches = json.loads((ROOT / ".research" / "matches.json").read_text(encoding="utf-8"))
    topic_map = {t["id"]: t for t in data["topics"]}
    unresolved = []
    status_counts = {"verified": 0, "secondary": 0, "unresolved": 0}
    for number, case in enumerate(data["cases"], 1):
        slug = case["id"]
        candidates = matches.get(slug, [])
        if slug in OVERRIDES:
            url, citation = OVERRIDES[slug]
        elif candidates:
            url, citation = candidates[0]["url"], citation_from_index(candidates[0]["text"])
        else:
            url, citation = "", case["syllabusCitations"][0]
        case.update({"sourceUrl": url or None, "sourceName": source_name(url) if url else None, "retrievedAt": RETRIEVED, "citation": citation, "topicTitles": [topic_map[x]["title"] for x in case["topicIds"]]})
        case["alternateNames"] = ALIASES.get(slug, [])
        if slug in CITATION_NOTES:
            case["citationNote"] = CITATION_NOTES[slug]
        try:
            text_url = TEXT_URLS.get(slug, url)
            raw = fetch(text_url)
            if slug in PDF_CASES and slug not in TEXT_URLS:
                decision = pdf_content(slug, raw)
            elif slug in TEXT_URLS:
                decision = lawphil_content(raw, text_url)
                case["textSourceUrl"] = text_url
                case["textSourceName"] = "ChanRobles Virtual Law Library transcription"
            elif "elibrary.judiciary.gov.ph" in url:
                decision = elibrary_content(raw, url)
            elif "legaldex.com" in url:
                decision = legaldex_content(raw, url)
            else:
                decision = lawphil_content(raw, url)
                if candidates and url == candidates[0]["url"]:
                    related = [x for x in candidates[1:] if x["score"] == candidates[0]["score"] and x["url"] != url and x["url"].rsplit("/", 1)[0] == url.rsplit("/", 1)[0]]
                    for i, opinion in enumerate(related[:8], 1):
                        try:
                            opinion_body = lawphil_content(fetch(opinion["url"]), opinion["url"], f"op{i}-")
                            decision += f'<hr><section class="separate-opinion"><h2>Separate opinion</h2>{opinion_body}</section>'
                        except Exception:
                            pass
            plain = " ".join(html.fromstring(decision).text_content().split())
            if len(plain) < 1800:
                raise ValueError(f"decision text only {len(plain)} characters")
            case["status"] = "secondary" if "legaldex.com" in url else "verified"
            case["textCharacters"] = len(plain)
        except Exception as exc:
            case["status"] = "unresolved"
            case["verificationIssue"] = str(exc)
            decision = f'<div class="unavailable"><h2>Full text unavailable</h2><p>This entry could not be reproduced from the linked source during the latest verification. Use the original source link above.</p><p><strong>Verification note:</strong> {html_lib.escape(str(exc))}</p></div>'
            unresolved.append({"id": slug, "title": case["title"], "sourceUrl": url, "issue": str(exc)})
        status_counts[case["status"]] += 1
        folder = DIST / "cases" / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(case_page(case, decision), encoding="utf-8")
        print(f"[{number:03}/{len(data['cases'])}] {case['status']:10} {case['title']}")

    DIST.joinpath("data").mkdir(parents=True, exist_ok=True)
    (DIST / "data" / "index.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DIST / "syllabus").mkdir(parents=True, exist_ok=True)
    (DIST / "syllabus" / "index.html").write_text(syllabus_page(data), encoding="utf-8")
    report = {"generatedAt": RETRIEVED, "referenceCount": len(data["references"]), "uniqueCaseCount": len(data["cases"]), "statusCounts": status_counts, "unresolved": unresolved}
    (ROOT / "content" / "verification-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
