// Hani — little girl, adapted to 2D cutout from the owner's character sheet:
// very curly dark hair in a high bun with a blue hair tie, loose curls framing
// the face, big dark-brown eyes, sky-blue tulle dress (original details: pearl
// collar, small star brooch, puff sleeves, no gloves), pink shoes.
// Rig mapping: earL -> bun sway, earR -> side-curl sway, earFold -> loose
// forehead curl (48 = tucked at the side, 150 = fallen over the eye).
import React from 'react';
import { clamp, lerp } from '../anim';
import { C, OUTLINE } from '../palette';
import { CharParams, SPECS } from '../rig';
import { Arm, Brow, Eye, Mouth } from './parts';

const spec = SPECS.hani;

const SKIRT =
  'M -122 -4 C -126 -40 -96 -74 -56 -82 L 56 -82 C 96 -74 126 -40 122 -4 C 84 9 -84 9 -122 -4 Z';
const BODICE = 'M -50 -78 C -56 -98 -55 -112 -44 -124 C -20 -132 20 -132 44 -124 C 55 -112 56 -98 50 -78 Z';
const HEAD = 'M -84 0 C -85 -50 -46 -80 0 -80 C 46 -80 85 -50 84 0 C 83 46 48 74 0 74 C -48 74 -83 46 -84 0 Z';
const FRINGE =
  'M -86 -22 C -92 -78 -42 -98 0 -96 C 42 -98 92 -78 86 -22 C 80 -42 70 -56 54 -60 C 44 -72 26 -74 14 -66 C 4 -74 -14 -74 -24 -66 C -36 -74 -54 -70 -60 -58 C -74 -54 -82 -40 -86 -22 Z';
const FRINGE_EDGE =
  'M 86 -22 C 80 -42 70 -56 54 -60 C 44 -72 26 -74 14 -66 C 4 -74 -14 -74 -24 -66 C -36 -74 -54 -70 -60 -58 C -74 -54 -82 -40 -86 -22';
const SPARKLES: [number, number][] = [
  [-90, -22], [-62, -40], [-30, -14], [4, -36], [34, -18], [66, -42], [92, -20], [-48, -64], [48, -62], [-8, -66],
];
const PEARLS = Array.from({ length: 9 }, (_, i) => {
  const t = i / 8;
  return { x: lerp(-28, 28, t), y: -126 + Math.sin(t * Math.PI) * 9 };
});

const Curl: React.FC<{ d: string; w?: number }> = ({ d, w = 8 }) => (
  <g fill="none" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} stroke={C.ink} strokeWidth={w + 5} />
    <path d={d} stroke={C.hair} strokeWidth={w} />
  </g>
);

