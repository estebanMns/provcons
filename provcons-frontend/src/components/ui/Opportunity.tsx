import { Badge } from "./Badge";
import { Icon } from "./Icon";
import { Score } from "./Score";

interface OpportunityProps { name: string; company: string; value: string; score: number; tags: string[]; onClick?: () => void }

export function Opportunity({ name, company, value, score, tags, onClick }: OpportunityProps) {
  const content = (
    <>
      <Score value={score} compact />
      <div className="op-main">
        <strong>{name}</strong><span>{company}</span>
        <div>{tags.map((tag) => <Badge key={tag} tone="success"><Icon name="check" size={12} /> {tag}</Badge>)}</div>
      </div>
      <div className="op-value"><strong>{value}</strong><span>Valor estimado</span></div>
      {onClick ? <Icon name="chevron" size={18} /> : <span />}
    </>
  );
  // Solo es un botón si hace algo; si no, una fila informativa
  return onClick
    ? <button className="opportunity-row" onClick={onClick}>{content}</button>
    : <div className="opportunity-row" style={{ cursor: "default" }}>{content}</div>;
}
