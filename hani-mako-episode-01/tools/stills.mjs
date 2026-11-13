// Render selected frames as PNG stills: node tools/stills.mjs <outDir> <scale> <frame> [frame...]
// Frames may also be cue ids with an optional +offset in frames, e.g. "move+60".
import { bundle } from '@remotion/bundler';
import { renderStill, selectComposition } from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';

const [outDir, scaleArg, ...frames] = process.argv.slice(2);
const browserExecutable = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
fs.mkdirSync(outDir, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.resolve('src/index.ts') });
const composition = await selectComposition({ serveUrl, id: 'EpisodeSilent', browserExecutable });
const tl = JSON.parse(fs.readFileSync('build/timeline.json', 'utf8'));
for (const spec of frames) {
  let frame = Number(spec);
  if (Number.isNaN(frame)) {
    const [id, off] = spec.split('+');
    frame = tl.cues.find((c) => c.id === id).start + Number(off ?? 0);
  }
  const output = path.join(outDir, `${spec.replace('+', '_')}.png`);
  await renderStill({ serveUrl, composition, frame, output, scale: Number(scaleArg), browserExecutable });
  console.log(output, frame);
}
