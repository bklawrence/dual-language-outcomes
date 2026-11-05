"""Save public CCD school-grade context; never import assessment/demographic data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..validation import load

DIRECTORY = 'data/raw/elementary_audit_2026_11_04'
API = 'https://educationdata.urban.org/api/v1/schools/ccd/directory/2024/'
FIELDS = ['year','ncessch','school_name','lea_name','state_leaid','seasch',
          'lowest_grade_offered','highest_grade_offered','school_level','school_status','fips']


def collect_state(root, state, fips):
    query = dict(fips=int(fips), fields=','.join(FIELDS))
    url = API + '?' + urlencode(query)
    destination = root / DIRECTORY
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / ('ccd_2024_' + state.lower() + '.json')
    metadata = path.with_suffix('.metadata.json')
    if path.exists() or metadata.exists():
        if not (path.exists() and metadata.exists()):
            raise ValueError('Incomplete grade snapshot: ' + state)
        raw, meta = path.read_bytes(), json.loads(metadata.read_text())
        if meta['url'] != url or hashlib.sha256(raw).hexdigest() != meta['sha256']:
            raise ValueError('Grade query/hash changed; use another vintage')
    else:
        request = Request(url, headers={'User-Agent':'DualLanguageOutcomesResearch/1.0'})
        with urlopen(request, timeout=50) as response:
            raw = response.read()
        data = json.loads(raw)
        if data.get('count',0) < len(data.get('results',[])) or not data.get('results'):
            raise ValueError('Directory pagination/empty response requires review: ' + state)
        if any(set(r) != set(FIELDS) or r['year'] != 2024 or r['fips'] != int(fips) for r in data['results']):
            raise ValueError('Unexpected directory fields/year/state: ' + state)
        meta = dict(url=url, dataset_url=API, publisher='Urban Institute Education Data Portal, NCES CCD directory',
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    sha256=hashlib.sha256(raw).hexdigest(), rows=len(data['results']),
                    selection=query, source_api_year=2024,
                    evidence_period_raw='CCD directory API year=2024',
                    capture_method='original_public_HTTP_response',
                    limitations='School-grade context only; no DL programme confirmation, programme grade allocation or historical cohort exposure inferred.')
        path.write_bytes(raw)
        metadata.write_text(json.dumps(meta,indent=2)+'\n')
    data = json.loads(raw)
    total, next_url = meta['rows'], data.get('next')
    page = 1
    while next_url:
        page += 1
        if page > 10 or not next_url.startswith(API):
            raise ValueError('Unexpected pagination URL/safety limit: ' + state)
        path = destination / ('ccd_2024_' + state.lower() + '_page' + str(page).zfill(2) + '.json')
        metadata = path.with_suffix('.metadata.json')
        if path.exists() or metadata.exists():
            if not (path.exists() and metadata.exists()):
                raise ValueError('Incomplete directory page')
            raw, page_meta = path.read_bytes(), json.loads(metadata.read_text())
            if page_meta['url'] != next_url or hashlib.sha256(raw).hexdigest() != page_meta['sha256']:
                raise ValueError('Directory page selection/hash changed')
        else:
            with urlopen(Request(next_url,headers={'User-Agent':'DualLanguageOutcomesResearch/1.0'}),timeout=50) as response:
                raw = response.read()
            payload = json.loads(raw)
            if not payload.get('results') or any(set(r)!=set(FIELDS) or r['year']!=2024 or r['fips']!=int(fips) for r in payload['results']):
                raise ValueError('Unexpected paginated directory records')
            page_meta = dict(meta, url=next_url, rows=len(payload['results']),
                retrieved_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest())
            path.write_bytes(raw)
            metadata.write_text(json.dumps(page_meta,indent=2)+'\n')
        total += page_meta['rows']
        next_url = json.loads(raw).get('next')
    if total != data['count']:
        raise ValueError('Directory pagination count mismatch: ' + state)
    return dict(state_code=state,rows=total,pages=page)


def collect(root):
    _, tables = load(root)
    selected = {r['state_code'] for r in tables['programs']}
    states = [(r['state_code'],r['state_fips']) for r in tables['states'] if r['state_code'] in selected]
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda spec:collect_state(root,*spec),states))
