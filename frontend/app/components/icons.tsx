// Minimal hairline icon set — no icon library, no emoji.
// Consistent 1.5px stroke, 20x20 viewBox, matches the institutional register.

type IconProps = { className?: string };

const base = {
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function SearchIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="8.5" cy="8.5" r="5.25" />
      <path d="M16.5 16.5l-3.6-3.6" />
    </svg>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M4 10.5l3.8 3.8L16 6" />
    </svg>
  );
}

export function AlertIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M10 3.2 L17.3 16.4 H2.7 Z" />
      <path d="M10 8.2v3.4" />
      <circle cx="10" cy="14.1" r="0.3" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function UserIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="10" cy="6.7" r="3.1" />
      <path d="M3.6 17c0.9-3.4 3.4-5.1 6.4-5.1s5.5 1.7 6.4 5.1" />
    </svg>
  );
}

export function DocumentIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M5.5 2.8h6.2l3 3v11.4h-9.2z" />
      <path d="M11.7 2.8v3h3" />
      <path d="M7.3 10.4h5.4M7.3 13.2h5.4" />
    </svg>
  );
}

export function ArrowRightIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M3.5 10h13" />
      <path d="M11.5 5.2 16.5 10l-5 4.8" />
    </svg>
  );
}

export function DotIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" className={className}>
      <circle cx="10" cy="10" r="3.5" fill="currentColor" />
    </svg>
  );
}

export function SpinIcon({ className }: IconProps) {
  return (
    <svg
      {...base}
      className={className}
      style={{ animation: "spin 900ms linear infinite" }}
    >
      <path d="M10 3.2a6.8 6.8 0 1 0 6.8 6.8" />
    </svg>
  );
}

export function CalendarIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="3" y="4.2" width="14" height="12.6" rx="0.5" />
      <path d="M3 8h14" />
      <path d="M6.6 2.4v3.2M13.4 2.4v3.2" />
    </svg>
  );
}

export function PinIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M10 17.3S15.4 12 15.4 8.1a5.4 5.4 0 1 0-10.8 0C4.6 12 10 17.3 10 17.3z" />
      <circle cx="10" cy="8.1" r="1.9" />
    </svg>
  );
}
