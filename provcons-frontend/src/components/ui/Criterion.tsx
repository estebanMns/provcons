import { Icon } from "./Icon";

export function Criterion({ label, value, percent }: { label: string; value: string; percent: number }) {
  return (
    <div className="criterion">
      <div><span>{label}</span><strong><Icon name="check" size={13} /> {value}</strong></div>
      <div className="criterion-bar"><span style={{ width: `${percent}%` }} /></div>
    </div>
  );
}
