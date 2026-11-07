import React from 'react';
import { gardenState } from './garden';

function Flower({kind, x, y}) {
  return <g className="plant-flower" aria-hidden="true">
    <path d={`M96 ${y+21} Q${x} ${y+39} ${x} ${y+5}`} stroke="#64815a" strokeWidth="1.5" fill="none"/>
    <g transform={`translate(${x} ${y})`}>
      {kind === 0 ? <>
        {[...Array(9)].map((_,i)=><g key={i} transform={`rotate(${i*40})`}>
          <path d="M0 1 C-12 -4 -13 -19 -5 -17 C3 -15 7 -6 0 1Z" fill={i%2?'#c4999f':'#b48291'}/>
          <path d="M-5 -14 Q-10 -20 -7 -23" stroke="#8d6176" strokeWidth=".7" fill="none"/>
          <circle cx="-7" cy="-23" r="1.1" fill="#b79951"/>
        </g>)}
        <circle r="4.7" fill="#72586c"/><circle cx="-1" cy="-1" r="1.7" fill="#d9bb71"/>
      </> : kind === 1 ? <>
        <path d="M0 -16 Q-7 -12 -8 -2 Q-12 7 -16 9 Q0 17 16 9 Q10 5 8 -2 Q6 -12 0 -16Z" fill="#c1a267"/>
        <path d="M-8 -1 Q0 8 8 -1 M0 -14 V12" stroke="#8f7651" strokeWidth=".8" fill="none"/>
        {[-7,0,7].map((x,i)=><g key={x}><path d={`M${x} 11 Q${x+4} 20 ${x} ${24+(i%2)*3}`} stroke="#8f7651" strokeWidth=".8" fill="none"/><circle cx={x} cy={24+(i%2)*3} r="2" fill="#8c6c86"/></g>)}
        <path d="M-5 -11 Q0 -16 5 -11" stroke="#6e825c" strokeWidth="2" fill="none"/>
      </> : <>
        {[...Array(7)].map((_,i)=><g key={i} transform={`rotate(${i*360/7})`}>
          <path d="M0 1 Q-14 -10 -7 -18 Q3 -24 5 -14 Q8 -2 0 1Z" fill="#c1b6c9" stroke="#96839e" strokeWidth=".6"/>
          <ellipse cx="-2" cy="-13" rx="2" ry="5" fill="#fffff8" opacity=".8"/>
        </g>)}
        <circle r="4" fill="#9b925c"/>
        {[0,1,2].map(i=><circle key={i} cx={i*3-3} cy={i%2?2:-1} r="1" fill="#e6d8a1"/>)}
      </>}
    </g>
  </g>;
}

function Butterfly({x, y, color, angle, delay}) {
  return <g transform={`translate(${x} ${y}) rotate(${angle})`} className="plant-butterfly" aria-hidden="true">
    <g className="butterfly-flight" style={{animationDelay:delay+'s'}}>
      <g className="butterfly-wings" style={{animationDelay:delay+'s'}} fill={color}>
        <path d="M0 1 C-6 -16 -18 -17 -17 -7 C-17 1 -7 5 0 1Z M0 1 C6 -16 18 -17 17 -7 C17 1 7 5 0 1Z"/>
        <path d="M0 1 C-13 -1 -14 9 -8 11 C-3 13 0 6 0 1Z M0 1 C13 -1 14 9 8 11 C3 13 0 6 0 1Z" opacity=".7"/>
        <path d="M-3 0 L-12 -8 M3 0 L12 -8" stroke="#fffff8" strokeWidth=".7" opacity=".75"/>
        <circle cx="-12" cy="-6" r="1.5" fill="#fffff8" opacity=".65"/><circle cx="12" cy="-6" r="1.5" fill="#fffff8" opacity=".65"/>
      </g>
      <path d="M0 -4 Q-1 2 0 8 M0 -4 Q-3 -9 -5 -8 M0 -4 Q3 -9 5 -8" stroke="#625f50" strokeWidth="1.1" fill="none" strokeLinecap="round"/>
    </g>
  </g>;
}

