"""Capture directory grade context for the existing Texas campus working set.

The 2024–25 AskTED-derived ArcGIS layer is a school directory, not a DL roster.
Neither a grade range nor an ID match confirms the grades of a DL programme.
"""
from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LAYER = ('https://services2.arcgis.com/5MVN2jsqIrNZD4tP/ArcGIS/rest/services/'
         'Schools_2024_to_2025/FeatureServer/0')
DESTINATION = 'data/raw/tx/grade_context_2024_25_captured_2026_11_04'


def collect(root):
    destination = root / DESTINATION
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    for offset in range(0, 20000, 2000):
        query = dict(where='1=1',
                     outFields='ObjectID,USER_District_Number,USER_School_Number,USER_School_Name,USER_Grade_Range',
                     returnGeometry='false', orderByFields='ObjectID', resultRecordCount=2000,
                     resultOffset=offset, f='json')
        url = LAYER + '/query?' + urlencode(query)
        key = 'page_' + str(offset // 2000 + 1).zfill(2)
        path, metadata = destination / (key + '.json'), destination / (key + '.metadata.json')
        if path.exists() or metadata.exists():
            if not (path.exists() and metadata.exists()):
                raise ValueError('Incomplete directory snapshot: ' + key)
            raw, meta = path.read_bytes(), json.loads(metadata.read_text())
            if meta['url'] != url or hashlib.sha256(raw).hexdigest() != meta['sha256']:
                raise ValueError('Directory selection/hash changed; use a new vintage')
        else:
            request = Request(url, headers={'User-Agent': 'DualLanguageOutcomesResearch/1.0'})
            with urlopen(request, timeout=50) as response:
                raw = response.read()
            data = json.loads(raw)
            if 'error' in data or 'features' not in data:
                raise ValueError('Incomplete/invalid directory query: ' + key)
            meta = dict(url=url, dataset_url=LAYER, retrieved_at=datetime.now(timezone.utc).isoformat(),
                        sha256=hashlib.sha256(raw).hexdigest(), school_year='2024-25',
                        selection=query, rows=len(data['features']),
                        capture_method='original_public_HTTP_response',
                        limitations='Directory campus grades only; not DL programme grades or 2023–24 operating confirmation.')
            path.write_bytes(raw)
            metadata.write_text(json.dumps(meta, indent=2) + '\n')
        results.append(dict(path=str(path.relative_to(root)), rows=meta['rows']))
        if not json.loads(raw).get('exceededTransferLimit'):
            return results
    raise ValueError('Directory pagination safety limit reached; collection incomplete')
