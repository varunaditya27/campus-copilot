"use client";

import type { Analytics } from "@/lib/adminTypes";

const PALETTE = ["#1b2a4a", "#b8863b", "#33684f", "#9c4a30", "#57534a", "#2e3f5c", "#d9bc85", "#8b8577"];

// Active students per day, as a line with a dot for each day.
export function LineChart({ points }: { points: Analytics["daily_active_users"] }) {
  const width = 640;
  const height = 200;
  const pad = { left: 36, right: 12, top: 12, bottom: 24 };
  const max = Math.max(1, ...points.map((p) => p.users));
  const top = Math.ceil(max / 2) * 2 || 2;
  const x = (i: number) => pad.left + (points.length <= 1 ? 0 : (i * (width - pad.left - pad.right)) / (points.length - 1));
  const y = (v: number) => pad.top + (1 - v / top) * (height - pad.top - pad.bottom);
  const line = points.map((p, i) => `${x(i)},${y(p.users)}`).join(" ");
  const labelEvery = Math.max(1, Math.ceil(points.length / 6));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Active students per day" className="w-full">
      {[0, top / 2, top].map((tick) => (
        <g key={tick}>
          <line x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} stroke="#ded5c0" />
          <text x={pad.left - 6} y={y(tick) + 4} textAnchor="end" fontSize="10" fill="#8b8577">
            {tick}
          </text>
        </g>
      ))}
      <polyline points={line} fill="none" stroke="#1b2a4a" strokeWidth="2" />
      {points.map((p, i) => (
        <g key={p.date}>
          <circle cx={x(i)} cy={y(p.users)} r="3.5" fill="#b8863b">
            <title>{`${p.date}: ${p.users} students, ${p.questions} questions`}</title>
          </circle>
          {i % labelEvery === 0 && (
            <text x={x(i)} y={height - 6} textAnchor="middle" fontSize="10" fill="#8b8577">
              {p.date.slice(5)}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

// A ring split into slices, with a legend.
export function Donut({ slices }: { slices: { label: string; value: number }[] }) {
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg viewBox="0 0 140 140" role="img" aria-label="Share of tool calls by tool" className="h-40 w-40 shrink-0">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#efe9d8" strokeWidth="22" />
        {total > 0 &&
          slices.map((slice, i) => {
            const length = (slice.value / total) * circumference;
            const circle = (
              <circle
                key={slice.label}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth="22"
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-offset}
                transform="rotate(-90 70 70)"
              >
                <title>{`${slice.label}: ${slice.value}`}</title>
              </circle>
            );
            offset += length;
            return circle;
          })}
        <text x="70" y="68" textAnchor="middle" fontSize="20" fontWeight="600" fill="#24211c">
          {total}
        </text>
        <text x="70" y="84" textAnchor="middle" fontSize="9" fill="#8b8577">
          tool calls
        </text>
      </svg>
      <ul className="min-w-0 flex-1 space-y-1.5 text-[13px]">
        {slices.map((slice, i) => (
          <li key={slice.label} className="flex items-center gap-2">
            <span className="h-3 w-3 shrink-0" style={{ background: PALETTE[i % PALETTE.length] }} />
            <span className="truncate">{slice.label}</span>
            <span className="ml-auto font-mono text-[12px] text-ink-soft">
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
          <div className="flex justify-between text-[13px]">
            <span className="truncate">{row.label}</span>
            <span className="font-mono text-[12px] text-ink-soft">{row.value}</span>
          </div>
          <div className="mt-1 h-2 bg-cream-sunken">
            <div className="h-full bg-navy" style={{ width: `${(100 * row.value) / max}%` }} />
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
        .map((t, i) => (
          <li
            key={t.term}
            title={`${t.count} questions`}
            style={{ fontSize: `${size(t.count)}px`, color: PALETTE[i % 4] }}
            className="font-display leading-tight"
          >
            {t.term}
          </li>
        ))}
    </ul>
  );
}

export function StackedBar({ parts }: { parts: { label: string; value: number; colour: string }[] }) {
  const total = parts.reduce((sum, p) => sum + p.value, 0);
  return (
    <div>
      <div className="flex h-4 w-full overflow-hidden bg-cream-sunken" role="img" aria-label="Outcome of proposed actions">
        {parts.map((p) => (
          <div key={p.label} style={{ width: `${total ? (100 * p.value) / total : 0}%`, background: p.colour }} title={`${p.label}: ${p.value}`} />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-soft">
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
