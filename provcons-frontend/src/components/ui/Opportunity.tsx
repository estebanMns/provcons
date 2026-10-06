import { Badge } from "./Badge";
import { Icon } from "./Icon";
import { Score } from "./Score";

interface OpportunityProps { name: string; company: string; value: string; score: number; tags: string[] }

export function Opportunity({ name, company, value, score, tags }: OpportunityProps) {
  return (
    <button className="opportunity-row">
      <Score value={score} compact />
      <div className="op-main">
        <strong>{name}</strong><span>{company}</span>
        <div>{tags.map((tag) => <Badge key={tag} tone="success"><Icon name="check" size={12} /> {tag}</Badge>)}</div>
      </div>
      <div className="op-value"><strong>{value}</strong><span>Valor estimado</span></div>
      <Icon name="chevron" size={18} />
    </button>
  );
}
