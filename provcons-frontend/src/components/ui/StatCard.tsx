import type { IconName } from "@/lib/types";
import { Icon } from "./Icon";

export function StatCard({ label, value, detail, icon, tone = "blue" }: { label: string; value: string; detail: string; icon: IconName; tone?: string }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon stat-${tone}`}><Icon name={icon} /></div>
      <div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
    </div>
  );
}
