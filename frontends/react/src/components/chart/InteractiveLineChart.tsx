import { useEffect, useMemo, useRef, useState } from "react";

export interface ChartSeries {
  name: string;
  color: string;
  points: [number, number][];
  fillBaseline?: number; // if set, area-fill down to this Y value
}

interface Domain {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

const MARGIN = { top: 12, right: 16, bottom: 34, left: 58 };
const WIDTH = 720;
const HEIGHT = 320;

function computeExtentDomain(series: ChartSeries[], aspectLock: boolean): Domain {
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
  for (const s of series) {
    for (const [x, y] of s.points) {
      if (x < xMin) xMin = x;
      if (x > xMax) xMax = x;
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    }
  }
  if (!isFinite(xMin)) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };

  const padX = (xMax - xMin) * 0.05 || 1;
  const padY = (yMax - yMin) * 0.12 || 1;
  xMin -= padX; xMax += padX; yMin -= padY; yMax += padY;

  if (aspectLock) {
    const innerW = WIDTH - MARGIN.left - MARGIN.right;
    const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;
    const dataAspect = (xMax - xMin) / (yMax - yMin || 1);
    const boxAspect = innerW / innerH;
    if (dataAspect > boxAspect) {
      const targetYRange = (xMax - xMin) / boxAspect;
      const cy = (yMin + yMax) / 2;
      yMin = cy - targetYRange / 2;
      yMax = cy + targetYRange / 2;
    } else {
      const targetXRange = (yMax - yMin) * boxAspect;
      const cx = (xMin + xMax) / 2;
      xMin = cx - targetXRange / 2;
      xMax = cx + targetXRange / 2;
    }
  }
  return { xMin, xMax, yMin, yMax };
}

/** Lightweight interactive SVG line/area chart: wheel-to-zoom, drag-to-pan,
 * hover tooltip on the nearest point of the primary (first) series. No
 * charting library dependency — see the note in the React frontend README. */
