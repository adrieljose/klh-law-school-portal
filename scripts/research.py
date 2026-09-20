import json,re,sys,time,hashlib,urllib.request,urllib.parse,concurrent.futures
from pathlib import Path
from lxml import html
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.research';CACHE.mkdir(exist_ok=True)
DATA=json.loads((ROOT/'content/syllabus.json').read_text(encoding='utf-8'))
def get(url):
    p=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
    if p.exists():return p.read_bytes()
    for i in range(3):
        try:
            r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'KLHStudyLibrary/1.0 (educational case indexing)'}),timeout=30)
            b=r.read();p.write_bytes(b);return b
        except Exception:
            if i==2: raise
            time.sleep(1+i)
def index_year(y):
    url=f'https://lawphil.net/judjuris/juri{y}/juri{y}.html'
    try:
        s=html.fromstring(get(url));months=[urllib.parse.urljoin(url,a.get('href')) for a in s.xpath('//a[@href]') if re.search(r'/[a-z]{3}'+str(y)+r'\.html$',a.get('href'))]
        return months
    except Exception as e:return []
def index_month(url):
    try:
        s=html.fromstring(get(url));res=[]
        for tr in s.xpath('//tr'):
            links=tr.xpath('.//a[@href]')
            for a in links:
                href=urllib.parse.urljoin(url,a.get('href'))
                if re.search(r'/(gr_|am_|ac_|bm_|a\.m\.|a\.c\.)',href,re.I) and href.endswith(('.html','.htm')):
                    res.append({'url':href,'text':re.sub(r'\s+',' ',tr.text_content()).strip()})
        return res
    except Exception as e:return []
if __name__=='__main__':
    years=set(int(y) for c in DATA['cases'] for y in re.findall(r'\b(?:19|20)\d{2}\b',c['syllabusCitations'][0]))
    years.update([1903,1922,1929,1965,1967,1974,1979,1986,1987,1990,1992,1993,1994,1995,1996,1997,1999,2000,2002,2004,2005,2006])
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        months=[u for group in ex.map(index_year,sorted(years)) for u in group]
        print('Indexing',len(months),'monthly archives',flush=True)
        entries=[e for group in ex.map(index_month,months) for e in group]
    (CACHE/'lawphil-index.json').write_text(json.dumps(entries,ensure_ascii=False),encoding='utf-8')
    print('Indexed',len(entries),'case documents',flush=True)
    matched={}
    for i,c in enumerate(DATA['cases']):
        citation=c['syllabusCitations'][0]
        docket=re.search(r'(?:G\.R\.|A\.M\.|A\.C\.) Nos?\. ([\w-]+)',citation)
        if docket:
            token=docket[1].lower().removeprefix('l-')
            pattern=r'(?<!\d)'+re.escape(token)+r'(?!\d)'
            hits=[e for e in entries if re.search(pattern,e['text'],re.I) or re.search(pattern,e['url'],re.I)]
        else:
            token=c['title'].split(' v. ')[0].replace('US','United States').split(',')[0].split()[0]
            hits=[e for e in entries if re.search(r'\b'+re.escape(token)+r'\b',e['text'],re.I)]
        year=re.findall(r'\b(?:19|20)\d{2}\b',citation)
        hits=sorted(hits,key=lambda e:(0 if year and '/juri'+year[-1]+'/' in e['url'] else 1,len(e['text'])))
        matched[c['id']]=hits[:30]
        print(i,c['title'],len(hits),json.dumps(hits[:3],ensure_ascii=False))
    (CACHE/'candidates.json').write_text(json.dumps(matched,ensure_ascii=False,indent=2),encoding='utf-8')