export const Hani: React.FC<{ p: CharParams; layer: 'body' | 'front'; t: number; armsInFront?: boolean }> = ({
  p,
  layer,
  t,
  armsInFront = false,
}) => {
  const sx = 1 + (1 - p.squash) * 0.6;
  const root = `translate(${p.x} ${p.y + p.hop}) rotate(${p.lean}) scale(${sx} ${p.squash})`;
  const arm = (side: 'armL' | 'armR') => (
    <Arm spec={spec} side={side} arm={p[side]} fill={C.skin} width={26} pawR={15} sleeve={C.dressLight} sleeveT={0.24} />
  );
  if (layer === 'front') {
    return (
      <g transform={root}>
        {armsInFront ? arm('armL') : null}
        {arm('armR')}
      </g>
    );
  }
  const hc = spec.headC;
  const fx = p.turn * 10;
  const breathe = 1 + Math.sin(t / 14) * 0.008;
  const bunRot = (p.earL + 10) * 0.55;
  const sideSway = (p.earR - 12) * 0.35 + Math.sin(t / 19) * 1.2;
  const lockT = clamp((p.earFold - 48) / 102, 0, 1);
  // loose curl: tucked by the left temple -> hanging over the left eye
  const lock = { x: lerp(-58, -36, lockT), y: lerp(-66, -32, lockT), r: lerp(-60, 0, lockT) };
  return (
    <g transform={root}>
      <ellipse cx={0} cy={2} rx={122} ry={16} fill={C.ink} opacity={0.12} />
      {/* shoes peeking out under the skirt */}
      {[-40, 40].map((x) => (
        <g key={x}>
          <ellipse cx={x} cy={-4} rx={27} ry={14} fill={C.shoePink} stroke={C.ink} strokeWidth={OUTLINE} />
          <path d={`M ${x - 14} -12 Q ${x} -18 ${x + 14} -12`} stroke={C.shoePinkDark} strokeWidth={4} fill="none" strokeLinecap="round" />
        </g>
      ))}
      <g transform={`scale(1 ${breathe})`}>
        {/* tulle skirt, spread while sitting */}
        <path d={SKIRT} fill={C.dress} stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <path
          d="M -112 -10 C -110 -38 -86 -64 -54 -72 L 54 -72 C 86 -64 110 -38 112 -10 C 76 0 -76 0 -112 -10 Z"
          fill={C.dressLight}
          opacity={0.45}
        />
        <path d="M -116 -8 C -78 6 78 6 116 -8" stroke={C.white} strokeWidth={4} opacity={0.55} fill="none" />
        {SPARKLES.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.6} fill={C.white} opacity={0.85} />
        ))}
        {/* bodice + waistband + pearl collar + star brooch */}
        <rect x={-10} y={-138} width={20} height={20} fill={C.skin} />
        <path d={BODICE} fill={C.dressDark} stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <path d="M -32 -126 Q 0 -112 32 -126 L 30 -131 Q 0 -122 -30 -131 Z" fill={C.skin} />
        <rect x={-56} y={-86} width={112} height={11} rx={5} fill="#EEF6FC" stroke={C.ink} strokeWidth={3} />
        {[-40, -20, 0, 20, 40].map((x) => (
          <circle key={x} cx={x} cy={-80.5} r={2.4} fill={C.dressDark} />
        ))}
        {PEARLS.map((q, i) => (
          <circle key={i} cx={q.x} cy={q.y} r={3.4} fill={C.white} stroke={C.inkSoft} strokeWidth={1.2} />
        ))}
        <path
          d="M 0 -112 L 3.5 -104.5 L 11.5 -104 L 5.5 -98.5 L 7.5 -90.5 L 0 -95 L -7.5 -90.5 L -5.5 -98.5 L -11.5 -104 L -3.5 -104.5 Z"
          fill="#FFF6D2"
          stroke={C.ink}
          strokeWidth={2.4}
          strokeLinejoin="round"
        />
      </g>
      {/* head */}
      <g transform={`rotate(${p.headTilt} ${spec.neck.x} ${spec.neck.y})`}>
        <g transform={`translate(${hc.x} ${hc.y + p.headY})`}>
          {/* bun with blue hair tie */}
          <g transform={`rotate(${bunRot} 0 -78) translate(0 -78) scale(1.38) translate(0 78)`}>
            <g stroke={C.ink} strokeWidth={OUTLINE} fill={C.hair}>
              <circle cx={-26} cy={-112} r={26} />
              <circle cx={24} cy={-114} r={27} />
              <circle cx={0} cy={-134} r={28} />
              <circle cx={-6} cy={-100} r={24} />
              <circle cx={14} cy={-96} r={22} />
            </g>
            <g fill={C.hair}>
              <circle cx={-26} cy={-112} r={21} />
              <circle cx={24} cy={-114} r={22} />
              <circle cx={0} cy={-134} r={23} />
              <circle cx={-6} cy={-100} r={20} />
              <circle cx={14} cy={-96} r={18} />
            </g>
            <path d="M -18 -126 q 8 -8 14 0 M 8 -112 q 8 -8 14 0 M -30 -104 q 6 -6 12 0" stroke={C.hairLight} strokeWidth={4} fill="none" strokeLinecap="round" />
            <rect x={-22} y={-86} width={44} height={13} rx={6} fill={C.hairTie} stroke={C.ink} strokeWidth={3.5} />
          </g>
          {/* back hair mass */}
          <ellipse cx={0} cy={-22} rx={92} ry={74} fill={C.hair} stroke={C.ink} strokeWidth={OUTLINE} />
          {/* side curls */}
          <g transform={`rotate(${sideSway} -84 -10)`}>
            <Curl d="M -86 -12 c -12 10 4 20 -6 30 c -10 10 6 18 -2 28" />
          </g>
          <g transform={`rotate(${-sideSway} 84 -10)`}>
            <Curl d="M 86 -12 c 12 10 -4 20 6 30 c 10 10 -6 18 2 28" />
          </g>
          {/* ears */}
          {[-1, 1].map((s) => (
            <ellipse key={s} cx={s * 82 - fx * 0.3} cy={6} rx={12} ry={16} fill={C.skin} stroke={C.ink} strokeWidth={OUTLINE} />
          ))}
          <defs>
            <radialGradient id="hani-skin" cx="45%" cy="38%" r="72%">
              <stop offset="0%" stopColor={C.skinLight} />
              <stop offset="75%" stopColor={C.skin} />
              <stop offset="100%" stopColor={C.skinShade} />
            </radialGradient>
          </defs>
          <path d={HEAD} fill="url(#hani-skin)" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
          <g transform={`translate(${fx} 0)`}>
            <ellipse cx={-50} cy={22} rx={15} ry={9} fill={C.blush} opacity={0.6 * p.blush} />
            <ellipse cx={50} cy={22} rx={15} ry={9} fill={C.blush} opacity={0.6 * p.blush} />
            <Eye x={-31} y={-2} rx={13} ry={16.5} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} iris={C.eye} lashes={-1} />
            <Eye x={31} y={-2} rx={13} ry={16.5} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} iris={C.eye} lashes={1} />
            <Brow x={-31} y={-32} side={-1} browY={p.browY} tilt={p.browTilt} w={11} />
            <Brow x={31} y={-32} side={1} browY={p.browY} tilt={p.browTilt} w={11} />
            <path d="M -6 16 Q 0 21 6 16" stroke={C.skinShade} strokeWidth={4} strokeLinecap="round" fill="none" />
            <Mouth x={0} y={34} open={p.mouthOpen} smile={p.smile} round={p.mouthRound} style="kid" />
          </g>
          {/* curly fringe */}
          <g transform={`translate(${fx * 0.5} 0)`}>
            <path d={FRINGE} fill={C.hair} />
            <path d={FRINGE_EDGE} fill="none" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" strokeLinecap="round" />
          </g>
          <path d="M -40 -82 q 10 -8 20 0 M 14 -84 q 10 -8 20 0" stroke={C.hairLight} strokeWidth={4} fill="none" strokeLinecap="round" />
          {/* the loose curl that loves to fall over Hani's eye */}
          <g transform={`translate(${lock.x + fx * 0.6} ${lock.y}) rotate(${lock.r})`}>
            <Curl d="M 0 0 c 12 8 14 24 2 30 c -10 5 -16 -6 -8 -12" w={7} />
          </g>
        </g>
      </g>
      {armsInFront ? null : arm('armL')}
    </g>
  );
};
