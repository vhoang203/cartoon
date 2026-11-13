import React, { useMemo } from 'react';
import { AbsoluteFill, Audio, staticFile, useCurrentFrame } from 'remotion';
import { easeOut, prog } from '../lib/anim';
import { Hani } from '../lib/characters/Hani';
import { Mako } from '../lib/characters/Mako';
import { Garden } from '../lib/environment/Garden';
import { C } from '../lib/palette';
import { BowlBack, BowlFront, NumberBadge, Plate, Strawberry, ThoughtBubble } from '../lib/props/Props';
import manifestJson from '../generated/audio-manifest.json';
import { evaluate, type SceneView } from './evaluate';
import { BADGE_POS, PLATE, THOUGHT_POS } from './layout';
import { buildTimeline, type Manifest, type Timeline } from './timeline';
import { FontLoader } from '../lib/fonts';

const manifest = manifestJson as unknown as Manifest;
export const getTimeline = (): Timeline => buildTimeline(manifest);

const ring = { hani: C.teal, mako: C.sky };

const Sparkle: React.FC<{ x: number; y: number; s: number; o: number }> = ({ x, y, s, o }) => (
  <path
    d="M 0 -16 Q 3 -3 16 0 Q 3 3 0 16 Q -3 3 -16 0 Q -3 -3 0 -16 Z"
    transform={`translate(${x} ${y}) scale(${s})`}
    fill="#FFE27A"
    stroke="#E9B93B"
    strokeWidth={2}
    opacity={o}
  />
);

/** World-space scene (1920x1300) — shared by the episode and the thumbnail. */
export const World: React.FC<{ v: SceneView; f: number }> = ({ v, f }) => {
  const H = v.chars.hani;
  const M = v.chars.mako;
  const bowlBerries = v.berries.filter((b) => b.layer === 'bowl');
  const plateBerries = v.berries.filter((b) => b.layer === 'plate');
  const topBerries = v.berries.filter((b) => b.layer === 'top');
  const berry = (b: (typeof v.berries)[number]) => (
    <Strawberry key={b.id} x={b.x} y={b.y} rot={b.rot} glow={b.glow} scale={b.scale} />
  );
  const think = v.overlays.find((o) => o.kind === 'think');
  const equal = v.overlays.find((o) => o.kind === 'equal');
  return (
    <g>
      <Garden t={f} />
      {H.behindBowl ? <Hani p={H.p} layer="body" t={f} armsInFront={H.armsInFront} /> : null}
      <BowlBack x={v.bowl.x} y={v.bowl.y} />
      {bowlBerries.map(berry)}
      <BowlFront x={v.bowl.x} y={v.bowl.y} />
      {!H.behindBowl ? <Hani p={H.p} layer="body" t={f} armsInFront={H.armsInFront} /> : null}
      <Mako p={M.p} layer="body" t={f} />
      <Plate x={PLATE.hani.x} y={PLATE.hani.y} rim={C.teal} rimDark={C.tealDark} />
      <Plate x={PLATE.mako.x} y={PLATE.mako.y} rim={C.sky} rimDark={C.skyDark} />
      {plateBerries.map(berry)}
      <Hani p={H.p} layer="front" t={f} armsInFront={H.armsInFront} />
      <Mako p={M.p} layer="front" t={f} />
      {topBerries.map(berry)}
      {equal
        ? [PLATE.hani, PLATE.mako].flatMap((pl, i) =>
            [
              [-118, -30],
              [112, -44],
              [-60, -76],
              [70, -84],
            ].map(([dx, dy], j) => {
              const ph = (equal.age - j * 6 - i * 9) / 30;
              const s = ph > 0 ? Math.sin(Math.min(1, ph) * Math.PI) : 0;
              return <Sparkle key={`${i}-${j}`} x={pl.x + dx} y={pl.y + dy} s={s * 1.1} o={s * (1 - prog(equal.p, 0.85, 1))} />;
            }),
          )
        : null}
      {v.badges.map((b) => (
        <NumberBadge key={b.who} x={BADGE_POS[b.who].x} y={BADGE_POS[b.who].y} n={b.n} ring={ring[b.who]} scale={b.scale} opacity={b.opacity} />
      ))}
      {v.tags.map((t) => (
        <NumberBadge key={t.id} x={t.x} y={t.y} n={t.n} r={22} ring="#FFC94D" scale={t.scale} opacity={t.opacity} fill="#FFF8D6" />
      ))}
      {think
        ? (['hani', 'mako'] as const).map((w, i) => {
            const a = easeOut(prog(think.age, i * 6, i * 6 + 14));
            const out = 1 - prog(think.left, 0, 12);
            return (
              <ThoughtBubble
                key={w}
                x={THOUGHT_POS[w].x}
                y={THOUGHT_POS[w].y + Math.sin((think.age + i * 20) / 20) * 3}
                scale={a * (1 - out * 0.3)}
                opacity={a * (1 - out)}
                tail={w === 'hani' ? -1 : 1}
              />
            );
          })
        : null}
    </g>
  );
};

