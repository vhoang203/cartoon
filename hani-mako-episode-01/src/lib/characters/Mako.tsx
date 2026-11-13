// Mako — little boy, adapted to 2D cutout from the owner's character sheet:
// dark curly mop of hair, big dark-brown eyes, mint henley T-shirt with a
// pocket, navy suspenders with brass clips, cream cuffed shorts, blue clogs.
// Rig mapping: earL/earR -> gentle bounce of the curls.
import React from 'react';
import { C, OUTLINE } from '../palette';
import { CharParams, SPECS } from '../rig';
import { Arm, Brow, Eye, Mouth } from './parts';

const spec = SPECS.mako;

const SHIRT =
  'M -88 -54 C -92 -82 -82 -106 -56 -116 C -30 -124 30 -124 56 -116 C 82 -106 92 -82 88 -54 C 60 -46 -60 -46 -88 -54 Z';
const SHORTS = 'M -98 -8 C -102 -36 -96 -54 -88 -62 L 88 -62 C 96 -54 102 -36 98 -8 C 64 2 -64 2 -98 -8 Z';
const HEAD = 'M -90 0 C -91 -52 -50 -82 0 -82 C 50 -82 91 -52 90 0 C 89 48 52 76 0 76 C -52 76 -89 48 -90 0 Z';
const FRINGE =
  'M -92 -14 C -98 -78 -44 -104 0 -102 C 44 -104 98 -78 92 -14 C 86 -34 76 -46 62 -50 C 56 -62 40 -66 28 -58 C 18 -70 0 -70 -8 -60 C -18 -70 -38 -66 -44 -54 C -60 -56 -76 -44 -80 -28 C -84 -24 -88 -20 -92 -14 Z';
const FRINGE_EDGE =
  'M 92 -14 C 86 -34 76 -46 62 -50 C 56 -62 40 -66 28 -58 C 18 -70 0 -70 -8 -60 C -18 -70 -38 -66 -44 -54 C -60 -56 -76 -44 -80 -28 C -84 -24 -88 -20 -92 -14';
// curl bumps for the mop (cx, cy, r)
const MOP: [number, number, number][] = [
  [-88, -40, 27], [-74, -78, 32], [-44, -106, 35], [-6, -120, 36], [34, -114, 35], [66, -92, 33], [88, -58, 29], [94, -24, 22], [-94, -10, 20],
];

