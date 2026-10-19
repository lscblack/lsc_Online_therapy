// Lightweight inline-SVG charts for the dashboard (no chart library). Colours inherit via
// currentColor / theme vars, so they adapt to light/dark automatically.

function points(data: number[], w: number, h: number, pad = 2): string {
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const span = max - min || 1;
  const step = (w - pad * 2) / Math.max(data.length - 1, 1);
  return data.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - ((v - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

export function Sparkline({ data, w = 120, h = 36 }: { data: number[]; w?: number; h?: number }) {
  const pts = points(data, w, h);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden="true" className="spark">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function AreaChart({ data, labels, w = 640, h = 220 }: { data: number[]; labels?: string[]; w?: number; h?: number }) {
  const padB = 24;
  const pts = points(data, w, h - padB);
  const area = `${pts} ${w - 2},${h - padB} 2,${h - padB}`;
  const last = pts.split(" ").pop()?.split(",").map(Number) ?? [0, 0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} role="img" aria-label="trend" className="area">
      <polygon points={area} fill="currentColor" opacity="0.14" />
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="4.5" fill="currentColor" stroke="var(--color-surface)" strokeWidth="2" />
      {labels && labels.map((l, i) => {
        const x = 2 + (i * (w - 4)) / Math.max(labels.length - 1, 1);
        return <text key={i} x={x} y={h - 6} fontSize="10" textAnchor="middle" fill="var(--color-text-muted)">{l}</text>;
      })}
    </svg>
  );
}

export function Donut({ value, size = 110, label }: { value: number; size?: number; label?: string }) {
  const r = size / 2 - 10;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={`${pct}%`} className="donut">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-surface-3)" strokeWidth="10" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth="10"
        strokeDasharray={`${(pct / 100) * c} ${c}`} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle" fontSize="20" fontWeight="800" fill="var(--color-text)">{pct}%</text>
      {label && <text x="50%" y="66%" textAnchor="middle" fontSize="9" fill="var(--color-text-muted)">{label}</text>}
    </svg>
  );
}
