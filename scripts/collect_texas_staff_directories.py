"""Resumable public Texas staff-directory discovery; hits are review leads only.

The frozen campus_targets.json supplies the 1,610-campus research scope.
Use --cache to preserve acquisition receipts and bodies outside the repository.
No network stage assigns a delivery model or changes canonical data.
--legacy-discovery-cache optionally reads previously saved district navigation.
"""
import argparse,collections,csv,gzip,hashlib,html,json,re,subprocess,threading,time,unicodedata
import urllib.request,urllib.parse,urllib.error
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CACHE=Path('/tmp/tx_staff_directory_research_2026_11_07')
TARGETS=None
LEGACY=None
LOCK=threading.Lock();HOSTS={};PAUSES={};NEXT_REQUEST=0;RATE_PAUSE_UNTIL=0
MONO=re.compile(r'monolinguals?|monoling[uü]es?|\bmono\b|non[ _-]?bilingual|English[ _-]?only|all[ _-]?English|non[ _-]?(?:DLI\b|DL\b|dual[ _-]?language)',re.I)
BILINGUAL=re.compile(r'bilinguals?|biling[uü]es?|dual[ _-]?language|\bBIL\b|\bDLI\b',re.I)
REGULAR=re.compile(r'general[ _-]education|regular[ _-](?:ed\.?\b|education|program)|\bGen[ .]*Ed\b',re.I)
STOP=set('the of and school schools elementary el es middle ms high hs h s intermediate int academy campus primary magnet dual language junior jr center centre early childhood kindergarten isd'.split())

def clean(s):return ' '.join(html.unescape(s or '').split())
def tokens(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    for short,full in [('wm','william'),('thos','thomas'),('chas','charles'),('robt','robert'),('jno','john')]:s=re.sub(r'\b'+short+r'\b',full,s)
    return {w for w in re.findall('[a-z0-9]+',s) if len(w)>1 and w not in STOP}
def urlkey(url):return hashlib.sha256(url.encode()).hexdigest()[:22]
def normalize_url(url,base=''):
    url=(url or '').strip()
    if not url:return ''
    if not urllib.parse.urlsplit(url).scheme and not base:url='https://'+url
    url=urllib.parse.urljoin(base,url);p=urllib.parse.urlsplit(url)
    if p.scheme not in {'https','http'} or not p.hostname or p.username or p.password:return ''
    return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path or '/',p.query,''))

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.skip=0;self.parts=[];self.links=[];self.anchor=None;self.anchor_text=[];self.in_title=False;self.title=[];self.h=False;self.headings=[];self.ht=[];self.scripts=[];self.script=None;self.json_parts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in {'script','style','noscript','svg'}:self.skip+=1
        if tag=='script':self.script=[]
        if tag=='title':self.in_title=True
        if tag in {'h1','h2','h3','h4'}:self.h=True;self.ht=[]
        if tag=='a' and a.get('href'):self.anchor=a['href'];self.anchor_text=[]
        if tag=='a' and self.anchor:self.anchor_text.extend([a.get('aria-label',''),a.get('title','')])
        if tag=='img' and self.anchor and a.get('alt'):self.anchor_text.append(a['alt'])
        if tag=='option' and a.get('value','').startswith(('http://','https://','/')):self.anchor=a['value'];self.anchor_text=[]
        if tag=='meta' and a.get('property') in {'og:title','og:site_name'}:self.headings.append(a.get('content',''))
        if tag in {'div','p','li','tr','br','article','section','h1','h2','h3','h4'}:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag=='script' and self.script is not None:self.scripts.append(''.join(self.script));self.script=None
        if tag in {'script','style','noscript','svg'}:self.skip=max(0,self.skip-1)
        if tag=='title':self.in_title=False
        if tag in {'h1','h2','h3','h4'} and self.h:self.headings.append(clean(' '.join(self.ht)));self.h=False
        if tag in {'a','option'} and self.anchor:self.links.append(dict(url=self.anchor,text=clean(' '.join(self.anchor_text))));self.anchor=None
        if tag in {'div','p','li','tr','br','article','section'}:self.parts.append('\n')
    def handle_data(self,s):
        if not self.skip:self.parts.append(s)
        if self.script is not None:self.script.append(s)
        if self.in_title:self.title.append(s)
        if self.anchor:self.anchor_text.append(s)
        if self.h:self.ht.append(s)

