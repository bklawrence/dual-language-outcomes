"""Export a public review queue and accept authenticated website submissions."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import os
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, unquote

from .baseline import school_rows, programme_rows
from .baseline_selection import Selection
from .hand_coding import CONFIG, batches, accept_issue
from .validation import load


def display_name(name):
    if name != name.upper(): return name
    acronyms={'isd':'ISD','cisd':'CISD','usd':'USD','es':'ES','el':'Elementary','k-8':'K–8','p.s.':'P.S.','ps':'P.S.'}
    return ' '.join(acronyms.get(w.lower(),w.capitalize()) for w in name.split())


def export(root, destination):
    config=json.loads((root/CONFIG).read_text());_,tables=load(root)
    rules=json.loads((root/'data/baselines/national_structural_v1/rules.json').read_text());selection=Selection(tables,rules)
    reference=config['reference_year'];school_views=[]
    for yr in sorted({reference,*rules['source_vintage_exceptions'].values()}):school_views.extend(school_rows(selection,tables,yr))
    programmes,_,_,_=programme_rows(selection,tables,school_views,reference)
    sources={r['source_id']:r for r in tables['sources']}
    site_index={r['site_id']:r for r in tables['program_sites']}
    fields=('delivery_structure','population_model','instruction_languages','programme_grade_scope')
    allocated={r['school_id'] for r in programmes if r['elementary_model_labels_normalized'] and r['elementary_model_status'] not in {'conflicting','later_only','not_reported'} and not r['elementary_model_status'].startswith('not_applicable')}
    grouped=defaultdict(list)
    for row in programmes:
        manual_event=selection.program_events.get(row['site_id'])
        if (row['school_level']=='elementary' or row['school_id'] in allocated) and (row['school_id'] in allocated or row['in_working_cohort'] or row['in_confirmed_qualifying_cohort'] or manual_event):
            grouped[row['school_id']].append(row)
    manual=[]
    for _,batch in batches(root):
        for record in batch['records']:
            manual.append(dict(record,hand_coded=True,batch_id=batch['batch_id'],github_actor=batch['submission']['github_actor'],
                               submitted_at=batch['submission']['submitted_at'],issue_url=batch['submission']['issue_url']))
    manual_by_school=defaultdict(list)
    for r in manual:manual_by_school[r['school_id']].append(r)
    cases=[]
    for sid,rows in sorted(grouped.items()):
        first=rows[0];sites=[];references={}
        school_name=display_name(first['school_name']);tokens=[w for w in re.findall(r'[a-z]+',school_name.lower()) if len(w)>3 and w not in {'school','elementary','academy','international','dual','language'}]
        def add_reference(url,locator='',excerpt=''):
            if not url or not url.startswith(('https://','http://')) or len(url)>2048:return
            parts=urlsplit(url);match=sum(t in unquote(parts.path).lower() or t in parts.netloc.lower() for t in tokens)
            score=match*4+(0 if parts.path.lower().endswith('.pdf') else 2)
            if 'github.com' in parts.netloc or 'webapp.cal.org' in parts.netloc:score-=5
            label=('School / district program page' if not parts.path.lower().endswith('.pdf') else 'Program document')
            if url not in references:references[url]=dict(url=url,label=label,domain=parts.netloc.removeprefix('www.'),locator=locator,excerpt=excerpt[:700],score=score)
        for row in rows:
            site=site_index[row['site_id']];known={};source_ids=set()
            for variable in fields:
                field,_=selection.select_field(site,variable,reference)
                known[variable]=dict(value=json.loads(field['value_json']),status=field['value_status'])
                source_ids.update(field['selected_source_ids'].split(' | '))
            grade=known['programme_grade_scope']['value']
            allocation,_=selection.select_allocations(site,reference,row['school_level'],grade)
            values=json.loads(allocation['value_json'])
            known['elementary_allocation_model']=dict(value=sorted({v['model_label_normalized'] for v in values if v.get('model_label_normalized')}),status=allocation['value_status'])
            source_ids.update(allocation['selected_source_ids'].split(' | '))
            for source_id in sorted(source_ids):
                if source_id in sources:add_reference(sources[source_id]['source_url'])
            for observation in selection.configs[site['site_id']]:
                if observation['source_id'] in source_ids:
                    note=observation.get('notes') or '';excerpt=note.split('Source quote:',1)[-1] if 'Source quote:' in note else ''
                    url=sources[observation['source_id']]['source_url']
                    if url in references:
                        references[url]['locator']=observation.get('source_locator') or ''
                        if excerpt:references[url]['excerpt']=excerpt[:700]
            languages=known['instruction_languages']['value']
            from .review_events import event_at
            event=event_at(selection.program_events.get(site['site_id'],[]),reference)
            sites.append(dict(site_id=site['site_id'],program_id=site['program_id'],program_name=row['program_name'],
                              label=' + '.join(languages) or row['program_name'],known=known,program_event=event,
                              hand_coded_variables=[v for v in known if (site['site_id'],reference,v) in selection.overrides and selection.overrides[(site['site_id'],reference,v)].get('hand_coded')]))
        for r in manual_by_school[sid]:
            add_reference(r.get('evidence_url'),r.get('source_locator',''),r.get('source_quote',''))
        missing=[]
        for variable in ['delivery_structure','population_model','elementary_allocation_model','instruction_languages']:
            if any(not s['known'][variable]['value'] or (variable!='elementary_allocation_model' and s['known'][variable]['status']!='documented') for s in sites):missing.append(variable)
        cases.append(dict(school_id=sid,school_name=school_name,canonical_school_name=first['school_name'],state_code=first['state_code'],
                          district_name=display_name(first['district_names']),allocation_known=sid in allocated,
                          sites=sites,missing=missing,references=sorted(references.values(),key=lambda r:(-r['score'],r['url']))[:6],
                          hand_coded_reviews=[{k:r.get(k) for k in ['review_id','reviewer','github_actor','submitted_at','reference_year','coding_method','issue_url']}
                                             for r in sorted(manual_by_school[sid],key=lambda r:(r['submitted_at'],r['review_id']))[-5:]]))
    state_names={r['state_code']:r['state_name'] for r in tables['states']}
    manifest=json.loads((root/'data/curated/manifest.json').read_text())
    district_names={}
    for p in programmes:
        if p['district_names']:district_names.setdefault(p['school_id'],display_name(p['district_names']))
    destinations=[dict(school_id=r['school_id'],school_name=display_name(r['school_name']),state_code=r['state_code'],
                       district_name=district_names.get(r['school_id'],'')) for r in tables['schools']]
    from .review_leaderboard import leaderboard
    data=dict(version=1,repository=config['repository'],site_url=config['site_url'],reference_year=reference,
              dataset_build_id=manifest['build_id'],updated_at=manifest['built_at'],state_names=state_names,
              accepted_review_ids=[r['review_id'] for r in manual],accepted_batch_ids=[b['batch_id'] for _,b in batches(root)],cases=cases,destination_schools=destinations,
              leaderboard=leaderboard(manual,{r['school_id']:r for r in tables['schools']}))
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'queue.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
    return dict(schools=len(cases),allocation_known=len(allocated),delivery_queue=sum(c['allocation_known'] and any(s['known']['elementary_allocation_model']['value'] and s['known']['elementary_allocation_model']['status'] not in {'conflicting','later_only','not_reported'} and s['known']['delivery_structure']['status']!='documented' for s in c['sites']) for c in cases))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());commands=p.add_subparsers(dest='command',required=True)
    e=commands.add_parser('export');e.add_argument('--destination',type=Path,default=Path('review-app/public/data'))
    a=commands.add_parser('accept-issue');a.add_argument('--event',type=Path,required=True)
    c=commands.add_parser('collect-issues');c.add_argument('--result',type=Path,required=True)
    args=p.parse_args();root=args.root.resolve()
    if args.command=='export':result=export(root,root/args.destination)
    elif args.command=='accept-issue':result=accept_issue(root,json.loads(args.event.read_text()))
    else:
        config=json.loads((root/CONFIG).read_text());repo=config['repository']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid configured repository.')
        token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not token:raise ValueError('GitHub authentication is unavailable to the trusted workflow.')
        result={'accepted':[],'rejected':[]};page=1
        while True:
            request=Request(f'https://api.github.com/repos/{repo}/issues?state=open&per_page=100&page={page}',
                            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
            with urlopen(request,timeout=30) as stream:issues=json.load(stream)
            for issue in issues:
                if 'pull_request' in issue or not issue['title'].startswith('[DL Review]'):continue
                try:
                    receipt=accept_issue(root,{'issue':issue});result['accepted'].append(dict(receipt,issue_number=issue['number']))
                except ValueError as exc:
                    result['rejected'].append(dict(issue_number=issue['number'],reason=str(exc)))
            if len(issues)<100:break
            page+=1
        args.result.write_text(json.dumps(result,indent=2)+'\n')
        result={'accepted_batches':len(result['accepted']),'rejected_batches':len(result['rejected'])}
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
