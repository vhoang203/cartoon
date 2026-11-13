// Mako — small apricot bear with a sky-blue scarf. Compact, round silhouette.
import React from 'react';
import { C, OUTLINE } from '../palette';
import { CharParams, SPECS } from '../rig';
import { Arm, Brow, Eye, Mouth } from './parts';

const spec = SPECS.mako;

const TORSO =
  'M -98 -6 C -105 -54 -86 -102 -56 -116 C -30 -126 30 -126 56 -116 C 86 -102 105 -54 98 -6 C 66 5 -66 5 -98 -6 Z';
const HEAD = 'M -96 2 C -96 -52 -54 -86 0 -86 C 54 -86 96 -52 96 2 C 96 50 56 80 0 80 C -56 80 -96 50 -96 2 Z';

export const Mako: React.FC<{ p: CharParams; layer: 'body' | 'front'; t: number; armsInFront?: boolean }> = ({
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
        <Arm spec={spec} side="armL" arm={p.armL} fill={C.apricot} pad={C.apricotLight} width={33} pawR={19} />
        {armsInFront ? <Arm spec={spec} side="armR" arm={p.armR} fill={C.apricot} pad={C.apricotLight} width={33} pawR={19} /> : null}
      </g>
    );
  }
  const hc = spec.headC;
  const fx = p.turn * 10;
  const breathe = 1 + Math.sin(t / 16 + 1.3) * 0.008;
  const sway = Math.sin(t / 22) * 3;
  // ears twitch slightly with "earL/earR" (offset from rabbit defaults)
  const earTwL = (p.earL + 10) * 0.35;
  const earTwR = (p.earR - 12) * 0.35;
  return (
    <g transform={root}>
      <ellipse cx={0} cy={2} rx={112} ry={17} fill={C.ink} opacity={0.12} />
      <defs>
        <radialGradient id="mako-fur" cx="45%" cy="32%" r="75%">
          <stop offset="0%" stopColor="#F9C08A" />
          <stop offset="70%" stopColor={C.apricot} />
          <stop offset="100%" stopColor={C.apricotShade} />
        </radialGradient>
        <radialGradient id="mako-head" cx="42%" cy="34%" r="72%">
          <stop offset="0%" stopColor="#FAC796" />
          <stop offset="72%" stopColor={C.apricot} />
          <stop offset="100%" stopColor={C.apricotShade} />
        </radialGradient>
      </defs>
      <g transform={`scale(1 ${breathe})`}>
        <path d={TORSO} fill="url(#mako-fur)" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <ellipse cx={0} cy={-46} rx={56} ry={40} fill={C.apricotLight} />
      </g>
      {[-52, 52].map((x) => (
        <g key={x}>
          <ellipse cx={x} cy={-6} rx={37} ry={19} fill={C.apricot} stroke={C.ink} strokeWidth={OUTLINE} />
          <ellipse cx={x} cy={-4} rx={15} ry={8} fill={C.apricotLight} />
        </g>
      ))}
      {/* scarf: neck band */}
      <path
        d="M -74 -124 C -40 -106 40 -106 74 -124 L 76 -102 C 40 -86 -40 -86 -76 -102 Z"
        fill={C.sky}
        stroke={C.ink}
        strokeWidth={OUTLINE}
        strokeLinejoin="round"
      />
      <path d="M -50 -108 C -20 -98 20 -98 50 -108" stroke={C.skyLight} strokeWidth={5} fill="none" opacity={0.9} />
      {/* scarf: hanging tail with a gentle sway */}
      <g transform={`rotate(${sway} -36 -100)`}>
        <path
          d="M -50 -102 C -60 -82 -64 -62 -60 -40 L -30 -42 C -32 -62 -28 -82 -22 -100 Z"
          fill={C.sky}
          stroke={C.ink}
          strokeWidth={OUTLINE}
          strokeLinejoin="round"
        />
        <path d="M -57 -68 L -29 -70 M -59 -54 L -30 -56" stroke={C.skyLight} strokeWidth={5} />
        <path d="M -56 -40 L -57 -30 M -46 -41 L -46 -31 M -36 -42 L -35 -32" stroke={C.skyDark} strokeWidth={4} strokeLinecap="round" />
      </g>
      <ellipse cx={-36} cy={-102} rx={16} ry={12} fill={C.sky} stroke={C.ink} strokeWidth={OUTLINE} />
      {/* head */}
      <g transform={`rotate(${p.headTilt} ${spec.neck.x} ${spec.neck.y})`}>
        <g transform={`translate(${hc.x} ${hc.y + p.headY})`}>
          {[
            [-70, earTwL],
            [70, earTwR],
          ].map(([x, rot]) => (
            <g key={x} transform={`rotate(${rot} ${x - fx * 0.3} -40)`}>
              <circle cx={x - fx * 0.3} cy={-60} r={31} fill={C.apricot} stroke={C.ink} strokeWidth={OUTLINE} />
              <circle cx={x - fx * 0.3} cy={-58} r={16} fill={C.apricotLight} />
            </g>
          ))}
          <path d={HEAD} fill="url(#mako-head)" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
          <g transform={`translate(${fx} 0)`}>
            <ellipse cx={0} cy={30} rx={44} ry={30} fill={C.apricotLight} />
            <ellipse cx={-60} cy={20} rx={15} ry={9} fill={C.blush} opacity={0.6 * p.blush} />
            <ellipse cx={60} cy={20} rx={15} ry={9} fill={C.blush} opacity={0.6 * p.blush} />
            <Eye x={-36} y={-8} rx={10.5} ry={13.5} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} />
            <Eye x={36} y={-8} rx={10.5} ry={13.5} open={p.eyeOpen} happy={p.happyEyes} lookX={p.lookX} lookY={p.lookY} />
            <Brow x={-36} y={-34} side={-1} browY={p.browY} tilt={p.browTilt} w={13} />
            <Brow x={36} y={-34} side={1} browY={p.browY} tilt={p.browTilt} w={13} />
            <ellipse cx={0} cy={14} rx={14} ry={9.5} fill={C.ink} />
            <ellipse cx={-4} cy={11} rx={4.5} ry={2.6} fill={C.white} opacity={0.7} />
            <Mouth x={0} y={33} open={p.mouthOpen} smile={p.smile} round={p.mouthRound} style="bear" />
          </g>
        </g>
      </g>
      {armsInFront ? null : <Arm spec={spec} side="armR" arm={p.armR} fill={C.apricot} pad={C.apricotLight} width={33} pawR={19} />}
    </g>
  );
};