def json_strings(value):
    if isinstance(value,dict):
        for v in value.values():yield from json_strings(v)
    elif isinstance(value,list):
        for v in value:yield from json_strings(v)
    elif isinstance(value,str):
        if value[:1] in {'[','{'}:
            try:
                x=json.loads(value)
                if isinstance(x,(dict,list)):yield from json_strings(x);return
            except ValueError:pass
        yield value

def json_objects(value,depth=0):
    if depth>60:return
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from json_objects(v,depth+1)
    elif isinstance(value,list):
        for v in value:yield from json_objects(v,depth+1)
    elif isinstance(value,str) and value[:1] in {'[','{'}:
        try:yield from json_objects(json.loads(value),depth+1)
        except (ValueError,RecursionError):pass

def application_links(raw,url):
    links=[];organizations=[];staff_api=[]
    text=raw.decode('utf-8','replace')
    for m in re.finditer(r'<script[^>]*>(.*?)</script>',text,re.S):
        payloads=[]
        if m[1].lstrip().startswith(('[','{')):
            try:payloads.append(json.loads(m[1]))
            except ValueError:pass
        if 'org_url' in m[1]:
            for literal in re.finditer(r'"(?:\\.|[^"\\])*"',m[1],re.S):
                if 'org_url' not in literal[0]:continue
                try:payloads.append(json.loads(literal[0]))
                except ValueError:pass
        for obj in (o for payload in payloads for o in json_objects(payload)):
            if isinstance(obj.get('org_url'),str) and isinstance(obj.get('name'),str):
                u=normalize_url(obj['org_url']);name=obj['name']
                if u:
                    links.append(dict(url=u,text=name));organizations.append(dict(name=name,url=u,org_id=obj.get('id'),path_prefix=obj.get('path_prefix','')))
            dest=next((obj[k] for k in ['url','href','link'] if isinstance(obj.get(k),str) and obj[k].startswith(('http://','https://','/'))),None)
            label=next((obj[k] for k in ['text','title','name','label'] if isinstance(obj.get(k),str)),None)
            if dest and label:
                u=normalize_url(dest,url)
                if u:links.append(dict(url=u,text=clean(label)))
    for m in re.finditer(r'.{0,50}(?:/api/[^"\\<> ]{0,180}staff[^"\\<> ]{0,180}).{0,50}',text,re.I):staff_api.append(m[0][:300])
    return links,organizations,staff_api[:20]

def extract(raw,content_type,url):
    if raw.startswith(b'%PDF'):
        result=subprocess.run(['pdftotext','-layout','-','-'],input=raw,capture_output=True,timeout=20)
        return dict(title='',headings=[],text=result.stdout.decode('utf-8','replace'),links=[])
    text=raw.decode('utf-8','replace')
    if 'json' in content_type or text.lstrip().startswith(('{','[')):
        try:parts=list(json_strings(json.loads(text)));return dict(title='',headings=[],text='\n'.join(parts),links=[])
        except ValueError:pass
    p=Parser();p.feed(text);visible='\n'.join(clean(x) for x in ''.join(p.parts).splitlines() if clean(x))
    embedded=[]
    for script in p.scripts:
        if script.lstrip().startswith(('[','{')):
            try:
                for s in json_strings(json.loads(script)):
                    if MONO.search(s) or BILINGUAL.search(s) or re.search(r'staff|faculty|directory',s,re.I):
                        if len(s)<150000:embedded.append(html.unescape(re.sub('<[^>]*>',' ',s)))
            except (ValueError,RecursionError):pass
    links=[];seen=set()
    for link in p.links:
        dest=normalize_url(link['url'],url)
        if dest and (dest,link['text']) not in seen:links.append(dict(url=dest,text=link['text']));seen.add((dest,link['text']))
    app_links,organizations,staff_api=application_links(raw,url)
    links=list({(x['url'],x['text']):x for x in links+app_links}.values())
    return dict(title=clean(' '.join(p.title)),headings=p.headings,text=visible,embedded_text='\n'.join(embedded),links=links,organizations=organizations,staff_api_leads=staff_api)

