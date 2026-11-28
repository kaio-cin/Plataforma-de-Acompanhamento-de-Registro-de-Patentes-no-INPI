/** Regras de apresentação do glossário de despachos. */

import { normalizeText } from './assets'

/** Texto curto sobre ação e prazo, mostrado ao lado de cada código. */
export function actionLabel(code) {
  if (!code.requires_action) return 'Informativo'
  if (code.deadline_days == null) return 'Exige ação · prazo no despacho'
  return `Exige ação · ${code.deadline_days} dias`
}

/** Busca por código ("6.1"), pelo título oficial ou pela explicação, sem acentos nem maiúsculas. */
export function matchesGlossarySearch(code, query) {
  if (!query.trim()) return true
  const terms = normalizeText(query.trim()).split(/\s+/)
  const haystack = normalizeText([code.code, code.official_description, code.plain_description].join(' '))
  return terms.every((term) => haystack.includes(term))
}

/** Aplica os filtros da tela: tipo de ativo, só os que exigem ação e busca. */
export function filterDispatchCodes(codes, { assetType, onlyAction = false, query = '' }) {
  return codes.filter(
    (code) =>
      code.asset_type === assetType && (!onlyAction || code.requires_action) && matchesGlossarySearch(code, query),
  )
}

/** Quantidade de códigos de cada tipo de ativo. */
export function countByType(codes) {
  const counts = {}
  for (const code of codes) counts[code.asset_type] = (counts[code.asset_type] ?? 0) + 1
  return counts
}
