import json, re, unicodedata
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r'C:\Users\Asus\Downloads\UPDATED - Administrative Law and Law on Public Officers - Syllabus.docx')
def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()).strip('-')
with ZipFile(SOURCE) as z:
    doc = etree.fromstring(z.read('word/document.xml'))
ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
rows = [''.join(p.xpath('.//w:t/text()', namespaces=ns)).strip() for p in doc.xpath('//w:body//w:p', namespaces=ns)]
parts, topics, cases, references = [], [], {}, []
part = topic = subsection = None
for i,t in enumerate(rows):
    if t.startswith('PART '):
        part = {'id': f'part-{len(parts)+1}', 'title': t.split(' — ')[-1].title(), 'topics': []}
        parts.append(part)
    elif part and re.match(r'^[IVX]+\.\s',t):
        title=re.sub(r'^[IVX]+\.\s*','',t).capitalize()
        topic={'id':f'topic-{len(topics)+1}', 'title':title, 'partId':part['id'], 'description':[], 'sections':[], 'caseIds':[]}
        topics.append(topic); part['topics'].append(topic['id']); subsection=None
    elif part and re.search(r'\bv\. |^In Re:',t):
        title=re.split(r',\s*(?:G\.R\.|A\.M\.|A\.C\.|\d|supra|January|February|March|April|May|June|July|August|September|October|November|December)',t)[0]
        title=title.replace('sCivil Service Commission','Civil Service Commission')
        cid=slug(title)
        if cid not in cases:
            cases[cid]={'id':cid,'title':title,'syllabusCitations':[], 'topicIds':[], 'status':'pending', 'sourceUrl':None}
        c=cases[cid]
        if t not in c['syllabusCitations']: c['syllabusCitations'].append(t)
        if topic['id'] not in c['topicIds']: c['topicIds'].append(topic['id'])
        topic['caseIds'].append(cid)
        references.append({'number':len(references)+1,'paragraph':i,'citation':t,'caseId':cid,'topicId':topic['id'],'section':subsection})
    elif topic and t and not t.startswith('x '):
        if re.match(r'^(?:[A-E]|[1-3])\.\s',t):
            subsection=t; topic['sections'].append({'title':t,'description':[]})
        elif subsection: topic['sections'][-1]['description'].append(t)
        else: topic['description'].append(t)
tables=[]
for table in doc.xpath('//w:body/w:tbl',namespaces=ns):
    tables.append([[' '.join(cell.xpath('.//w:t/text()',namespaces=ns)) for cell in tr.xpath('./w:tc',namespaces=ns)] for tr in table.xpath('./w:tr',namespaces=ns)])
data={'title':'KLH Law School Portal','course':rows[3],'professor':rows[4],'school':rows[0].title(),'academicYear':rows[2], 'policies':rows[7:12], 'gradingTables':tables, 'recitationNote':rows[30], 'consultation':rows[32], 'parts':parts,'topics':topics,'cases':list(cases.values()),'references':references}
(ROOT/'content').mkdir(exist_ok=True)
(ROOT/'content'/'syllabus.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(references)} references, {len(cases)} unique cases, {len(topics)} topics; {len(tables)} grading tables')