export const Mako: React.FC<{ p: CharParams; layer: 'body' | 'front'; t: number; armsInFront?: boolean }> = ({
  p,
  layer,
  t,
  armsInFront = false,
}) => {
  const sx = 1 + (1 - p.squash) * 0.6;
  const root = `translate(${p.x} ${p.y + p.hop}) rotate(${p.lean}) scale(${sx} ${p.squash})`;
  const arm = (side: 'armL' | 'armR') => (
    <Arm spec={spec} side={side} arm={p[side]} fill={C.skin} width={28} pawR={16} sleeve={C.mint} sleeveT={0.26} />
  );
  if (layer === 'front') {
    return (
      <g transform={root}>
        {arm('armL')}
        {armsInFront ? arm('armR') : null}
      </g>
    );
  }
  const hc = spec.headC;
  const fx = p.turn * 10;
  const breathe = 1 + Math.sin(t / 16 + 1.3) * 0.008;
  const bounce = (p.earL + 10) * 0.3 + Math.sin(t / 21) * 0.8;
  return (
    <g transform={root}>
      <ellipse cx={0} cy={2} rx={112} ry={17} fill={C.ink} opacity={0.12} />
      <g transform={`scale(1 ${breathe})`}>
        {/* shorts */}
        <path d={SHORTS} fill={C.shorts} stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <path d="M -94 -20 C -64 -12 -20 -12 -6 -16 M 6 -16 C 20 -12 64 -12 94 -20" stroke={C.shortsShade} strokeWidth={5} fill="none" />
        <path d="M 0 -60 L 0 -14" stroke={C.shortsShade} strokeWidth={3} />
        {/* shirt */}
        <rect x={-10} y={-134} width={20} height={20} fill={C.skin} />
        <path d={SHIRT} fill={C.mint} stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <path d="M -24 -121 Q 0 -108 24 -121" stroke={C.mintDark} strokeWidth={5} fill="none" strokeLinecap="round" />
        <path d="M 0 -112 L 0 -86" stroke={C.mintDark} strokeWidth={3.5} />
        {[-106, -97, -88].map((y) => (
          <circle key={y} cx={5} cy={y} r={3.2} fill={C.shorts} stroke={C.inkSoft} strokeWidth={1.2} />
        ))}
        <rect x={-58} y={-104} width={24} height={20} rx={4} fill="none" stroke={C.mintDark} strokeWidth={3.5} />
        {/* suspenders */}
        {[-1, 1].map((s) => (
          <g key={s}>
            <path d={`M ${s * 34} -58 L ${s * 46} -120`} stroke={C.ink} strokeWidth={17} strokeLinecap="round" />
            <path d={`M ${s * 34} -58 L ${s * 46} -120`} stroke={C.navy} strokeWidth={11} strokeLinecap="round" />
            <rect x={s * 34 - 8} y={-70} width={16} height={11} rx={2} fill={C.brass} stroke={C.ink} strokeWidth={2.5} />
          </g>
        ))}
      </g>
      {/* blue clogs */}
      {[-48, 48].map((x) => (
        <g key={x}>
          <ellipse cx={x} cy={-6} rx={33} ry={18} fill={C.clog} stroke={C.ink} strokeWidth={OUTLINE} />
          {[-12, 0, 12].map((d) => (
            <circle key={d} cx={x + d} cy={-10} r={2.8} fill={C.clogDark} />
          ))}
        </g>
      ))}
      {/* head */}
      <g transform={`rotate(${p.headTilt} ${spec.neck.x} ${spec.neck.y})`}>
        <g transform={`translate(${hc.x} ${hc.y + p.headY})`}>
          <g transform={`rotate(${bounce} 0 -40)`}>
            <g stroke={C.ink} strokeWidth={OUTLINE} fill={C.hair}>
              {MOP.map(([x, y, r], i) => (
                <circle key={i} cx={x} cy={y} r={r} />
              ))}
            </g>
            <g fill={C.hair}>
              {MOP.map(([x, y, r], i) => (
                <circle key={i} cx={x} cy={y} r={r - 5} />
              ))}
            </g>
            <ellipse cx={0} cy={-46} rx={96} ry={70} fill={C.hair} />
            <path d="M -60 -96 q 12 -12 26 -2 M -14 -116 q 12 -12 26 -2 M 30 -104 q 12 -10 24 2 M 62 -78 q 10 -8 18 4 M -84 -56 q 8 -10 18 -2" stroke={C.hairLight} strokeWidth={4.5} fill="none" strokeLinecap="round" />
          </g>
          {[-1, 1].map((s) => (
            <ellipse key={s} cx={s * 88 - fx * 0.3} cy={8} rx={13} ry={17} fill={C.skin} stroke={C.ink} strokeWidth={OUTLINE} />
          ))}
          <defs>
            <radialGradient id="mako-skin" cx="45%" cy="38%" r="72%">
              <stop offset="0%" stopColor={C.skinLight} />
              <stop offset="75%" stopColor={C.skin} />
              <stop offset="100%" stopColor={C.skinShade} />
            </radialGradient>
          </defs>
          <path d={HEAD} fill="url(#mako-skin)" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
          <g transform={`translate(${fx} 0)`}>
            <ellipse cx={-54} cy={24} rx={15} ry={9} fill={C.blush} opacity={0.55 * p.blush} />
            <ellipse cx={54} cy={24} rx={15} ry={9} fill={C.blush} opacity={0.55 * p.blush} />
            <Eye x={-33} y={0} rx={12.5} ry={15.5} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} iris={C.eye} />
            <Eye x={33} y={0} rx={12.5} ry={15.5} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} iris={C.eye} />
            <Brow x={-33} y={-30} side={-1} browY={p.browY} tilt={p.browTilt} w={12} />
            <Brow x={33} y={-30} side={1} browY={p.browY} tilt={p.browTilt} w={12} />
            <path d="M -7 18 Q 0 24 7 18" stroke={C.skinShade} strokeWidth={4} strokeLinecap="round" fill="none" />
            <Mouth x={0} y={37} open={p.mouthOpen} smile={p.smile} round={p.mouthRound} style="kid" />
          </g>
          <g transform={`translate(${fx * 0.5} 0)`}>
            <path d={FRINGE} fill={C.hair} />
            <path d={FRINGE_EDGE} fill="none" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" strokeLinecap="round" />
          </g>
          <path d="M -50 -80 q 10 -10 22 -2 M 10 -86 q 12 -10 24 0 M 50 -66 q 8 -8 16 2" stroke={C.hairLight} strokeWidth={4} fill="none" strokeLinecap="round" />
        </g>
      </g>
      {armsInFront ? null : arm('armR')}
    </g>
  );
};
