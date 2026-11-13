import React from 'react';
import { C, OUTLINE } from '../palette';

export const BERRY_W = 46;
export const BERRY_H = 50;

const BERRY =
  'M 0 25 C -15 22 -25 6 -24 -8 C -23 -20 -12 -24 0 -21 C 12 -24 23 -20 24 -8 C 25 6 15 22 0 25 Z';
const SEEDS: [number, number][] = [
  [-11, -9],
  [0, -11],
  [11, -9],
  [-14, 3],
  [-3, 1],
  [8, 2],
  [-6, 12],
  [5, 13],
  [15, -1],
];

/** One strawberry, centred on (0,0). `glow` 0..1 shows the counting highlight. */
export const Strawberry: React.FC<{ x: number; y: number; scale?: number; rot?: number; glow?: number }> = ({
  x,
  y,
  scale = 1,
  rot = 0,
  glow = 0,
}) => (
  <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${scale})`}>
    {glow > 0 ? <circle cx={0} cy={0} r={40} fill="#FFF3A6" opacity={0.85 * glow} /> : null}
    {glow > 0 ? <circle cx={0} cy={0} r={40} fill="none" stroke="#FFC94D" strokeWidth={5} opacity={glow} /> : null}
    <defs>
      <radialGradient id="berry-g" cx="38%" cy="35%" r="70%">
        <stop offset="0%" stopColor={C.coralLight} />
        <stop offset="55%" stopColor={C.coral} />
        <stop offset="100%" stopColor={C.coralDark} />
      </radialGradient>
    </defs>
    <path d={BERRY} fill="url(#berry-g)" stroke={C.ink} strokeWidth={3.5} strokeLinejoin="round" />
    {SEEDS.map(([sx, sy], i) => (
      <ellipse key={i} cx={sx} cy={sy} rx={1.8} ry={2.6} fill="#FFE9A8" />
    ))}
    <ellipse cx={-10} cy={-8} rx={5} ry={8} fill={C.white} opacity={0.35} transform="rotate(25 -10 -8)" />
    <path
      d="M 0 -18 L -15 -24 L -6 -26 L -10 -34 L 0 -27 L 10 -34 L 6 -26 L 15 -24 Z"
      fill={C.leaf}
      stroke={C.ink}
      strokeWidth={3}
      strokeLinejoin="round"
    />
    <path d="M 0 -28 Q 1 -34 4 -37" stroke={C.leafDark} strokeWidth={4} strokeLinecap="round" fill="none" />
  </g>
);

export const Plate: React.FC<{ x: number; y: number; rim: string; rimDark: string }> = ({ x, y, rim, rimDark }) => (
  <g transform={`translate(${x} ${y})`}>
    <ellipse cx={0} cy={9} rx={106} ry={32} fill={C.ink} opacity={0.13} />
    <ellipse cx={0} cy={0} rx={102} ry={35} fill={rim} stroke={C.ink} strokeWidth={OUTLINE} />
    <ellipse cx={0} cy={1} rx={80} ry={25} fill={C.creamLight} stroke={rimDark} strokeWidth={3} />
    <ellipse cx={-30} cy={-14} rx={24} ry={5} fill={C.white} opacity={0.5} />
  </g>
);

// Bowl is split so strawberries can sit "inside" it: back (interior) then
// berries, then the front wall.
export const BOWL_RX = 158;
export const BOWL_RY = 30;
export const BowlBack: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <g transform={`translate(${x} ${y})`}>
    <ellipse cx={0} cy={58} rx={150} ry={18} fill={C.ink} opacity={0.12} />
    <ellipse cx={0} cy={0} rx={BOWL_RX} ry={BOWL_RY} fill="#EED9B8" stroke={C.ink} strokeWidth={OUTLINE} />
    <ellipse cx={0} cy={6} rx={BOWL_RX - 14} ry={BOWL_RY - 9} fill="#E6CDA6" />
  </g>
);
export const BowlFront: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <g transform={`translate(${x} ${y})`}>
    <defs>
      <linearGradient id="bowl-g" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stopColor={C.creamLight} />
        <stop offset="100%" stopColor={C.creamShade} />
      </linearGradient>
    </defs>
    <path
      d={`M ${-BOWL_RX} 0 C ${-BOWL_RX + 6} 40 -104 58 0 58 C 104 58 ${BOWL_RX - 6} 40 ${BOWL_RX} 0 A ${BOWL_RX} ${BOWL_RY} 0 0 1 ${-BOWL_RX} 0 Z`}
      fill="url(#bowl-g)"
      stroke={C.ink}
      strokeWidth={OUTLINE}
      strokeLinejoin="round"
    />
    <path d={`M ${-BOWL_RX + 10} 22 C -90 50 90 50 ${BOWL_RX - 10} 22`} stroke={C.apricot} strokeWidth={9} fill="none" />
    <path d={`M ${-BOWL_RX + 22} 36 C -80 56 80 56 ${BOWL_RX - 22} 36`} stroke={C.apricotLight} strokeWidth={4} fill="none" />
  </g>
);

/** Round number badge used for plate totals and per-strawberry counting tags. */
export const NumberBadge: React.FC<{
  x: number;
  y: number;
  n: number;
  r?: number;
  ring: string;
  scale?: number;
  opacity?: number;
  fill?: string;
}> = ({ x, y, n, r = 34, ring, scale = 1, opacity = 1, fill = C.white }) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`} opacity={opacity}>
    <circle cx={0} cy={3} r={r + 2} fill={C.ink} opacity={0.18} />
    <circle cx={0} cy={0} r={r} fill={fill} stroke={ring} strokeWidth={r * 0.2} />
    <circle cx={0} cy={0} r={r + r * 0.1} fill="none" stroke={C.ink} strokeWidth={3} />
    <text
      x={0}
      y={r * 0.42}
      textAnchor="middle"
      fontFamily="Nunito"
      fontWeight={900}
      fontSize={r * 1.3}
      fill={C.ink}
    >
      {n}
    </text>
  </g>
);

export const ThoughtBubble: React.FC<{ x: number; y: number; scale: number; opacity: number; tail: -1 | 1 }> = ({
  x,
  y,
  scale,
  opacity,
  tail,
}) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`} opacity={opacity}>
    <circle cx={tail * -34} cy={52} r={7} fill={C.white} stroke={C.ink} strokeWidth={3} />
    <circle cx={tail * -20} cy={36} r={10} fill={C.white} stroke={C.ink} strokeWidth={3} />
    <ellipse cx={0} cy={0} rx={38} ry={32} fill={C.white} stroke={C.ink} strokeWidth={4} />
    <text x={0} y={16} textAnchor="middle" fontFamily="Nunito" fontWeight={900} fontSize={46} fill={C.skyDark}>
      ?
    </text>
  </g>
);
