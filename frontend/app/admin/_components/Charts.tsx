"use client";

import { useState } from "react";
import type { Analytics } from "@/lib/adminTypes";

// Series colours in their validated order. A sixth series is never a new colour:
// it folds into "Other".
export const SERIES = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
];
const OTHER = "var(--color-chart-other)";

// Active students per day, as a line with a dot for each day. A crosshair and a
// readout follow the pointer, or the arrow keys when the chart has focus.
export function LineChart({ points }: { points: Analytics["daily_active_users"] }) {
  const [active, setActive] = useState<number | null>(null);
  const width = 640;
  const height = 200;
  const pad = { left: 36, right: 12, top: 12, bottom: 24 };
  const max = Math.max(1, ...points.map((p) => p.users));
  const top = Math.ceil(max / 2) * 2 || 2;
  const step = points.length <= 1 ? 0 : (width - pad.left - pad.right) / (points.length - 1);
  const x = (i: number) => pad.left + i * step;
  const y = (v: number) => pad.top + (1 - v / top) * (height - pad.top - pad.bottom);
  const line = points.map((p, i) => `${x(i)},${y(p.users)}`).join(" ");
  const labelEvery = Math.max(1, Math.ceil(points.length / 6));
  const last = points.length - 1;
  const shown = active === null ? null : points[active];

  function nearest(clientX: number, svg: SVGSVGElement) {
    const rect = svg.getBoundingClientRect();
    if (!rect.width || last < 0) return null;
    if (step === 0) return 0;
    const vx = ((clientX - rect.left) / rect.width) * width;
    return Math.min(last, Math.max(0, Math.round((vx - pad.left) / step)));
  }

  function onKeyDown(e: React.KeyboardEvent) {
    const move = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (move === 0 || last < 0) return;
    e.preventDefault();
    setActive((i) => Math.min(last, Math.max(0, (i ?? last) + move)));
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Active students per day"
        tabIndex={0}
        onPointerMove={(e) => setActive(nearest(e.clientX, e.currentTarget))}
        onPointerLeave={() => setActive(null)}
        onFocus={() => setActive((i) => i ?? (last >= 0 ? last : null))}
        onBlur={() => setActive(null)}
        onKeyDown={onKeyDown}
        className="w-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink"
      >
        {[0, top / 2, top].map((tick) => (
          <g key={tick}>
            <line x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} stroke="var(--color-ground)" />
            <text x={pad.left - 6} y={y(tick) + 4} textAnchor="end" fontSize="10" fill="var(--color-muted)">
              {tick}
            </text>
          </g>
        ))}
        {active !== null && (
          <line
            x1={x(active)}
            x2={x(active)}
            y1={pad.top}
            y2={height - pad.bottom}
            stroke="var(--color-muted)"
            aria-hidden
          />
        )}
        <polyline
          points={line}
          fill="none"
          stroke={SERIES[0]}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {points.map((p, i) => (
          <g key={p.date}>
            <circle cx={x(i)} cy={y(p.users)} r="4" fill={SERIES[0]} stroke="var(--color-surface)" strokeWidth="2">
              <title>{`${p.date}: ${p.users} students, ${p.questions} questions`}</title>
            </circle>
            {i % labelEvery === 0 && (
              <text x={x(i)} y={height - 6} textAnchor="middle" fontSize="10" fill="var(--color-muted)">
                {p.date.slice(5)}
              </text>
            )}
          </g>
        ))}
      </svg>
      {shown && active !== null && (
        <div
          aria-hidden
          className="pointer-events-none absolute top-0 bg-ink px-3 py-2 text-small leading-snug text-ground"
          style={{
            left: `${(x(active) / width) * 100}%`,
            transform: active > last / 2 ? "translateX(calc(-100% - 8px))" : "translateX(8px)",
          }}
        >
          <p className="font-medium">{shown.users} students</p>
          <p>{shown.questions} questions</p>
          <p>{shown.date}</p>
        </div>
      )}
      <p aria-live="polite" className="sr-only">
        {shown ? `${shown.date}: ${shown.users} students, ${shown.questions} questions` : ""}
      </p>
    </div>
  );
}

