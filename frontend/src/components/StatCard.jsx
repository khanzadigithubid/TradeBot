export default function StatCard({ title, value, sub, color, icon: Icon }) {
  return (
    <div className={`stat-card ${color || ""}`}>
      <div className="stat-icon-wrap">
        {Icon && <Icon size={20} strokeWidth={1.8} />}
      </div>
      <div className="stat-content">
        <div className="stat-title">{title}</div>
        <div className="stat-value">{value ?? "—"}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}
