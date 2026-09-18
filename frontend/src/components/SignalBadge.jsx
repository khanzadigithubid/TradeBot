import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export default function SignalBadge({ action, confidence }) {
  const map = {
    BUY:  { cls: "badge-buy",  Icon: TrendingUp,   label: "BUY" },
    SELL: { cls: "badge-sell", Icon: TrendingDown,  label: "SELL" },
    HOLD: { cls: "badge-hold", Icon: Minus,         label: "HOLD" },
  };
  const { cls, Icon, label } = map[action] || map.HOLD;
  return (
    <span className={`signal-badge ${cls}`}>
      <Icon size={14} strokeWidth={2.5} />
      {label} {confidence != null ? `${confidence}%` : ""}
    </span>
  );
}