// A ring split into slices, with a legend. Beyond five slices the rest are summed into "Other".
export function Donut({ slices }: { slices: { label: string; value: number }[] }) {
  const rest = slices.slice(SERIES.length).reduce((sum, s) => sum + s.value, 0);
  const parts = [
    ...slices.slice(0, SERIES.length).map((s, i) => ({ ...s, colour: SERIES[i] })),
    ...(rest > 0 ? [{ label: "Other", value: rest, colour: OTHER }] : []),
  ];
  const total = parts.reduce((sum, s) => sum + s.value, 0);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  // A 2px gap in the panel colour separates neighbouring slices; a lone slice needs none.
  const gap = parts.filter((p) => p.value > 0).length > 1 ? 2 : 0;
  let offset = 0;

  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg viewBox="0 0 140 140" role="img" aria-label="Share of tool calls by tool" className="h-40 w-40 shrink-0">
        {total === 0 && <circle cx="70" cy="70" r={radius} fill="none" stroke="var(--color-ground)" strokeWidth="22" />}
        {total > 0 &&
          parts.map((slice) => {
            const length = (slice.value / total) * circumference;
            const drawn = Math.max(0, length - gap);
            const circle = (
              <circle
                key={slice.label}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={slice.colour}
                strokeWidth="22"
                strokeDasharray={`${drawn} ${circumference - drawn}`}
                strokeDashoffset={-offset}
                transform="rotate(-90 70 70)"
              >
                <title>{`${slice.label}: ${slice.value}`}</title>
              </circle>
            );
            offset += length;
            return circle;
          })}
        <text x="70" y="68" textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--color-ink)">
          {total}
        </text>
        <text x="70" y="84" textAnchor="middle" fontSize="9" fill="var(--color-muted)">
          tool calls
        </text>
      </svg>
      <ul className="min-w-0 flex-1 space-y-1.5 text-small">
        {parts.map((slice) => (
          <li key={slice.label} className="flex items-center gap-2">
            <span className="h-3 w-3 shrink-0" style={{ background: slice.colour }} />
            <span className="truncate">{slice.label}</span>
            <span className="ml-auto text-small tabular-nums text-muted">
              {slice.value} ({total ? Math.round((100 * slice.value) / total) : 0}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BarList({ rows }: { rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.label}>
          <div className="flex justify-between text-small">
            <span className="truncate">{row.label}</span>
            <span className="text-small tabular-nums text-muted">{row.value}</span>
          </div>
          <div className="mt-1 h-2 bg-ground">
            <div className="h-full bg-chart-1" style={{ width: `${(100 * row.value) / max}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

// The most common words in questions, bigger the more often they were used.
export function WordCloud({ terms }: { terms: { term: string; count: number }[] }) {
  const max = Math.max(1, ...terms.map((t) => t.count));
  const min = Math.min(max, ...terms.map((t) => t.count));
  const size = (count: number) => 13 + (max === min ? 10 : ((count - min) / (max - min)) * 25);
  return (
    <ul className="flex flex-wrap items-baseline gap-x-4 gap-y-2" aria-label="Most common words in questions">
      {[...terms]
        .sort((a, b) => a.term.localeCompare(b.term))
        .map((t) => (
          <li
            key={t.term}
            title={`${t.count} questions`}
            style={{ fontSize: `${size(t.count)}px` }}
            className="leading-tight text-ink"
          >
            {t.term}
          </li>
        ))}
    </ul>
  );
}

// Parts of a whole in one bar. Segments grow in proportion and sit 2px apart;
// empty parts are left out of the bar but stay in the legend.
export function StackedBar({ parts }: { parts: { label: string; value: number; colour: string }[] }) {
  const empty = parts.every((p) => p.value === 0);
  return (
    <div>
      <div
        className={`flex h-4 w-full gap-0.5 ${empty ? "bg-ground" : ""}`}
        role="img"
        aria-label="Outcome of proposed actions"
      >
        {parts
          .filter((p) => p.value > 0)
          .map((p) => (
            <div key={p.label} style={{ flex: `${p.value} 1 0`, background: p.colour }} title={`${p.label}: ${p.value}`} />
          ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-small text-muted">
        {parts.map((p) => (
          <li key={p.label} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5" style={{ background: p.colour }} />
            {p.label} {p.value}
          </li>
        ))}
      </ul>
    </div>
  );
}
