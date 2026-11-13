import React from 'react';
import { clamp, rad } from '../anim';
import { C, OUTLINE } from '../palette';
import { ArmP, CharSpec, pawLocal } from '../rig';

/** Noodle-style cutout arm: tapered stroke with an outline and a round paw. */
export const Arm: React.FC<{
  spec: CharSpec;
  side: 'armL' | 'armR';
  arm: ArmP;
  fill: string;
  pad?: string;
  width?: number;
  pawR?: number;
  sleeve?: string; // optional sleeve colour covering the upper part of the arm
  sleeveT?: number;
}> = ({ spec, side, arm, fill, pad, width = 30, pawR = 17, sleeve, sleeveT = 0.38 }) => {
  const s = side === 'armL' ? spec.shoulderL : spec.shoulderR;
  const h = pawLocal(spec, side, arm);
  const L = arm.len * spec.armBase;
  const a = rad(arm.angle);
  const perp = { x: Math.cos(a), y: -Math.sin(a) };
  const m = { x: (s.x + h.x) / 2 + perp.x * arm.bend * L * 0.35, y: (s.y + h.y) / 2 + perp.y * arm.bend * L * 0.35 };
  const d = `M ${s.x} ${s.y} Q ${m.x} ${m.y} ${h.x} ${h.y}`;
  return (
    <g>
      <path d={d} stroke={C.ink} strokeWidth={width + OUTLINE * 2} strokeLinecap="round" fill="none" />
      <circle cx={h.x} cy={h.y} r={pawR + OUTLINE} fill={C.ink} />
      <path d={d} stroke={fill} strokeWidth={width} strokeLinecap="round" fill="none" />
      <circle cx={h.x} cy={h.y} r={pawR} fill={fill} />
      {pad ? <ellipse cx={h.x} cy={h.y + 3} rx={pawR * 0.45} ry={pawR * 0.32} fill={pad} opacity={0.8} /> : null}
      {sleeve
        ? (() => {
            // de Casteljau split of the quadratic at sleeveT
            const t = sleeveT;
            const p01 = { x: s.x + (m.x - s.x) * t, y: s.y + (m.y - s.y) * t };
            const p11 = { x: m.x + (h.x - m.x) * t, y: m.y + (h.y - m.y) * t };
            const e = { x: p01.x + (p11.x - p01.x) * t, y: p01.y + (p11.y - p01.y) * t };
            const sd = `M ${s.x} ${s.y} Q ${p01.x} ${p01.y} ${e.x} ${e.y}`;
            return (
              <>
                <path d={sd} stroke={C.ink} strokeWidth={width + 7 + OUTLINE * 2} strokeLinecap="round" fill="none" />
                <path d={sd} stroke={sleeve} strokeWidth={width + 7} strokeLinecap="round" fill="none" />
              </>
            );
          })()
        : null}
    </g>
  );
};

export const Eye: React.FC<{
  x: number;
  y: number;
  rx: number;
  ry: number;
  open: number;
  happy: number;
  lookX: number;
  lookY: number;
  iris?: string;
  lashes?: -1 | 1; // draw two small lashes on the outer side (-1 = left eye, 1 = right eye)
}> = ({ x, y, rx, ry, open, happy, lookX, lookY, iris = C.ink, lashes }) => {
  const ox = clamp(lookX, -1, 1) * rx * 0.42;
  const oy = clamp(lookY, -1, 1) * ry * 0.3;
  if (happy > 0.5) {
    const w = rx * 1.15;
    return (
      <path
        d={`M ${x - w} ${y + 4} Q ${x} ${y - ry * 0.95} ${x + w} ${y + 4}`}
        stroke={C.ink}
        strokeWidth={5.5}
        strokeLinecap="round"
        fill="none"
      />
    );
  }
  if (open < 0.18) {
    return (
      <path
        d={`M ${x - rx * 1.05} ${y} Q ${x} ${y + ry * 0.35} ${x + rx * 1.05} ${y}`}
        stroke={C.ink}
        strokeWidth={5}
        strokeLinecap="round"
        fill="none"
      />
    );
  }
  const ery = ry * open;
  return (
    <g>
      {lashes ? (
        <path
          d={`M ${x + lashes * rx * 0.7} ${y - ery * 0.72} l ${lashes * 7} ${-6} M ${x + lashes * rx * 0.98} ${y - ery * 0.3} l ${lashes * 8} ${-3}`}
          stroke={C.ink}
          strokeWidth={3.5}
          strokeLinecap="round"
        />
      ) : null}
      <ellipse cx={x + ox} cy={y + oy} rx={rx} ry={ery} fill={iris} />
      {open > 0.45 ? (
        <>
          <circle cx={x + ox - rx * 0.32} cy={y + oy - ery * 0.38} r={rx * 0.38} fill={C.white} />
          <circle cx={x + ox + rx * 0.36} cy={y + oy + ery * 0.32} r={rx * 0.17} fill={C.white} opacity={0.9} />
        </>
      ) : null}
    </g>
  );
};