const TitleCard: React.FC<{ p: number; age: number; left: number; end?: boolean }> = ({ age, left, end }) => {
  const a = easeOut(prog(age, 0, 14)) * prog(left, 0, 14);
  const s = 0.85 + 0.15 * easeOut(prog(age, 0, 18));
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top: end ? 70 : 90,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        opacity: a,
        transform: `scale(${s})`,
        fontFamily: 'Nunito',
      }}
    >
      <div
        style={{
          fontSize: end ? 110 : 150,
          fontWeight: 900,
          color: C.teal,
          WebkitTextStroke: `10px ${C.ink}`,
          paintOrder: 'stroke fill',
          letterSpacing: 2,
          lineHeight: 1.05,
          textShadow: '0 8px 0 rgba(46,58,75,0.18)',
        }}
      >
        Hani <span style={{ color: C.apricot }}>&amp;</span> <span style={{ color: C.sky }}>Mako</span>
      </div>
      <div
        style={{
          marginTop: 22,
          padding: '14px 40px',
          borderRadius: 999,
          background: 'rgba(255,251,242,0.94)',
          border: `5px solid ${C.ink}`,
          fontSize: end ? 50 : 54,
          fontWeight: 800,
          color: C.ink,
        }}
      >
        {end ? 'Hẹn gặp lại các bạn!' : 'Tập 1 · Bữa picnic của Hani và Mako'}
      </div>
    </div>
  );
};

export const SceneFrame: React.FC<{ tl: Timeline; f: number; width?: number; height?: number; camera?: { cx: number; cy: number; z: number } }> = ({
  tl,
  f,
  width = 1920,
  height = 1080,
  camera,
}) => {
  const v = evaluate(tl, manifest, f);
  const { cx, cy, z } = camera ?? v.camera;
  const k = width / 1920;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ position: 'absolute', inset: 0 }}>
      <g transform={`scale(${k}) translate(960 540) scale(${z}) translate(${-cx} ${-cy})`}>
        <World v={v} f={f} />
      </g>
    </svg>
  );
};

export const Episode01: React.FC<{ withAudio?: boolean; startFrame?: number }> = ({ withAudio = true, startFrame = 0 }) => {
  const frame = useCurrentFrame() + startFrame;
  const tl = useMemo(getTimeline, []);
  const v = evaluate(tl, manifest, frame);
  const title = v.overlays.find((o) => o.kind === 'title');
  const end = v.overlays.find((o) => o.kind === 'end');
  return (
    <AbsoluteFill style={{ backgroundColor: C.cream }}>
      <FontLoader />
      <SceneFrame tl={tl} f={frame} />
      {title ? <TitleCard {...title} /> : null}
      {end ? <TitleCard {...end} end /> : null}
      {withAudio ? <Audio src={staticFile('audio/mix.wav')} startFrom={startFrame} /> : null}
    </AbsoluteFill>
  );
};
