import { useState } from 'react'

import { ListState } from '../components/ListState'
import { PageHeader } from '../components/PageHeader'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Chip } from '../components/ui/Chip'
import { TextField } from '../components/ui/Field'
import { Tabs } from '../components/ui/Tabs'
import { useDispatchCodes } from '../hooks/useDispatchCodes'
import { actionLabel, countByType, filterDispatchCodes } from '../utils/dispatchCodes'

const TYPE_TABS = [
  { id: 'Patente', label: 'Patentes' },
  { id: 'Programa de Computador', label: 'Programas de computador' },
]

/** Glossário de despachos: o que cada código da RPI significa, se exige ação e qual o prazo. */
export function GlossaryPage() {
  const { codes, loading, error, reload } = useDispatchCodes()
  const [assetType, setAssetType] = useState('Patente')
  const [onlyAction, setOnlyAction] = useState(false)
  const [query, setQuery] = useState('')

  const counts = countByType(codes)
  const ofType = counts[assetType] ?? 0
  const visible = filterDispatchCodes(codes, { assetType, onlyAction, query })
  const filtering = onlyAction || query.trim() !== ''

  function clearFilters() {
    setOnlyAction(false)
    setQuery('')
  }

  return (
    <>
      <PageHeader
        eyebrow="Glossário"
        title="Glossário de despachos"
        subtitle="O que cada despacho publicado pelo INPI na RPI significa, em linguagem simples, e se exige alguma providência."
      />

      <Card flush>
        <div className="flex flex-wrap items-end gap-3 px-6 pt-1 pb-4">
          <Tabs
            label="Tipo de ativo"
            active={assetType}
            onChange={setAssetType}
            items={TYPE_TABS.map((tab) => ({ ...tab, count: counts[tab.id] ?? 0 }))}
          />
          <Chip on={onlyAction} onChange={setOnlyAction}>
            Só os que exigem ação
          </Chip>
          <span className="hidden flex-1 lg:block" />
          <TextField
            label="Buscar no glossário"
            type="search"
            icon="busca"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Código ou palavra, ex.: 6.1 ou exigência"
            className="w-full sm:w-80"
          />
        </div>

        {loading || error || visible.length === 0 ? (
          <ListState
            loading={loading}
            error={error}
            onRetry={reload}
            loadingLabel="Carregando o glossário…"
            empty={
              codes.length === 0
                ? {
                    icon: 'glossario',
                    title: 'O glossário ainda está vazio',
                    description: 'Peça à equipe técnica para carregar os códigos de despacho do INPI.',
                  }
                : {
                    title: 'Nenhum código encontrado',
                    description: 'Revise a busca ou os filtros.',
                    action: filtering && (
                      <Button size="sm" variant="ghost" icon="fechar" onClick={clearFilters}>
                        Limpar filtros
                      </Button>
                    ),
                  }
            }
          />
        ) : (
          <ul className="divide-y divide-line px-6">
            {visible.map((item) => (
              <li key={item.id} className="flex flex-col gap-2 py-4 sm:flex-row sm:gap-5">
                <span className="w-24 flex-none pt-0.5 font-mono text-sm font-bold text-primary-ink">{item.code}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="min-w-0 text-sm leading-5 font-bold text-ink">{item.official_description}</p>
                    <Badge tone={item.requires_action ? 'warning' : 'neutral'} dot={item.requires_action}>
                      {actionLabel(item)}
                    </Badge>
                  </div>
                  <p className="mt-1 type-body-sm text-ink-muted">{item.plain_description}</p>
                </div>
              </li>
            ))}
          </ul>
        )}

        {!loading && !error && ofType > 0 && (
          <p className="px-6 pt-4 pb-1 type-body-sm text-ink-muted">
            Mostrando {visible.length} de {ofType}
          </p>
        )}
      </Card>
    </>
  )
}