export const Brow: React.FC<{ x: number; y: number; side: -1 | 1; browY: number; tilt: number; w?: number }> = ({
  x,
  y,
  side,
  browY,
  tilt,
  w = 12,
}) => {
  const yy = y + browY * 7;
  // side -1 = screen-left brow (inner end is its right end)
  const rot = side === -1 ? -tilt * 18 : tilt * 18;
  return (
    <path
      d={`M ${x - w} ${yy + 2} Q ${x} ${yy - 6} ${x + w} ${yy + 2}`}
      transform={`rotate(${rot} ${x} ${yy})`}
      stroke={C.ink}
      strokeWidth={5}
      strokeLinecap="round"
      fill="none"
    />
  );
};

export const Mouth: React.FC<{
  x: number;
  y: number;
  open: number;
  smile: number;
  round: number;
  style: 'bunny' | 'bear' | 'kid';
}> = ({ x, y, open, smile, round, style }) => {
  if (open < 0.07) {
    const s = clamp(smile, -1, 1);
    if (style === 'bunny') {
      return (
        <path
          d={`M ${x - 13} ${y - 3} Q ${x - 6.5} ${y + 5 + s * 4} ${x} ${y} Q ${x + 6.5} ${y + 5 + s * 4} ${x + 13} ${y - 3}`}
          stroke={C.ink}
          strokeWidth={4}
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      );
    }
    if (style === 'kid') {
      return (
        <path
          d={`M ${x - 14} ${y - 2} Q ${x} ${y + 6 + s * 7} ${x + 14} ${y - 2}`}
          stroke={C.ink}
          strokeWidth={4}
          strokeLinecap="round"
          fill="none"
        />
      );
    }
    return (
      <g stroke={C.ink} strokeWidth={4} strokeLinecap="round" fill="none">
        <path d={`M ${x} ${y - 9} L ${x} ${y}`} />
        <path d={`M ${x - 15} ${y - 3} Q ${x - 7.5} ${y + 4 + s * 5} ${x} ${y} Q ${x + 7.5} ${y + 4 + s * 5} ${x + 15} ${y - 3}`} />
      </g>
    );
  }
  const w = (24 + 10 * clamp(smile, 0, 1)) * (1 - 0.42 * round);
  const h = 5 + clamp(open, 0, 1) * 24;
  const top = -2 - round * 2;
  const d = `M ${x - w / 2} ${y + top} C ${x - w / 2} ${y + h} ${x + w / 2} ${y + h} ${x + w / 2} ${y + top} C ${
    x + w / 4
  } ${y + top - 3 + smile * 2} ${x - w / 4} ${y + top - 3 + smile * 2} ${x - w / 2} ${y + top} Z`;
  return (
    <g>
      <path d={d} fill={C.mouth} stroke={C.ink} strokeWidth={3.5} strokeLinejoin="round" />
      {h > 12 ? <ellipse cx={x} cy={y + top + h * 0.62} rx={w * 0.26} ry={h * 0.16} fill={C.tongue} /> : null}
      {style === 'bunny' ? (
        <g fill={C.white} stroke={C.ink} strokeWidth={1.6}>
          <rect x={x - 6} y={y + top - 1} width={5.6} height={6.5} rx={1.5} />
          <rect x={x + 0.4} y={y + top - 1} width={5.6} height={6.5} rx={1.5} />
        </g>
      ) : null}
    </g>
  );
};
