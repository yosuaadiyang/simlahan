import React from "react";
import classNames from "classnames";
import type { Choice, ChoiceMap } from "../types";

export const labelOf = (
  choices: ChoiceMap | null | undefined,
  enumName: string,
  value: unknown,
): string => {
  if (value === null || value === undefined || value === "") return "–";
  const found = (choices?.[enumName] || []).find(
    (c: Choice) => c.value === value,
  );
  return found ? found.label : String(value);
};

export const Section: React.FC<{
  title: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, actions, children }) => (
  <section className="acq-section">
    <header className="acq-section__header">
      <h2>{title}</h2>
      {actions && <div className="acq-section__actions">{actions}</div>}
    </header>
    {children}
  </section>
);

export const Stat: React.FC<{
  label: string;
  value: React.ReactNode;
  tone?: "default" | "warning" | "danger" | "success";
  hint?: React.ReactNode;
}> = ({ label, value, tone = "default", hint }) => (
  <div className={classNames("acq-stat", `acq-stat--${tone}`)}>
    <span className="acq-stat__label">{label}</span>
    <strong className="acq-stat__value">{value}</strong>
    {hint && <span className="acq-stat__hint">{hint}</span>}
  </div>
);

export const Progress: React.FC<{ value: number; label?: string }> = ({
  value,
  label,
}) => (
  <div className="acq-progress" title={label}>
    <div className="acq-progress__bar" style={{ width: `${value}%` }} />
    <span className="acq-progress__text">{label || `${value}%`}</span>
  </div>
);

const STATE_TONE: Record<string, string> = {
  overdue: "danger",
  due_soon: "warning",
  upcoming: "default",
  done: "success",
  paid: "success",
  released: "success",
  handed_over: "success",
  validated: "success",
  final: "success",
  agreed: "success",
  objection: "danger",
  consigned: "warning",
  cancelled: "muted",
  excluded: "muted",
  skipped: "muted",
  in_progress: "warning",
};

export const Tag: React.FC<{
  value?: string | null;
  children: React.ReactNode;
}> = ({ value, children }) => (
  <span
    className={classNames(
      "acq-tag",
      `acq-tag--${(value && STATE_TONE[value]) || "default"}`,
    )}
  >
    {children}
  </span>
);

export const Tabs: React.FC<{
  tabs: Array<{ key: string; label: string; badge?: number | null }>;
  active: string;
  onChange: (key: string) => void;
}> = ({ tabs, active, onChange }) => (
  <nav className="acq-tabs" role="tablist">
    {tabs.map((tab) => (
      <button
        key={tab.key}
        type="button"
        role="tab"
        aria-selected={tab.key === active}
        className={classNames("acq-tabs__tab", {
          "is-active": tab.key === active,
        })}
        onClick={() => onChange(tab.key)}
      >
        {tab.label}
        {!!tab.badge && <span className="acq-tabs__badge">{tab.badge}</span>}
      </button>
    ))}
  </nav>
);

export const Empty: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => <p className="acq-empty">{children}</p>;

export const ErrorText: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <p className="acq-error" role="alert">
    {children}
  </p>
);

type ButtonProps = {
  variant?: "primary" | "secondary" | "danger" | "link";
  className?: string;
  type?: "button" | "submit" | "reset";
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "className" | "type">;

export const Button = ({
  variant = "primary",
  className,
  type = "button",
  ...rest
}: ButtonProps) => (
  <button
    type={type}
    className={classNames(
      "acq-button",
      { [`acq-button--${variant}`]: variant !== "primary" },
      className,
    )}
    {...rest}
  />
);

export type Column<T> = {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
};

export function DataTable<T extends Record<string, any>>({
  columns,
  rows,
  onRowClick,
  actions,
  empty = "Belum ada data.",
}: {
  columns: Array<Column<T>>;
  rows: Array<T>;
  onRowClick?: (row: T) => void;
  actions?: (row: T) => React.ReactNode;
  empty?: string;
}) {
  if (!rows.length) return <Empty>{empty}</Empty>;
  return (
    <div className="acq-table-wrapper">
      <table className="acq-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.className}>
                {c.header}
              </th>
            ))}
            {actions && <th className="acq-table__actions" />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={row.id ?? index}
              className={classNames({ "is-clickable": Boolean(onRowClick) })}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((c) => (
                <td key={c.key} className={c.className}>
                  {c.render ? c.render(row) : (row[c.key] ?? "–")}
                </td>
              ))}
              {actions && (
                <td
                  className="acq-table__actions"
                  onClick={(e) => e.stopPropagation()}
                >
                  {actions(row)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
