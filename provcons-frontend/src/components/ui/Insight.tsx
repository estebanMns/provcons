import type { IconName } from "@/lib/types";
import { Icon } from "./Icon";

export function Insight({ icon, label, value, note, tone }: { icon: IconName; label: string; value: string; note: string; tone: string }) {
  return (
    <div className="insight">
      <span className={`insight-icon ${tone}`}><Icon name={icon} /></span>
      <div><small>{label}</small><strong>{value}</strong><p><Icon name="check" size={12} /> {note}</p></div>
    </div>
  );
}
