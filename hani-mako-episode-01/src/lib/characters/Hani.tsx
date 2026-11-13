// Hani — small cream rabbit in teal overalls. Signature: long ears, the
// right ear tip folds outward. Rendered in two layers so the arm toward the
// partner can pass in front of props.
import React from 'react';
import { C, OUTLINE } from '../palette';
import { CharParams, SPECS } from '../rig';
import { Arm, Brow, Eye, Mouth } from './parts';

const spec = SPECS.hani;

const TORSO =
  'M -86 -6 C -93 -50 -80 -110 -52 -126 C -30 -137 30 -137 52 -126 C 80 -110 93 -50 86 -6 C 58 5 -58 5 -86 -6 Z';
const HEAD = 'M -90 2 C -91 -48 -50 -80 0 -80 C 50 -80 91 -48 90 2 C 89 46 52 74 0 74 C -52 74 -89 46 -90 2 Z';
const EAR1 = 'M -22 4 C -27 -38 -23 -70 -16 -84 L 16 -84 C 23 -70 27 -38 22 4 Z';
const EAR1_IN = 'M -11 -4 C -14 -38 -11 -64 -8 -78 L 8 -78 C 11 -64 14 -38 11 -4 Z';
const EAR2 = 'M -16 2 C -20 -28 -13 -60 0 -70 C 13 -60 20 -28 16 2 Z';
const EAR2_IN = 'M -8 0 C -10 -26 -6 -50 0 -58 C 6 -50 10 -26 8 0 Z';

const Ear: React.FC<{ x: number; y: number; angle: number; fold: number }> = ({ x, y, angle, fold }) => (
  <g transform={`translate(${x} ${y}) rotate(${angle})`}>
    {/* outline underlay for both segments */}
    <g stroke={C.ink} strokeWidth={OUTLINE * 2} strokeLinejoin="round" fill={C.ink}>
      <path d={EAR1} />
      <g transform={`translate(0 -80) rotate(${fold})`}>
        <path d={EAR2} />
      </g>
    </g>
    <path d={EAR1} fill={C.cream} />
    <g transform={`translate(0 -80) rotate(${fold})`}>
      <path d={EAR2} fill={C.cream} />
      <path d={EAR2_IN} fill={C.pink} opacity={0.85} />
    </g>
    <path d={EAR1_IN} fill={C.pink} opacity={0.85} />
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
  if (layer === 'front') {
    return (
      <g transform={root}>
        {armsInFront ? <Arm spec={spec} side="armL" arm={p.armL} fill={C.cream} pad={C.pink} /> : null}
        <Arm spec={spec} side="armR" arm={p.armR} fill={C.cream} pad={C.pink} />
      </g>
    );
  }
  const hc = spec.headC;
  const fx = p.turn * 10;
  const breathe = 1 + Math.sin(t / 14) * 0.008;
  return (
    <g transform={root}>
      <ellipse cx={0} cy={2} rx={104} ry={16} fill={C.ink} opacity={0.12} />
      {/* torso + overalls */}
      <g transform={`scale(1 ${breathe})`}>
        <defs>
          <clipPath id="hani-torso-clip">
            <path d={TORSO} />
          </clipPath>
          <radialGradient id="hani-fur" cx="45%" cy="35%" r="75%">
            <stop offset="0%" stopColor={C.creamLight} />
            <stop offset="70%" stopColor={C.cream} />
            <stop offset="100%" stopColor={C.creamShade} />
          </radialGradient>
        </defs>
        <path d={TORSO} fill="url(#hani-fur)" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <g clipPath="url(#hani-torso-clip)">
          <path d="M -100 -66 L 100 -66 L 100 10 L -100 10 Z" fill={C.teal} />
          <rect x={-40} y={-114} width={80} height={52} rx={12} fill={C.teal} />
          <path d="M -36 -110 L -54 -132 M 36 -110 L 54 -132" stroke={C.teal} strokeWidth={16} strokeLinecap="round" />
          <path d="M -100 -66 L 100 -66" stroke={C.tealDark} strokeWidth={3} opacity={0.5} />
          <rect x={-17} y={-98} width={34} height={22} rx={6} fill="none" stroke={C.tealDark} strokeWidth={3} />
          <path d="M 0 -6 L 0 -40" stroke={C.tealDark} strokeWidth={3} opacity={0.55} />
          <ellipse cx={0} cy={-2} rx={90} ry={14} fill={C.tealDark} opacity={0.25} />
        </g>
        <path d={TORSO} fill="none" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <circle cx={-30} cy={-104} r={6.5} fill={C.sun} stroke={C.ink} strokeWidth={3} />
        <circle cx={30} cy={-104} r={6.5} fill={C.sun} stroke={C.ink} strokeWidth={3} />
      </g>
      {/* feet */}
      {[-44, 44].map((fxp) => (
        <g key={fxp}>
          <ellipse cx={fxp} cy={-6} rx={33} ry={18} fill={C.cream} stroke={C.ink} strokeWidth={OUTLINE} />
          <ellipse cx={fxp} cy={-4} rx={12} ry={7} fill={C.pink} opacity={0.75} />
        </g>
      ))}
      {/* head */}
      <g transform={`rotate(${p.headTilt} ${spec.neck.x} ${spec.neck.y})`}>
        <g transform={`translate(${hc.x} ${hc.y + p.headY})`}>
          <Ear x={-32 - fx * 0.4} y={-62} angle={p.earL} fold={6 + (p.earL + 10) * 0.3} />
          <Ear x={32 - fx * 0.4} y={-62} angle={p.earR} fold={p.earFold} />
          <defs>
            <radialGradient id="hani-head" cx="42%" cy="35%" r="72%">
              <stop offset="0%" stopColor={C.creamLight} />
              <stop offset="72%" stopColor={C.cream} />
              <stop offset="100%" stopColor={C.creamShade} />
            </radialGradient>
          </defs>
          <path d={HEAD} fill="url(#hani-head)" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
          <g transform={`translate(${fx} 0)`}>
            <ellipse cx={0} cy={28} rx={33} ry={21} fill={C.creamLight} />
            <ellipse cx={-52} cy={20} rx={15} ry={9} fill={C.blush} opacity={0.55 * p.blush} />
            <ellipse cx={52} cy={20} rx={15} ry={9} fill={C.blush} opacity={0.55 * p.blush} />
            <Eye x={-33} y={-8} rx={12} ry={16} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} />
            <Eye x={33} y={-8} rx={12} ry={16} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} />
            <Brow x={-33} y={-36} side={-1} browY={p.browY} tilt={p.browTilt} />
            <Brow x={33} y={-36} side={1} browY={p.browY} tilt={p.browTilt} />
            <path
              d="M -9 12 Q 0 8 9 12 Q 5 22 0 23 Q -5 22 -9 12 Z"
              fill="#F08A9A"
              stroke={C.ink}
              strokeWidth={3}
              strokeLinejoin="round"
            />
            <Mouth x={0} y={33} open={p.mouthOpen} smile={p.smile} round={p.mouthRound} style="bunny" />
          </g>
        </g>
      </g>
      {/* outer (screen-left) arm in front of the body */}
      {armsInFront ? null : <Arm spec={spec} side="armL" arm={p.armL} fill={C.cream} pad={C.pink} />}
    </g>
  );
};