export function InteractiveLineChart({
  series,
  xLabel,
  yLabel,
  aspectLock = false,
  valueFormatter = (v: number) => v.toFixed(2),
}: {
  series: ChartSeries[];
  xLabel: string;
  yLabel: string;
  aspectLock?: boolean;
  valueFormatter?: (v: number) => string;
}) {
  const baseDomain = useMemo(() => computeExtentDomain(series, aspectLock), [series, aspectLock]);
  const [domain, setDomain] = useState<Domain>(baseDomain);
  useEffect(() => setDomain(baseDomain), [baseDomain]);

  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef<{ x: number; y: number; domain: Domain } | null>(null);
  const [hover, setHover] = useState<{ px: number; py: number; index: number } | null>(null);

  const innerW = WIDTH - MARGIN.left - MARGIN.right;
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;

  const xScale = (x: number) => MARGIN.left + ((x - domain.xMin) / (domain.xMax - domain.xMin)) * innerW;
  const yScale = (y: number) => MARGIN.top + innerH - ((y - domain.yMin) / (domain.yMax - domain.yMin)) * innerH;
  // Native (non-passive) wheel listener so preventDefault actually stops page scroll.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * WIDTH;
      const py = ((e.clientY - rect.top) / rect.height) * HEIGHT;
      const factor = e.deltaY > 0 ? 1.12 : 1 / 1.12;
      setDomain((d) => {
        const cx = d.xMin + ((px - MARGIN.left) / innerW) * (d.xMax - d.xMin);
        const cy = d.yMin + (innerH - (py - MARGIN.top)) / innerH * (d.yMax - d.yMin);
        const newW = Math.max((d.xMax - d.xMin) * factor, (baseDomain.xMax - baseDomain.xMin) * 0.02);
        const newH = Math.max((d.yMax - d.yMin) * factor, (baseDomain.yMax - baseDomain.yMin) * 0.02);
        const cappedW = Math.min(newW, (baseDomain.xMax - baseDomain.xMin) * 4);
        const cappedH = Math.min(newH, (baseDomain.yMax - baseDomain.yMin) * 4);
        const xFrac = (cx - d.xMin) / (d.xMax - d.xMin);
        const yFrac = (cy - d.yMin) / (d.yMax - d.yMin);
        return {
          xMin: cx - xFrac * cappedW,
          xMax: cx + (1 - xFrac) * cappedW,
          yMin: cy - yFrac * cappedH,
          yMax: cy + (1 - yFrac) * cappedH,
        };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [baseDomain, innerW, innerH]);

  function handlePointerDown(e: React.PointerEvent<SVGSVGElement>) {
    (e.target as Element).setPointerCapture(e.pointerId);
    draggingRef.current = { x: e.clientX, y: e.clientY, domain };
  }
  function handlePointerMove(e: React.PointerEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * WIDTH;
    const py = ((e.clientY - rect.top) / rect.height) * HEIGHT;

    if (draggingRef.current) {
      const start = draggingRef.current;
      const dxPx = e.clientX - start.x;
      const dyPx = e.clientY - start.y;
      const dxData = -(dxPx / rect.width) * WIDTH * ((start.domain.xMax - start.domain.xMin) / innerW);
      const dyData = (dyPx / rect.height) * HEIGHT * ((start.domain.yMax - start.domain.yMin) / innerH);
      setDomain({
        xMin: start.domain.xMin + dxData,
        xMax: start.domain.xMax + dxData,
        yMin: start.domain.yMin + dyData,
        yMax: start.domain.yMax + dyData,
      });
      return;
    }

    // Hover: nearest point on the primary series, by pixel distance.
    const primary = series[0];
    if (!primary || primary.points.length === 0) return;
    let bestIdx = 0, bestDist = Infinity;
    for (let i = 0; i < primary.points.length; i++) {
      const [x, y] = primary.points[i];
      const ddx = xScale(x) - px;
      const ddy = yScale(y) - py;
      const d = ddx * ddx + ddy * ddy;
      if (d < bestDist) { bestDist = d; bestIdx = i; }
    }
    setHover({ px, py, index: bestIdx });
  }
  function handlePointerUp() {
    draggingRef.current = null;
  }

  function resetView() {
    setDomain(baseDomain);
  }

  const xTicks = useMemo(() => niceTicks(domain.xMin, domain.xMax, 6), [domain]);
  const yTicks = useMemo(() => niceTicks(domain.yMin, domain.yMax, 5), [domain]);

  const hoverPoint = hover ? series.map((s) => s.points[hover.index]).find(Boolean) : null;

  return (
    <div className="flex flex-col gap-2">
      <div ref={containerRef} className="relative w-full touch-none select-none">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full cursor-grab rounded-md border border-navy/10 bg-white active:cursor-grabbing"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={() => { setHover(null); draggingRef.current = null; }}
        >
          {/* Axes */}
          <line x1={MARGIN.left} y1={MARGIN.top} x2={MARGIN.left} y2={HEIGHT - MARGIN.bottom} stroke="#20293a33" />
          <line x1={MARGIN.left} y1={HEIGHT - MARGIN.bottom} x2={WIDTH - MARGIN.right} y2={HEIGHT - MARGIN.bottom} stroke="#20293a33" />

          {xTicks.map((t) => (
            <g key={`x${t}`}>
              <line x1={xScale(t)} y1={HEIGHT - MARGIN.bottom} x2={xScale(t)} y2={HEIGHT - MARGIN.bottom + 4} stroke="#20293a55" />
              <text x={xScale(t)} y={HEIGHT - MARGIN.bottom + 16} fontSize={9} textAnchor="middle" fill="#697386">
                {valueFormatter(t)}
              </text>
            </g>
          ))}
          {yTicks.map((t) => (
            <g key={`y${t}`}>
              <line x1={MARGIN.left - 4} y1={yScale(t)} x2={MARGIN.left} y2={yScale(t)} stroke="#20293a55" />
              <text x={MARGIN.left - 8} y={yScale(t) + 3} fontSize={9} textAnchor="end" fill="#697386">
                {valueFormatter(t)}
              </text>
            </g>
          ))}

          <text x={(WIDTH + MARGIN.left - MARGIN.right) / 2} y={HEIGHT - 4} fontSize={10} textAnchor="middle" fill="#202a3a">
            {xLabel}
          </text>
          <text
            x={12}
            y={(HEIGHT - MARGIN.bottom + MARGIN.top) / 2}
            fontSize={10}
            textAnchor="middle"
            fill="#202a3a"
            transform={`rotate(-90 12 ${(HEIGHT - MARGIN.bottom + MARGIN.top) / 2})`}
          >
            {yLabel}
          </text>

          {series.map((s) => {
            const path = s.points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${xScale(x)},${yScale(y)}`).join(" ");
            return (
              <g key={s.name}>
                {s.fillBaseline !== undefined && (
                  <path
                    d={`${path} L${xScale(s.points[s.points.length - 1]?.[0] ?? 0)},${yScale(s.fillBaseline)} L${xScale(s.points[0]?.[0] ?? 0)},${yScale(s.fillBaseline)} Z`}
                    fill={s.color}
                    opacity={0.12}
                    stroke="none"
                  />
                )}
                <path d={path} fill="none" stroke={s.color} strokeWidth={1.75} />
              </g>
            );
          })}

          {hover && hoverPoint && (
            <g>
              <line x1={xScale(hoverPoint[0])} y1={MARGIN.top} x2={xScale(hoverPoint[0])} y2={HEIGHT - MARGIN.bottom} stroke="#20293a55" strokeDasharray="3 3" />
              {series.map((s) => {
                const pt = s.points[hover.index];
                if (!pt) return null;
                return <circle key={s.name} cx={xScale(pt[0])} cy={yScale(pt[1])} r={3} fill={s.color} />;
              })}
            </g>
          )}
        </svg>

        {hover && hoverPoint && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border border-navy/15 bg-white/95 px-2 py-1 text-xs shadow"
            style={{
              left: `${(xScale(hoverPoint[0]) / WIDTH) * 100}%`,
              top: `${(yScale(hoverPoint[1]) / HEIGHT) * 100}%`,
            }}
          >
            <div className="font-semibold text-navy">
              {xLabel} = {valueFormatter(hoverPoint[0])}
            </div>
            {series.map((s) => {
              const pt = s.points[hover.index];
              if (!pt) return null;
              return (
                <div key={s.name} style={{ color: s.color }}>
                  {s.name}: {valueFormatter(pt[1])}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted">
        <span>Molette = zoom · glisser = déplacer</span>
        <button type="button" onClick={resetView} className="font-semibold text-navy hover:text-accent">
          Réinitialiser la vue
        </button>
      </div>
    </div>
  );
}

function niceTicks(min: number, max: number, count: number): number[] {
  if (!isFinite(min) || !isFinite(max) || min === max) return [min];
  const step = (max - min) / count;
  const magnitude = Math.pow(10, Math.floor(Math.log10(step)));
  const residual = step / magnitude;
  let niceStep: number;
  if (residual > 5) niceStep = 10 * magnitude;
  else if (residual > 2) niceStep = 5 * magnitude;
  else if (residual > 1) niceStep = 2 * magnitude;
  else niceStep = magnitude;

  const ticks: number[] = [];
  const start = Math.ceil(min / niceStep) * niceStep;
  for (let v = start; v <= max; v += niceStep) ticks.push(Number(v.toFixed(6)));
  return ticks;
}
