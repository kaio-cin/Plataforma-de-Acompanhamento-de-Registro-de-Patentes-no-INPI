import { useState } from 'react'

import { ListState } from '../components/ListState'
import { PageHeader } from '../components/PageHeader'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Icon } from '../components/ui/Icon'
import { Tabs } from '../components/ui/Tabs'
import { useAlerts } from '../hooks/useAlerts'
import { ALERT_TABS, countAlertsByTab, deadlineInfo, filterAlerts } from '../utils/alerts'
import { formatDate, todayIso } from '../utils/format'

const EMPTY_BY_TAB = {
  'nao-lidos': { icon: 'ok', title: 'Nenhum alerta não lido', description: 'Você está em dia com os despachos da RPI.' },
  acao: { icon: 'ok', title: 'Nenhum alerta que exige ação', description: 'Nenhum despacho pede providência no momento.' },
}

/** Alertas do usuário (US12): despachos da RPI nos processos que ele acompanha, com prazo em destaque. */
export function AlertsPage() {
  const { alerts, loading, error, reload, markAsRead } = useAlerts()
  const [tab, setTab] = useState('todos')
  const [marking, setMarking] = useState({})
  const [itemErrors, setItemErrors] = useState({})

  const counts = countAlertsByTab(alerts)
  const visible = filterAlerts(alerts, tab)
  const today = todayIso()

  async function handleMarkAsRead(id) {
    setMarking((current) => ({ ...current, [id]: true }))
    setItemErrors((current) => ({ ...current, [id]: null }))
    try {
      await markAsRead(id)
    } catch (err) {
      setItemErrors((current) => ({ ...current, [id]: err.message }))
    } finally {
      setMarking((current) => ({ ...current, [id]: false }))
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Alertas"
        title="Alertas"
        subtitle="Despachos publicados pelo INPI na RPI nos processos que você acompanha, com o prazo de cada providência."
      />

      <Card flush>
        <div className="flex flex-wrap items-end gap-3 px-6 pt-1 pb-4">
          <Tabs
            label="Filtrar alertas"
            active={tab}
            onChange={setTab}
            items={ALERT_TABS.map((item) => ({ ...item, count: counts[item.id] }))}
          />
        </div>

        {loading || error || visible.length === 0 ? (
          <ListState
            loading={loading}
            error={error}
            onRetry={reload}
            loadingLabel="Carregando alertas…"
            empty={
              alerts.length === 0
                ? {
                    icon: 'sino',
                    title: 'Nenhum alerta por enquanto',
                    description: 'Quando a RPI publicar um despacho de um processo seu, ele aparece aqui.',
                  }
                : {
                    ...EMPTY_BY_TAB[tab],
                    action: (
                      <Button size="sm" variant="ghost" onClick={() => setTab('todos')}>
                        Ver todos
                      </Button>
                    ),
                  }
            }
          />
        ) : (
          <ul className="divide-y divide-line px-6">
            {visible.map((alert) => {
              const deadline = deadlineInfo(alert, today)
              const urgent = deadline.tone === 'critical' || deadline.tone === 'warning'
              return (
                <li key={alert.id} className="flex flex-col gap-3 py-4 sm:flex-row sm:gap-5">
                  <div className="flex w-24 flex-none items-center gap-2 pt-0.5">
                    <span
                      className={`size-2 flex-none rounded-full ${alert.is_read ? 'bg-transparent' : 'bg-primary'}`}
                      aria-hidden
                    />
                    <span className="font-mono text-sm font-bold text-primary-ink">{alert.dispatch_code}</span>
                    {!alert.is_read && <span className="sr-only">Não lido</span>}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className={`min-w-0 text-sm leading-5 ${alert.is_read ? 'font-semibold text-ink-muted' : 'font-bold text-ink'}`}>
                        {alert.dispatch_description}
                      </p>
                      <Badge tone={deadline.tone} dot={urgent}>
                        {deadline.label}
                      </Badge>
                    </div>
                    {alert.dispatch_plain_description && (
                      <p className="mt-1 type-body-sm text-ink-muted">{alert.dispatch_plain_description}</p>
                    )}
                    {/* Quando a rota /ativos/:id existir, o título vira <Link to={assetPath(alert.asset_id)}>. */}
                    <p className="mt-2 type-caption text-ink-muted">
                      <span className="font-bold text-ink">{alert.asset_title}</span>
                      {' · '}
                      <span className="font-mono">{alert.process_number}</span>
                      {' · '}
                      publicado na RPI de {formatDate(alert.publication_date)}
                    </p>
                    {itemErrors[alert.id] && (
                      <p role="alert" className="mt-1 type-caption text-critical">
                        {itemErrors[alert.id]}
                      </p>
                    )}
                  </div>

                  <div className="flex-none sm:pt-0.5">
                    {alert.is_read ? (
                      <span className="inline-flex h-[34px] items-center gap-1.5 px-3 type-caption text-ink-subtle">
                        <Icon name="check" size={14} />
                        Lido
                      </span>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        icon="check"
                        loading={Boolean(marking[alert.id])}
                        onClick={() => handleMarkAsRead(alert.id)}
                      >
                        Marcar como lido
                      </Button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}

        {!loading && !error && alerts.length > 0 && (
          <p className="px-6 pt-4 pb-1 type-body-sm text-ink-muted">
            Mostrando {visible.length} de {alerts.length}
          </p>
        )}
      </Card>
    </>
  )
}
