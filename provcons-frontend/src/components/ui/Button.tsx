import type { ReactNode } from "react";
import type { IconName } from "@/lib/types";
import { Icon } from "./Icon";

interface ButtonProps {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  icon?: IconName;
  onClick?: () => void;
  disabled?: boolean;
  wide?: boolean;
}

export function Button({ children, variant = "primary", icon, onClick, disabled, wide = false }: ButtonProps) {
  return (
    <button className={`btn btn-${variant}${wide ? " btn-wide" : ""}`} onClick={onClick} disabled={disabled}>
      {icon && <Icon name={icon} size={18} />}
      <span>{children}</span>
    </button>
  );
}
