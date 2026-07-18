import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function PageScaffold({
  title,
  description,
  icon: Icon,
  action,
  children,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="management-page">
      <header className="management-header">
        <div className="management-title">
          <span>
            <Icon />
          </span>
          <div>
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
        </div>
        {action}
      </header>
      <div className="management-content">{children}</div>
    </section>
  );
}
