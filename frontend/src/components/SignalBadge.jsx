import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export default function SignalBadge({ action, confidence }) {
  const map = {
    BUY:  { cls: "badge-buy",  Icon: TrendingUp,  label: "BUY" },
    SELL: { cls: "badge-sell", Icon: TrendingDown, label: "SELL" },
    HOLD: { cls: "badge-hold", Icon: Minus,        label: "HOLD" },
  };
  const { cls, Icon, label } = map[action] || map.HOLD;

  return (
    <div className="signal-badge-wrap">
      <span className={`signal-badge ${cls}`}>
        <Icon size={15} strokeWidth={2.5} />
        {label}
      </span>
      {confidence != null && <ConfidenceRing value={confidence} action={action} />}
    </div>
  );
}

function ConfidenceRing({ value, action }) {
  const size   = 52;
  const stroke = 4;
  const r      = (size - stroke) / 2;
  const circ   = 2 * Math.PI * r;
  const fill   = ((value || 0) / 100) * circ;
  const color  = action === "BUY" ? "#00c896" : action === "SELL" ? "#ff3b5c" : "#f0b90b";

  return (
    <div className="conf-ring" title={`${value}% confidence`}>
      <svg width={size} height={size}>
        {/* Background track */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke="var(--bg-input)"
          strokeWidth={stroke}
        />
        {/* Fill arc */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${fill} ${circ}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `drop-shadow(0 0 4px ${color})`, transition: "stroke-dasharray 0.6s ease" }}
        />
      </svg>
      <span className="conf-ring-val" style={{ color }}>{value}%</span>
    </div>
  );
}
