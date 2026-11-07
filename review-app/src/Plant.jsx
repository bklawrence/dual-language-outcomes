import React from 'react';
import { Droplets } from 'lucide-react';
import { gardenState } from './garden';

export default function Plant({garden, watering, now}) {
  const state = gardenState(garden, now);
  const leaves = [
    {x:79,y:113,r:-31,flip:false}, {x:103,y:95,r:34,flip:true},
    {x:83,y:77,r:-24,flip:false}, {x:100,y:60,r:25,flip:true},
    {x:86,y:43,r:-18,flip:false}, {x:95,y:25,r:15,flip:true},
  ];
  return <section className={'plant-card '+(watering?'is-watering':'')} aria-label="Your research plant">

    <svg viewBox="0 0 190 190" className="plant-art" role="img" aria-label={`Your plant: ${state.label}. ${state.leaves} leaves remaining.`}>
      <defs><linearGradient id="pot" x1="0" x2="1"><stop stopColor="#c88465"/><stop offset="1" stopColor="#d99b79"/></linearGradient><linearGradient id="leaf" x2="1" y2="1"><stop stopColor="#6e9b65"/><stop offset="1" stopColor="#38684b"/></linearGradient></defs>
      <ellipse cx="95" cy="176" rx="52" ry="6" fill="#48644a" opacity=".08"/>
      <path d={`M95 144 Q${89+state.droop*10} 99 ${93+state.droop*9} 24`} fill="none" stroke={state.moisture>20?'#64815a':'#929066'} strokeWidth="3.6" strokeLinecap="round"/>
      {leaves.map((leaf,i)=><g key={i} style={{opacity:i<state.leaves?1:0,transform:`translate(${leaf.x}px,${leaf.y}px) rotate(${leaf.r+(leaf.flip?1:-1)*state.droop*30}deg) scale(${leaf.flip?-1:1},1)`,transformOrigin:'0 0'}} className="plant-leaf"><path d="M0 1 C-3 -22 -31 -27 -34 -18 C-36 -3 -12 12 0 1Z" fill={state.moisture>30?'url(#leaf)':'#a2a174'}/><path d="M-2 0 Q-15 -10 -28 -15" fill="none" stroke="#c4d3a4" strokeWidth=".8" opacity=".65"/></g>)}
      {[...Array(6-state.leaves)].map((_,i)=><path key={i} d="M0 0 C-8 -11 -20 -8 -18 -1 C-14 6 -5 6 0 0" transform={`translate(${48+i*19} ${174+(i%2)*4}) rotate(${i*48-25}) scale(.65)`} fill="#b9a779" opacity=".8"/>)}
      <path d="M67 139 L73 168 Q95 180 117 168 L123 139Z" fill="url(#pot)"/>
      <rect x="64" y="132" width="62" height="13" rx="4" fill="#dca385"/>
      <ellipse cx="95" cy="133" rx="27" ry="4" fill="#8b624b"/>
      <path d="M79 150 V166 M88 151 V169 M99 151 V170 M110 150 V166" stroke="#bd795e" opacity=".3" strokeWidth="1.3"/>
      <g opacity={state.webs} stroke="#8d9991" strokeWidth=".8" fill="none"><path d="M130 10 L130 85 M130 10 L180 10 M130 10 L170 65 M130 10 L182 38 M130 30 Q140 32 146 29 Q155 27 159 10 M130 47 Q147 49 157 43 Q171 35 175 10 M130 65 Q155 68 170 56 Q182 45 183 24"/><path d="M161 62 v13"/><ellipse cx="161" cy="78" rx="2" ry="3" fill="#7d8a80"/></g>
      <g className="water-drops" fill="#75a6b5"><path d="M91 9 Q82 21 91 22 Q100 21 91 9"/><path d="M109 30 Q102 39 109 40 Q116 39 109 30"/></g>
      {watering&&<text x="141" y="109" className="water-plus" fill="#3c7165" fontSize="12">+ water</text>}
    </svg>
    <div className="plant-name">Research fern</div><p className="plant-mood" aria-live="polite">{state.label}</p>
    <div className="moisture-line"><Droplets size={13}/><span className="moisture-track"><span style={{width:state.moisture+'%'}}/></span></div>
    <p className="plant-help">Saved reviews and notes water the fern.</p>
    <span className="plant-tooltip">Small saves help it grow. After a few days without water it gets thirsty; longer breaks bring fallen leaves and cobwebs. It can always recover.</span>
  </section>;
}
