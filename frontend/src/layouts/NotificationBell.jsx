import { NavLink } from 'react-router-dom'

import { Icon } from '../components/ui/Icon'
import { useUnreadCount } from '../hooks/useUnreadCount'
import { unreadBadgeText, unreadLabel } from '../utils/alerts'

/** Sininho da barra superior: leva à tela de alertas e mostra quantos não foram lidos (US12). */
export function NotificationBell() {
  const count = useUnreadCount()
  const badge = unreadBadgeText(count)
  const label = unreadLabel(count)

  return (
    <NavLink
      to="/alertas"
      aria-label={label}
      title={label}
      className={({ isActive }) =>
        `relative inline-flex size-[42px] flex-none items-center justify-center rounded-md border border-line hover:bg-surface-muted ${
          isActive ? 'bg-primary-soft text-primary-ink' : 'text-ink-muted'
        }`
      }
    >
      <Icon name="sino" />
      {badge && (
        <span
          aria-hidden
          className="absolute -top-1.5 -right-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-critical px-1 text-[11px] leading-none font-bold text-on-primary ring-2 ring-surface"
        >
          {badge}
        </span>
      )}
    </NavLink>
  )
}
