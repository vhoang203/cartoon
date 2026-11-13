// Garden picnic environment (world space 1920 x 1300). Calm, low-saturation
// background; nothing red or round-and-small that could be mistaken for a
// strawberry.
import React from 'react';
import { C, OUTLINE } from '../palette';

const Cloud: React.FC<{ x: number; y: number; s: number }> = ({ x, y, s }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} opacity={0.92}>
    <path
      d="M -90 20 C -110 20 -112 -8 -88 -10 C -86 -36 -50 -44 -34 -24 C -24 -52 26 -52 34 -22 C 50 -40 92 -30 86 -4 C 110 -2 110 20 88 20 Z"
      fill={C.white}
    />
  </g>
);

export const Garden: React.FC<{ t: number }> = ({ t }) => {
  const drift = (t * 0.12) % 2400;
  return (
    <g>
      <defs>
        <linearGradient id="sky-g" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#A9DDF3" />
          <stop offset="70%" stopColor="#DDF2F7" />
          <stop offset="100%" stopColor="#EEF8EC" />
        </linearGradient>
        <linearGradient id="grass-g" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={C.grass} />
          <stop offset="100%" stopColor={C.grassDark} />
        </linearGradient>
        <pattern id="gingham" width="56" height="56" patternUnits="userSpaceOnUse">
          <rect width="56" height="56" fill="#FFF7EA" />
          <rect width="28" height="56" fill="#F7D6B5" opacity={0.45} />
          <rect width="56" height="28" fill="#F7D6B5" opacity={0.45} />
        </pattern>
      </defs>
      <rect x={-400} y={-200} width={2720} height={1700} fill="url(#sky-g)" />
      {/* soft sun */}
      <circle cx={1660} cy={150} r={110} fill={C.sun} opacity={0.35} />
      <circle cx={1660} cy={150} r={70} fill="#FFF1B8" opacity={0.9} />
      <Cloud x={((300 + drift) % 2400) - 240} y={150} s={1.2} />
      <Cloud x={((1100 + drift * 0.8) % 2400) - 240} y={260} s={0.9} />
      <Cloud x={((1800 + drift * 0.6) % 2400) - 240} y={110} s={0.75} />
      {/* distant hills */}
      <path d="M -400 520 C 100 400 500 420 900 480 C 1300 540 1600 410 2320 470 L 2320 800 L -400 800 Z" fill={C.grassFar} />
      <path d="M -400 600 C 300 520 700 560 1100 590 C 1500 620 1800 540 2320 580 L 2320 900 L -400 900 Z" fill="#B9DFA2" />
      {/* tree on the left */}
      <g>
        <path d="M 150 640 C 160 560 150 470 170 400 L 220 400 C 230 470 226 560 240 640 Z" fill="#B98A5E" stroke={C.ink} strokeWidth={OUTLINE} strokeLinejoin="round" />
        <path d="M 196 470 C 230 450 250 430 262 410" stroke="#9C7048" strokeWidth={10} strokeLinecap="round" fill="none" />
        <g stroke={C.ink} strokeWidth={OUTLINE} fill="#8CCB7E">
          <circle cx={110} cy={330} r={95} />
          <circle cx={290} cy={320} r={100} />
          <circle cx={200} cy={240} r={115} />
        </g>
        <circle cx={160} cy={220} r={40} fill="#A6DA98" opacity={0.6} />
      </g>
      {/* bushes on the right */}
      <g stroke={C.ink} strokeWidth={OUTLINE} fill="#93CF83">
        <circle cx={1700} cy={600} r={70} />
        <circle cx={1800} cy={580} r={86} />
        <circle cx={1900} cy={610} r={70} />
      </g>
      {/* lawn */}
      <path d="M -400 640 C 400 610 1500 610 2320 640 L 2320 1500 L -400 1500 Z" fill="url(#grass-g)" />
      {/* a few tufts and pale daisies, kept far from the picnic area */}
      {[
        [90, 760],
        [330, 700],
        [1640, 720],
        [1830, 780],
        [60, 1010],
        [1870, 1020],
      ].map(([x, y], i) => (
        <g key={i} transform={`translate(${x} ${y})`}>
          <path d="M -14 0 Q -10 -18 -4 -24 M 0 0 Q 2 -22 4 -30 M 12 0 Q 12 -16 18 -22" stroke={C.grassDark} strokeWidth={5} strokeLinecap="round" fill="none" />
        </g>
      ))}
      {[
        [260, 760],
        [1700, 760],
        [1760, 860],
        [140, 900],
      ].map(([x, y], i) => (
        <g key={i} transform={`translate(${x} ${y})`}>
          {[0, 72, 144, 216, 288].map((a) => (
            <ellipse key={a} cx={0} cy={-9} rx={5} ry={9} fill={C.white} transform={`rotate(${a})`} />
          ))}
          <circle r={5} fill={C.sun} />
        </g>
      ))}
      {/* picnic blanket */}
      <path
        d="M 470 772 Q 960 752 1450 772 Q 1490 774 1500 800 L 1620 1150 Q 1630 1185 1590 1190 L 330 1190 Q 290 1185 300 1150 L 420 800 Q 430 774 470 772 Z"
        fill="url(#gingham)"
        stroke={C.ink}
        strokeWidth={OUTLINE}
        strokeLinejoin="round"
      />
      <path d="M 430 800 Q 960 780 1490 800" stroke={C.white} strokeWidth={4} opacity={0.6} fill="none" />
    </g>
  );
};
