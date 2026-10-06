import type { IconName } from "@/lib/types";
import { Icon } from "./Icon";

interface AttentionProps { icon: IconName; title: string; text: string; time: string; onClick?: () => void }

export function Attention({ icon, title, text, time, onClick }: AttentionProps) {
  return (
    <button className="attention-row" onClick={onClick}>
      <span><Icon name={icon} /></span>
      <div><strong>{title}</strong><p>{text}</p><small>{time}</small></div>
      <Icon name="chevron" size={16} />
    </button>
  );
}