export default function Plant({garden, watering, now}) {
  const state = gardenState(garden, now);
  const height = 90 * state.growth, stemTop = 24-height;
  const leaves = Array.from({length:state.maxLeaves},(_,i)=>({
    x:i%2?102:82, y:113-i*(88+height)/(state.maxLeaves-1),
    r:i%2?30:-27, flip:Boolean(i%2),
  }));
  const flowers = [{x:56,y:stemTop+22},{x:139,y:stemTop+61},{x:44,y:stemTop+110}];
  const butterflies = [
    {x:163,y:stemTop+8,color:'#b7955f',angle:18,delay:0},
    {x:24,y:stemTop+67,color:'#b48b9e',angle:-24,delay:-2},
    {x:112,y:stemTop-9,color:'#91a79e',angle:8,delay:-4},
  ];
  return <section className={'plant-card '+(watering?'is-watering':'')} aria-label="Your research plant" style={{'--plant-growth':state.growth}}>
    <svg viewBox={`0 ${-height} 190 ${190+height}`} className="plant-art" role="img" aria-label={`Your plant: ${state.label}. ${state.leaves} ${state.leaves===1?'leaf':'leaves'} remaining. ${state.flowers} flowers and ${state.butterflies} butterflies.`}>
      <defs><linearGradient id="pot" x1="0" x2="1"><stop stopColor="#c88465"/><stop offset="1" stopColor="#d99b79"/></linearGradient><linearGradient id="leaf" x2="1" y2="1"><stop stopColor="#6e9b65"/><stop offset="1" stopColor="#38684b"/></linearGradient></defs>
      <ellipse cx="95" cy="176" rx="52" ry="6" fill="#48644a" opacity=".08"/>
      <path d={`M95 144 Q${89+state.droop*10} ${99-height/2} ${93+state.droop*9} ${stemTop}`} fill="none" stroke={state.moisture>20?'#64815a':'#929066'} strokeWidth="3.6" strokeLinecap="round"/>
      {leaves.map((leaf,i)=><g key={i} style={{opacity:i<state.leaves?1:0,transform:`translate(${leaf.x}px,${leaf.y}px) rotate(${leaf.r+(leaf.flip?1:-1)*state.droop*30}deg) scale(${leaf.flip?-1:1},1)`,transformOrigin:'0 0'}} className="plant-leaf"><path d="M0 1 C-3 -22 -31 -27 -34 -18 C-36 -3 -12 12 0 1Z" fill={state.moisture>30?'url(#leaf)':'#a2a174'}/><path d="M-2 0 Q-15 -10 -28 -15" fill="none" stroke="#c4d3a4" strokeWidth=".8" opacity=".65"/></g>)}
      {flowers.slice(0,state.flowers).map((f,i)=><Flower key={i} kind={i} {...f}/>)}
      {[...Array(state.maxLeaves-state.leaves)].map((_,i)=><path key={i} d="M0 0 C-8 -11 -20 -8 -18 -1 C-14 6 -5 6 0 0" transform={`translate(${44+(i*19)%110} ${174+(i%3)*3}) rotate(${i*48-25}) scale(.65)`} fill="#b9a779" opacity=".8"/>)}
      <path d="M67 139 L73 168 Q95 180 117 168 L123 139Z" fill="url(#pot)"/>
      <rect x="64" y="132" width="62" height="13" rx="4" fill="#dca385"/>
      <ellipse cx="95" cy="133" rx="27" ry="4" fill="#8b624b"/>
      <path d="M79 150 V166 M88 151 V169 M99 151 V170 M110 150 V166" stroke="#bd795e" opacity=".3" strokeWidth="1.3"/>
      <g transform={`translate(0 ${-height})`} opacity={state.webs} stroke="#8d9991" strokeWidth=".8" fill="none"><path d="M130 10 L130 85 M130 10 L180 10 M130 10 L170 65 M130 10 L182 38 M130 30 Q140 32 146 29 Q155 27 159 10 M130 47 Q147 49 157 43 Q171 35 175 10 M130 65 Q155 68 170 56 Q182 45 183 24"/><path d="M161 62 v13"/><ellipse cx="161" cy="78" rx="2" ry="3" fill="#7d8a80"/></g>
      {butterflies.slice(0,state.butterflies).map((b,i)=><Butterfly key={i} {...b}/>)}
      <g className="water-drops" transform={`translate(0 ${-height})`} fill="#75a6b5"><path d="M91 9 Q82 21 91 22 Q100 21 91 9"/><path d="M109 30 Q102 39 109 40 Q116 39 109 30"/></g>
    </svg>
  </section>;
}