def capture(url,retry_errors=False):
    global NEXT_REQUEST,RATE_PAUSE_UNTIL
    key=urlkey(url);mp=CACHE/(key+'.json')
    old=json.loads(mp.read_text()) if mp.exists() else None
    if old and not (retry_errors and old.get('http_status') in {429,421,503} and old.get('retry_count',0)<1):return old
    host=urllib.parse.urlsplit(url).netloc
    with LOCK:semaphore=HOSTS.setdefault(host,threading.Semaphore(2))
    with semaphore:
        with LOCK:
            start=max(time.monotonic(),NEXT_REQUEST,PAUSES.get(host,0),RATE_PAUSE_UNTIL)
            delay=max(0,start-time.monotonic());NEXT_REQUEST=start+.4;PAUSES[host]=start+.8
        if delay:time.sleep(delay)
        while True:
            with LOCK:pause=RATE_PAUSE_UNTIL-time.monotonic()
            if pause<=0:break
            time.sleep(min(pause,25))
        meta=dict(key=key,url=url,retrieved_at=datetime.now(timezone.utc).isoformat())
        if old:meta.update(retry_count=old.get('retry_count',0)+1,previous_attempts=old.get('previous_attempts',[])+[{k:old.get(k) for k in ['retrieved_at','http_status','status','error','retry_after']}])
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; PublicEducationResearch/1.0)','Accept':'text/html,application/json;q=0.9,*/*;q=0.5'})
            with urllib.request.urlopen(request,timeout=22) as response:
                raw=response.read(6*1024*1024+1);meta.update(http_status=response.status,final_url=response.url,content_type=response.headers.get('Content-Type',''))
            if len(raw)>6*1024*1024:raise ValueError('Response exceeds research acquisition limit')
            if raw[:2]==b'\x1f\x8b':raw=gzip.decompress(raw)
            path=CACHE/(key+'.body.gz');compressed=gzip.compress(raw,mtime=0);path.write_bytes(compressed)
            meta.update(bytes=len(raw),sha256=hashlib.sha256(compressed).hexdigest(),body_sha256=hashlib.sha256(raw).hexdigest(),body_file=path.name,status='retrieved',archive_kind='gzip_complete_decoded_HTTP_response_body')
            parsed=extract(raw,meta['content_type'],meta['final_url']);meta.update({k:parsed[k] for k in ['title','headings','links']});meta.update(organizations=parsed.get('organizations',[]),staff_api_leads=parsed.get('staff_api_leads',[]))
            (CACHE/(key+'.txt')).write_text(parsed['text']);(CACHE/(key+'.embedded.txt')).write_text(parsed.get('embedded_text',''))
            bodytext=parsed['text']+'\n'+parsed.get('embedded_text','')
            if re.search(r'Access Denied|Please verify you are a human|Just a moment\.\.\.|enable JavaScript and cookies to continue|Your request has been blocked|Robot Challenge|Press and Hold',bodytext,re.I) and len(parsed['text'])<2500:meta['status']='access_blocked'
            meta['monolingual_contexts']=[clean(bodytext[max(0,m.start()-180):m.end()+220]) for m in list(MONO.finditer(bodytext))[:35]]
            meta['bilingual_contexts']=[clean(bodytext[max(0,m.start()-120):m.end()+180]) for m in list(BILINGUAL.finditer(bodytext))[:20]]
            meta['regular_program_contexts']=[clean(bodytext[max(0,m.start()-120):m.end()+180]) for m in list(REGULAR.finditer(bodytext))[:20]]
            meta['has_both_language_labels']=bool(meta['monolingual_contexts'] and meta['bilingual_contexts'])
        except urllib.error.HTTPError as e:
            meta.update(http_status=e.code,status='http_error',error=str(e))
            try:meta['error_body_excerpt']=e.read(2000).decode('utf-8','replace')
            except Exception as body_error:meta['error_body_excerpt']='Could not read error response: '+str(body_error)
            if e.code==429:
                meta['retry_after']=e.headers.get('Retry-After')
                try:pause=float(meta['retry_after'] or '10')
                except ValueError:pause=15
                with LOCK:RATE_PAUSE_UNTIL=max(RATE_PAUSE_UNTIL,time.monotonic()+pause)
        except Exception as e:meta.update(status='retrieval_failed',error=str(e))
        mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
        return meta

def capture_many(urls,workers=16,retry_errors=False):
    unique=list(dict.fromkeys(normalize_url(u) for u in urls if normalize_url(u)))
    # Interleave hosts so many campuses at one district do not occupy all workers.
    hosts=collections.defaultdict(list)
    for u in unique:hosts[urllib.parse.urlsplit(u).netloc].append(u)
    ordered=[]
    while hosts:
        for h in list(hosts):
            ordered.append(hosts[h].pop())
            if not hosts[h]:del hosts[h]
    results=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(capture,u,retry_errors):u for u in ordered}
        for n,f in enumerate(as_completed(futures),1):
            try:results.append(f.result())
            except Exception as e:results.append(dict(url=futures[f],status='worker_failed',error=str(e)))
            if n%40==0 or n==len(ordered):print(json.dumps(dict(done=n,total=len(ordered),outcomes=dict(collections.Counter(m['status'] for m in results)),both_labels=sum(m.get('has_both_language_labels',False) for m in results))),flush=True)
    return results

def roster():
    target=TARGETS or ROOT/'data/registry/tx_staff_delivery_review_2026_11_07/campus_targets.json'
    result=json.loads(target.read_text())
    (CACHE/'roster.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def read_docs():
    docs={}
    for p in CACHE.glob('*.json'):
        if len(p.stem)!=22:continue
        try:d=json.loads(p.read_text())
        except (OSError,ValueError):continue
        if isinstance(d,dict) and d.get('url'):docs[d['url']]=d
    for p in CACHE.glob('*.browser.json'):
        try:d=json.loads(p.read_text())
        except (OSError,ValueError):continue
        if d.get('status')=='retrieved' or d['url'] not in docs:docs[d['url']]=d
    return docs

def match_score(school,label,url):
    wanted=tokens(school['school_name']);label_tokens=tokens(label)
    if not wanted:return 0
    if school['school_level']=='elementary' and re.search(r'\b(high school|middle school|junior high)\b',label,re.I):return 0
    if school['school_level']=='secondary_6_plus' and re.search(r'\b(elementary|primary)\b',label,re.I):return 0
    if re.search(r'\bMIDDLE\b|\bM S\b|\bJ H\b',school['school_name'],re.I) and re.search(r'\bhigh school\b',label,re.I) and not re.search(r'junior|middle',label,re.I):return 0
    if re.search(r'\bH S\b|\bHIGH\b',school['school_name'],re.I) and re.search(r'\bmiddle school\b',label,re.I) and not re.search(r'junior',school['school_name'],re.I):return 0
    common=wanted&label_tokens;recall=len(common)/len(wanted)
    # Abbreviated state labels can omit the person's first name on the site.
    if not common or (recall<.55 and len(common)<2):return 0
    return round(10*recall+2*len(common)+(4 if wanted<=label_tokens else 0),2)

def discover():
    schools=json.loads((CACHE/'roster.json').read_text());docs=read_docs();by_district=collections.defaultdict(list)
    extras=json.loads((CACHE/'additional_staff_leads.json').read_text()) if (CACHE/'additional_staff_leads.json').exists() else {}
    for school in schools:
        for u in {school['official_web_url'],school['district_root']}:
            d=docs.get(u)
            if d and d.get('status')=='retrieved':by_district[school['district_id']].append(d)
    for district in {s['district_id'] for s in schools}:
        p=LEGACY/('tx_root_'+district+'.metadata.json') if LEGACY else None
        if p and p.exists():
            d=json.loads(p.read_text())
            if d.get('http_status')==200 and not d.get('error'):
                d=dict(d,key='legacy_'+district,status='retrieved',final_url=d.get('final_url',d['url']),legacy_discovery_only=True)
                by_district[district].append(d)
    for district,items in by_district.items():by_district[district]=list({d['key']:d for d in items}.values())
    owners=collections.defaultdict(set)
    for school in schools:
        for u in [school['official_web_url'],school['district_root']]:
            if u:owners[re.sub(r'^www\d*\.','',urllib.parse.urlsplit(u).netloc)].add(school['district_id'])
    for d in docs.values():
        if d.get('status')!='retrieved':continue
        host=re.sub(r'^www\d*\.','',urllib.parse.urlsplit(d['url']).netloc)
        districts=set().union(*(ids for domain,ids in owners.items() if host==domain or host.endswith('.'+domain)))
        if len(districts)==1:by_district[next(iter(districts))].append(d)
    for district,items in by_district.items():by_district[district]=list({d['key']:d for d in items}.values())
    district_links={district:list({(x['url'],x['text']):(x,d['url']) for d in items for x in d.get('links',[])}.values()) for district,items in by_district.items()}
    final_docs={d.get('final_url'):d for d in docs.values() if d.get('status')=='retrieved'}
    mapped=[];new_urls=[]
    for school in schools:
        candidates={};own=docs.get(school['official_web_url'])
        if own and own.get('status')=='retrieved':
            identity=' '.join([own.get('title',''),*own.get('headings',[])[:2]])
            score=match_score(school,identity,own['final_url'])
            if urllib.parse.urlsplit(own['final_url']).path=='/' and re.search(r'\bISD\b|independent school district',own.get('title',''),re.I) and not re.search(r'elementary|middle school|high school|academy',own.get('title',''),re.I):score=0
            if score>=10:candidates[own['final_url']]=dict(url=own['final_url'],score=score+4,basis='official_directory_link_and_page_identity',source_url=own['url'],label=own.get('title',''))
        for link,source_url in district_links.get(school['district_id'],[]):
                if re.search(r'\.(pdf|jpg|png|docx)(\?|$)',link['url'],re.I):continue
                if re.search(r'const_id=|profile|constituent|teacher|faculty|staff-directory',link['url'],re.I) and not re.search(r'elementary|middle school|high school|academy|school website',link['text'],re.I):continue
                score=match_score(school,link['text'],link['url'])
                if score>=10:
                    dest=link['url'];item=dict(url=dest,score=score,basis='school_name_on_official_navigation',source_url=source_url,label=link['text'])
                    if score>candidates.get(dest,{}).get('score',0):candidates[dest]=item
        ordered=sorted(candidates.values(),key=lambda x:(-x['score'],len(x['url'])))
        best=ordered[:3]
        # Multiple navigation aliases for the same campus are retained as leads.
        school=dict(school,campus_home_candidates=best,staff_candidates=[])
        for home in best:
            d=docs.get(home['url']) or final_docs.get(home['url'])
            if not d:new_urls.append(home['url']);continue
            for link in d.get('links',[]):
                text=link['text'];path=urllib.parse.urlsplit(link['url']).path
                score=0
                if re.search(r'staff directory|faculty directory|faculty.*team|staff.*directory',text,re.I):score=12
                elif re.search(r'\b(faculty|staff|teachers|grade level)\b',text,re.I):score=7
                elif re.search(r'/staff(?:/|$)|faculty|staff-directory|directory',path,re.I):score=5
                if re.search(r'for staff|staff resources|staff login|employment|job|staff development|handbook|student|department|school directory',text,re.I):score-=10
                if re.search(r'login|employment|careers|portal|board|calendar|news|staff-resources|for-staff',path,re.I):score-=10
                hp=urllib.parse.urlsplit(d['final_url']);lp=urllib.parse.urlsplit(link['url'])
                if hp.netloc==lp.netloc and (hp.path=='/' or lp.path.startswith(hp.path.rstrip('/')+'/')):score+=4
                if score>=9:
                    school['staff_candidates'].append(dict(link,score=score,home_url=d['final_url'],home_evidence=home['basis']))
        school['staff_candidates'].extend(extras.get(school['school_id'],[]))
        school['staff_candidates']=sorted({x['url']:x for x in school['staff_candidates']}.values(),key=lambda x:(-x['score'],len(x['url'])))[:7]
        mapped.append(school)
    (CACHE/'mapped_schools.json').write_text(json.dumps(mapped,indent=2,ensure_ascii=False)+'\n')
    (CACHE/'campus-home-followups.json').write_text(json.dumps(list(dict.fromkeys(new_urls)),indent=2)+'\n')
    first_homes=list(dict.fromkeys(s['campus_home_candidates'][0]['url'] for s in mapped if s['campus_home_candidates'] and s['campus_home_candidates'][0]['url'] not in docs and s['campus_home_candidates'][0]['url'] not in final_docs))
    (CACHE/'first-campus-home-followups.json').write_text(json.dumps(first_homes,indent=2)+'\n')
    staff=list(dict.fromkeys(x['url'] for school in mapped for x in school['staff_candidates']))
    (CACHE/'staff-urls.json').write_text(json.dumps(staff,indent=2)+'\n')
    print(json.dumps(dict(campuses=len(schools),home_identified=sum(bool(s['campus_home_candidates']) for s in mapped),staff_link_identified=sum(bool(s['staff_candidates']) for s in mapped),staff_urls=len(staff),campus_home_followup_urls=len(set(new_urls)))),flush=True)

def staff_followups():
    schools=json.loads((CACHE/'mapped_schools.json').read_text());docs=read_docs();urls=[];browser=[];children={}
    for school in schools:
        selected=[]
        for lead in school['staff_candidates']:
            d=docs.get(lead['url'])
            if not d:urls.append(lead['url']);continue
            if d.get('status')!='retrieved':browser.append(lead['url']);continue
            for link in d.get('links',[]):
                label=link['text'].strip();dest=link['url']
                if re.search(r'\b(kindergarten|pre.?k|first grade|second grade|third grade|fourth grade|fifth grade|sixth grade|[1-6](st|nd|rd|th)? grade|grade [k1-6]|grade level|teaching team)\b',label,re.I):
                    if urllib.parse.urlsplit(dest).netloc==urllib.parse.urlsplit(d['final_url']).netloc and dest!=d['final_url']:
                        selected.append(dict(link,parent_url=d['url']))
                elif re.search(r'const_page=|staff.*page=|pagenum=|pageIndex=',dest,re.I) and re.fullmatch(r'\d+|Next|Next Page|[›»→]',label,re.I):selected.append(dict(link,parent_url=d['url']))
        children[school['school_id']]=list({x['url']:x for x in selected}.values())[:14]
        urls.extend(x['url'] for x in children[school['school_id']] if x['url'] not in docs)
    (CACHE/'grade-team-leads.json').write_text(json.dumps(children,indent=2,ensure_ascii=False)+'\n')
    (CACHE/'staff-followup-urls.json').write_text(json.dumps(list(dict.fromkeys(urls)),indent=2)+'\n')
    (CACHE/'browser-staff-followup-urls.json').write_text(json.dumps(list(dict.fromkeys(browser)),indent=2)+'\n')
    print(json.dumps(dict(new_http_urls=len(set(urls)),browser_fallback_urls=len(set(browser)),schools_with_grade_team_leads=sum(bool(x) for x in children.values()))))

def enrich_links():
    updated=0
    for p in CACHE.glob('*.json'):
        if not (len(p.stem)==22 or p.name.endswith('.browser.json')):continue
        try:d=json.loads(p.read_text())
        except ValueError:continue
        if d.get('status')!='retrieved' or not d.get('body_file'):continue
        try:raw=gzip.decompress((CACHE/d['body_file']).read_bytes())
        except (OSError,EOFError):continue
        if b'__NUXT_DATA__' not in raw:continue
        links,organizations,staff_api=application_links(raw,d.get('final_url',d['url']))
        if not links:continue
        d['links']=list({(x['url'],x['text']):x for x in d.get('links',[])+links}.values());d['organizations']=organizations;d['staff_api_leads']=staff_api
        p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');updated+=1
    print(json.dumps(dict(enriched_application_navigation_documents=updated)))

def main():
    global ROOT,CACHE,TARGETS,LEGACY
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['roster','homes','urls','discover','staff-followups','enrich']);p.add_argument('--file',type=Path);p.add_argument('--workers',type=int,default=16);p.add_argument('--retry-errors',action='store_true');p.add_argument('--repo-root',type=Path,default=ROOT);p.add_argument('--cache',type=Path,default=CACHE);p.add_argument('--targets',type=Path);p.add_argument('--legacy-discovery-cache',type=Path);args=p.parse_args()
    ROOT=args.repo_root;CACHE=args.cache;TARGETS=args.targets;LEGACY=args.legacy_discovery_cache;CACHE.mkdir(parents=True,exist_ok=True)
    if args.stage=='roster':print(json.dumps(dict(campuses=len(roster()))));return
    if args.stage=='discover':discover();return
    if args.stage=='staff-followups':staff_followups();return
    if args.stage=='enrich':enrich_links();return
    if args.stage=='homes':
        schools=roster();urls=[r['official_web_url'] for r in schools]+[r['district_root'] for r in schools]
    else:urls=json.loads(args.file.read_text())
    results=capture_many(urls,args.workers,args.retry_errors)
    (CACHE/(args.stage+'-results.json')).write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
