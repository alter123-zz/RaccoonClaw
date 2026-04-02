import type { ReactNode } from 'react';

type HeroStat = {
  value: ReactNode;
  label: string;
  onClick?: () => void;
  className?: string;
};

export default function PageHero({
  kicker,
  title,
  desc,
  stats,
  actions,
  note,
}: {
  kicker: string;
  title: string;
  desc: string;
  stats?: HeroStat[];
  actions?: ReactNode;
  note?: ReactNode;
}) {
  const hasSide = Boolean((stats && stats.length) || note);
  return (
    <div className={`tpl-hero page-hero ${hasSide ? '' : 'page-hero-no-side'}`.trim()}>
      <div className="tpl-hero-main">
        <div className="tpl-hero-kicker">{kicker}</div>
        <div className="tpl-hero-title">{title}</div>
        {desc ? <div className="tpl-hero-desc">{desc}</div> : null}
        {actions ? <div className="page-hero-actions">{actions}</div> : null}
      </div>
      {hasSide ? (
        <div className="tpl-hero-side">
          {(stats || []).map((stat) => (
            <div
              className={`tpl-hero-stat ${stat.onClick ? 'is-interactive' : ''} ${stat.className || ''}`.trim()}
              key={stat.label}
              onClick={stat.onClick}
              role={stat.onClick ? 'button' : undefined}
              tabIndex={stat.onClick ? 0 : undefined}
              onKeyDown={
                stat.onClick
                  ? (event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        stat.onClick?.();
                      }
                    }
                  : undefined
              }
            >
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </div>
          ))}
          {note ? <div className="tpl-hero-note">{note}</div> : null}
        </div>
      ) : null}
    </div>
  );
}
