import json, re, sys, unicodedata
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "content/syllabus.json").read_text(encoding="utf-8"))
entries = json.loads((ROOT / ".research/lawphil-index.json").read_text(encoding="utf-8"))

ALIASES = {
    "comelec":"commission elections", "csc":"civil service commission", "ca":"court appeals",
    "iac":"intermediate appellate court", "erb":"energy regulatory board", "coa":"commission audit",
    "cir":"industrial relations internal revenue", "ntc":"national telecommunications commission",
    "pagcor":"philippine amusement gaming corporation", "llda":"laguna lake development authority",
    "bid":"bureau immigration deportation", "pse":"philippine stock exchange",
    "sss":"social security system", "gsis":"government service insurance system",
    "nlrc":"national labor relations commission", "poea":"philippine overseas employment administration",
    "erc":"energy regulatory commission", "hlurb":"housing land use regulatory board",
    "dotc":"transportation communications", "ppa":"philippine ports authority", "npc":"national power corporation",
}
STOP = set("the of and in re inc corporation company philippines philippine heirs office department board secretary general manager commission people republic united states junior jr et al versus vs v".split())

def norm(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = value.replace("&", " and ")
    value = re.sub(r"\bvs?\.?\b", " versus ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    words=[]
    for w in value.split(): words.extend(ALIASES.get(w,w).split())
    return " ".join(words)

def case_tokens(value):
    return {w for w in norm(value).split() if w not in STOP and (len(w)>2 or w.isdigit())}

def year_of(citation):
    ys=re.findall(r"\b(?:19|20)\d{2}\b",citation)
    return ys[-1] if ys else None

def docket_of(citation):
    m=re.search(r"(?:G\.R\.|A\.M\.|A\.C\.) Nos?\.\s*([A-Z]?-?\d+)",citation,re.I)
    return m.group(1).lower().removeprefix("l-") if m else None

def score(case, entry):
    citation=case["syllabusCitations"][0]; title=case["title"]
    nt, ne = norm(title), entry["_norm"]
    ct, et = case_tokens(title), entry["_tokens"]
    overlap=len(ct & et)/max(1,len(ct))
    sequence=SequenceMatcher(None,nt,ne[-max(len(nt)*3,100):]).ratio()
    score=overlap*75+sequence*15
    yr=year_of(citation)
    if yr and f"/juri{yr}/" in entry["url"]: score+=15
    docket=docket_of(citation)
    if docket:
        compact=re.sub(r"\D","",docket)
        urlnums=re.sub(r"\D","",entry["url"].rsplit("/",1)[-1].split("_")[1] if "gr_" in entry["url"] else entry["url"])
        if re.search(r"(?<!\d)"+re.escape(docket)+r"(?!\d)",ne) or compact and compact in urlnums: score+=90
        else: score-=50
    if re.search(r"_(?:so|dissent|concur|res)_",entry["url"]): score-=10
    return round(score,2)

for entry in entries:
    entry["_norm"]=norm(entry["text"])
    entry["_tokens"]=case_tokens(entry["text"])

matches={}
for case in data["cases"]:
    tokens=case_tokens(case["title"])
    docket=docket_of(case["syllabusCitations"][0])
    pool=[]
    for entry in entries:
        ne=entry["_norm"]
        if docket:
            compact=re.sub(r"\D","",docket)
            last=entry["url"].rsplit("/",1)[-1]
            if not (re.search(r"(?<!\d)"+re.escape(docket)+r"(?!\d)",ne) or compact and compact in re.sub(r"\D","",last)):
                continue
        elif not tokens or len(tokens & entry["_tokens"]) < min(2,len(tokens)):
            continue
        pool.append((score(case,entry),entry))
    pool.sort(key=lambda x:x[0],reverse=True)
    matches[case["id"]]=[{"score":s,"url":e["url"],"text":e["text"]} for s,e in pool[:10]]

# U.S. case has an authoritative federal source outside Lawphil.
matches["poindexter-v-greenhow"]=[{"score":200,"url":"https://www.govinfo.gov/content/pkg/USREPORTS-114/pdf/USREPORTS-114-270.pdf","text":"Poindexter v. Greenhow, 114 U.S. 270 (1885) — U.S. Reports"}]
(ROOT/".research"/"matches.json").write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding="utf-8")
for i,c in enumerate(data["cases"]):
    hit=matches[c["id"]][0] if matches[c["id"]] else None
    print(f"{i:03} {hit['score'] if hit else 0:6} {c['title']} :: {hit['text'][:120] if hit else 'NO MATCH'}")
