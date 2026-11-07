import React from 'react';
import {Award,BookOpen,Flower2,Globe2,Leaf,RefreshCw,Search,Trophy} from 'lucide-react';

const BADGES=[
  {name:'First review',rule:'1 published review',icon:Leaf,earned:r=>r.reviews>=1},
  {name:'Ten reviews',rule:'10 published reviews',icon:BookOpen,earned:r=>r.reviews>=10},
  {name:'In bloom',rule:'25 published reviews',icon:Flower2,earned:r=>r.reviews>=25},
  {name:'Fifty reviews',rule:'50 published reviews',icon:Award,earned:r=>r.reviews>=50},
  {name:'A hundred reviews',rule:'100 published reviews',icon:Trophy,earned:r=>r.reviews>=100},
  {name:'Source scout',rule:'5 evidence-only reviews',icon:Search,earned:r=>r.evidence_only>=5},
  {name:'Across states',rule:'Reviews in 3 states',icon:Globe2,earned:r=>r.states>=3},
];

export default function Leaderboard({rows,reviewer,updatedAt,onRefresh,refreshing}){
  const me=reviewer.trim().toLowerCase().replace(/\s+/g,' ');
  return <main className="saved-view leaderboard-view">
    <div className="section-eyebrow">SHARED FIELDWORK</div><h1>Leaderboard</h1>
    <p className="section-intro">Published reviews, credited to the researcher named in each entry. Coding decisions and saved evidence both count. One submission can contain several school reviews.</p>
    <div className="saved-toolbar"><span>{rows.reduce((n,r)=>n+r.reviews,0)} reviews · {rows.length} reviewers</span><button className="text-button" onClick={onRefresh}><RefreshCw size={14}/>{refreshing?'Refreshing…':'Refresh totals'}</button></div>
    {!rows.length?<p className="review-empty">The first published review will start the leaderboard. Saved work counts after it reaches the dataset.</p>:<div className="leaderboard-scroll"><table className="leaderboard-table"><thead><tr><th scope="col">Rank</th><th scope="col">Reviewer</th><th scope="col">Reviews</th><th scope="col">Schools</th><th scope="col">Submissions</th><th scope="col">Badges</th></tr></thead><tbody>{rows.map((r,i)=><tr key={r.reviewer.toLowerCase()} className={r.reviewer.toLowerCase().replace(/\s+/g,' ')===me?'your-ranking':''}>
      <td>{i+1}</td><th scope="row">{r.reviewer}</th><td>{r.reviews}</td><td>{r.schools}</td><td>{r.submissions}</td><td><div className="earned-badges">{BADGES.filter(b=>b.earned(r)).map(({name,rule,icon:Icon})=><span key={name} title={name+' · '+rule} aria-label={name+' badge: '+rule}><Icon size={17} aria-hidden="true"/></span>)}</div></td>
    </tr>)}</tbody></table></div>}
    <p className="leaderboard-note">Ranked by reviews, then schools covered. Credit follows the recorded reviewer name, including work published by someone else. Use a consistent reviewer name so your contributions stay together.</p>
    <h2 className="badges-heading">Badges to earn</h2><dl className="badge-key">{BADGES.map(({name,rule,icon:Icon})=><div key={name}><Icon size={18}/><dt>{name}</dt><dd>{rule}</dd></div>)}</dl>
    <p className="leaderboard-note">Totals cover published work across all review years. Empty parked cases and drafts add no points. Updated {new Date(updatedAt).toLocaleString()}.</p>
  </main>;
}
