"""
Build a self-contained, offline HTML step-viewer from a results/layout.json.

Each placement in layout.json is in the order the greedy algorithm placed it, so
we can replay the run frame by frame: step k shows the first k+1 shapes, with the
newly added shape highlighted and the running bounding box drawn.

Usage:
    python3 viz/export_viewer.py results_simple
    python3 viz/export_viewer.py results_edge
"""

import json
import os
import sys

# allow "from src...." when run as a plain script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shapes import build_default_shapes
from src.persistence import load_placements

CANVAS_W, CANVAS_H = 200.0, 100.0

# tab10 palette, indexed by shape id (matches the matplotlib pictures)
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
           "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]


def build_frames(results_dir):
    shapes = build_default_shapes()
    path = os.path.join(results_dir, "layout.json")
    placements = load_placements(shapes, path=path)

    frames = []
    for p in placements:
        verts = list(p.polygon.exterior.coords)[:-1]      # drop closing point
        frames.append({
            "name": p.shape_type.name,
            "angle": round(p.rotation, 1),
            "color": PALETTE[p.shape_type.id % len(PALETTE)],
            "area": round(p.polygon.area, 4),
            "verts": [[round(x, 4), round(y, 4)] for x, y in verts],
        })
    return frames


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NFP packing - step viewer (__DIR__)</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: #fafafa; color: #111; }
  @media (prefers-color-scheme: dark) { body { background:#15171a; color:#e8e8e8; } }
  header { padding: 12px 16px; }
  h1 { font-size: 16px; margin: 0 0 2px; }
  .sub { font-size: 12px; opacity: .7; }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 0 16px 24px; }
  .stage { width: 100%; background: #fff; border: 1px solid #ccc; border-radius: 8px; }
  @media (prefers-color-scheme: dark) { .stage { background:#0e0f11; border-color:#333; } }
  svg { width: 100%; height: auto; display: block; border-radius: 8px; }
  .controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 12px 0; }
  button { font-size: 14px; padding: 6px 12px; border-radius: 6px; border: 1px solid #999;
           background: #fff; color: inherit; cursor: pointer; }
  @media (prefers-color-scheme: dark) { button { background:#23262b; border-color:#444; } }
  button:hover { border-color: #666; }
  input[type=range] { flex: 1 1 260px; min-width: 200px; }
  .info { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 8px 20px; font-size: 13px; margin-top: 6px; }
  .info div span { opacity: .6; }
  .info div b { font-variant-numeric: tabular-nums; }
  .speed { font-size: 13px; display: flex; align-items: center; gap: 6px; }
  kbd { font-size: 11px; border:1px solid #999; border-radius:4px; padding:0 4px; }
</style>
</head>
<body>
<header>
  <h1>Deterministic greedy NFP packing &mdash; step viewer</h1>
  <div class="sub">Source: __DIR__/layout.json &middot; drag the slider or press
     <kbd>&larr;</kbd> <kbd>&rarr;</kbd> &middot; <kbd>Space</kbd> plays/pauses</div>
</header>
<div class="wrap">
  <div class="stage"><svg id="svg" viewBox="0 0 1020 540" preserveAspectRatio="xMidYMid meet"></svg></div>
  <div class="controls">
    <button id="first">&#8676; first</button>
    <button id="prev">&larr; prev</button>
    <button id="play">&#9654; play</button>
    <button id="next">next &rarr;</button>
    <button id="last">last &#8677;</button>
    <input id="slider" type="range" min="0" max="0" value="0">
    <label class="speed">speed
      <input id="speed" type="range" min="1" max="60" value="20"> <b id="fps">20</b>/s</label>
  </div>
  <div class="info">
    <div><span>step</span> <b id="i_step">0</b> / <b id="i_total">0</b></div>
    <div><span>just placed</span> <b id="i_shape">&mdash;</b></div>
    <div><span>rotation</span> <b id="i_angle">&mdash;</b></div>
    <div><span>area added</span> <b id="i_area">&mdash;</b></div>
    <div><span>used area</span> <b id="i_used">0</b></div>
    <div><span>utilisation</span> <b id="i_util">0.00%</b></div>
    <div><span>bounding-box density</span> <b id="i_dens">&mdash;</b></div>
  </div>
</div>

<script>
const FRAMES = __FRAMES__;
const CANVAS_W = __CW__, CANVAS_H = __CH__, CANVAS_AREA = CANVAS_W * CANVAS_H;

// world (x up) -> svg (y down), with a margin
const PAD = 10, SCALE = 5;               // 200*5=1000 + 2*10 = 1020 wide
const SX = x => PAD + x * SCALE;
const SY = y => PAD + (CANVAS_H - y) * SCALE;

const svg = document.getElementById('svg');
const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs) { const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }

// static canvas border
function drawCanvasBorder() {
  svg.appendChild(el('rect', {x: SX(0), y: SY(CANVAS_H), width: CANVAS_W*SCALE,
    height: CANVAS_H*SCALE, fill: 'none', stroke: '#e11', 'stroke-width': 2}));
}

// precompute cumulative used area
const CUM = []; let acc = 0;
for (const f of FRAMES) { acc += f.area; CUM.push(acc); }

let idx = 0, playing = false, timer = null;

function bbox(upto) {
  let minx=1e9, miny=1e9, maxx=-1e9, maxy=-1e9;
  for (let k=0; k<=upto; k++) for (const [x,y] of FRAMES[k].verts) {
    if (x<minx)minx=x; if (y<miny)miny=y; if (x>maxx)maxx=x; if (y>maxy)maxy=y; }
  return [minx,miny,maxx,maxy];
}

function render() {
  svg.innerHTML = '';
  drawCanvasBorder();
  if (FRAMES.length === 0) return;

  // shapes 0..idx
  for (let k=0; k<=idx; k++) {
    const f = FRAMES[k];
    const pts = f.verts.map(([x,y]) => `${SX(x)},${SY(y)}`).join(' ');
    const isNew = (k === idx);
    svg.appendChild(el('polygon', {points: pts, fill: f.color,
      'fill-opacity': isNew ? 0.95 : 0.80,
      stroke: isNew ? '#000' : '#333',
      'stroke-width': isNew ? 2.5 : 0.7}));
  }
  // running bounding box (denominator of bbox density)
  const [minx,miny,maxx,maxy] = bbox(idx);
  svg.appendChild(el('rect', {x: SX(minx), y: SY(maxy),
    width: (maxx-minx)*SCALE, height: (maxy-miny)*SCALE,
    fill: 'none', stroke: '#09f', 'stroke-width': 1.2, 'stroke-dasharray': '6 4'}));

  // info
  const f = FRAMES[idx];
  const used = CUM[idx];
  const bboxArea = (maxx-minx)*(maxy-miny);
  document.getElementById('i_step').textContent = idx+1;
  document.getElementById('i_total').textContent = FRAMES.length;
  document.getElementById('i_shape').textContent = f.name;
  document.getElementById('i_angle').textContent = f.angle + '\\u00b0';
  document.getElementById('i_area').textContent = f.area.toFixed(2);
  document.getElementById('i_used').textContent = used.toFixed(1) + ' / ' + CANVAS_AREA;
  document.getElementById('i_util').textContent = (used/CANVAS_AREA*100).toFixed(2) + '%';
  document.getElementById('i_dens').textContent =
    bboxArea > 0 ? (used/bboxArea).toFixed(4) : '\\u2014';
  document.getElementById('slider').value = idx;
}

function go(i) { idx = Math.max(0, Math.min(FRAMES.length-1, i)); render(); }
function stopPlay() { playing=false; if (timer) clearInterval(timer); timer=null;
  document.getElementById('play').innerHTML = '\\u25b6 play'; }
function startPlay() {
  if (idx >= FRAMES.length-1) idx = 0;
  playing=true; document.getElementById('play').innerHTML = '\\u23f8 pause';
  const fps = +document.getElementById('speed').value;
  timer = setInterval(() => {
    if (idx >= FRAMES.length-1) { stopPlay(); return; }
    go(idx+1);
  }, 1000/fps);
}

document.getElementById('first').onclick = () => { stopPlay(); go(0); };
document.getElementById('prev').onclick  = () => { stopPlay(); go(idx-1); };
document.getElementById('next').onclick  = () => { stopPlay(); go(idx+1); };
document.getElementById('last').onclick  = () => { stopPlay(); go(FRAMES.length-1); };
document.getElementById('play').onclick  = () => { playing ? stopPlay() : startPlay(); };
document.getElementById('slider').oninput = (e) => { stopPlay(); go(+e.target.value); };
document.getElementById('speed').oninput  = (e) => {
  document.getElementById('fps').textContent = e.target.value;
  if (playing) { stopPlay(); startPlay(); } };
window.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') { stopPlay(); go(idx+1); }
  else if (e.key === 'ArrowLeft') { stopPlay(); go(idx-1); }
  else if (e.key === ' ') { e.preventDefault(); playing ? stopPlay() : startPlay(); }
});

document.getElementById('slider').max = Math.max(0, FRAMES.length-1);
render();
</script>
</body>
</html>
"""


def main():
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results_simple"
    frames = build_frames(results_dir)
    if not frames:
        print(f"no placements found in {results_dir}/layout.json")
        return

    html = (HTML_TEMPLATE
            .replace("__FRAMES__", json.dumps(frames))
            .replace("__CW__", str(CANVAS_W))
            .replace("__CH__", str(CANVAS_H))
            .replace("__DIR__", results_dir))

    out = os.path.join(results_dir, "step_viewer.html")
    with open(out, "w") as fh:
        fh.write(html)
    print(f"wrote {out}  ({len(frames)} frames, {os.path.getsize(out)//1024} KB)")


if __name__ == "__main__":
    main()
