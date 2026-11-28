import { describe, expect, it } from 'vitest'

import { actionLabel, countByType, filterDispatchCodes, matchesGlossarySearch } from './dispatchCodes'

const code = (overrides = {}) => ({
  id: 1,
  code: '6.1',
  asset_type: 'Patente',
  official_description: 'Exigência Técnica - Art. 36 da LPI',
  plain_description: 'O INPI parou o exame e pediu ajustes no pedido.',
  requires_action: true,
  deadline_days: 90,
  ...overrides,
})

describe('actionLabel', () => {
  it('mostra o prazo em dias quando existe', () => {
    expect(actionLabel(code())).toBe('Exige ação · 90 dias')
  })

  it('avisa quando exige ação mas o prazo vem no despacho', () => {
    expect(actionLabel(code({ deadline_days: null }))).toBe('Exige ação · prazo no despacho')
  })

  it('código que não exige ação é informativo', () => {
    expect(actionLabel(code({ requires_action: false, deadline_days: null }))).toBe('Informativo')
  })
})

describe('busca no glossário', () => {
  it('encontra pelo código', () => {
    expect(matchesGlossarySearch(code(), '6.1')).toBe(true)
  })

  it('ignora acentos e maiúsculas no título e na explicação', () => {
    expect(matchesGlossarySearch(code(), 'EXIGENCIA tecnica')).toBe(true)
    expect(matchesGlossarySearch(code(), 'ajustes')).toBe(true)
  })

  it('exige todos os termos digitados', () => {
    expect(matchesGlossarySearch(code(), 'exigência concessão')).toBe(false)
  })

  it('busca vazia mostra tudo', () => {
    expect(matchesGlossarySearch(code(), '  ')).toBe(true)
  })
})

describe('filterDispatchCodes', () => {
  const codes = [
    code(),
    code({ id: 2, code: '16.1', official_description: 'Concessão de Patente', requires_action: false, deadline_days: null }),
    code({ id: 3, code: '730', asset_type: 'Programa de Computador', requires_action: false, deadline_days: null }),
  ]
  const ids = (list) => list.map((item) => item.id)

  it('filtra pelo tipo de ativo', () => {
    expect(ids(filterDispatchCodes(codes, { assetType: 'Programa de Computador' }))).toEqual([3])
  })

  it('pode mostrar só os que exigem ação', () => {
    expect(ids(filterDispatchCodes(codes, { assetType: 'Patente', onlyAction: true }))).toEqual([1])
  })

  it('combina tipo e busca', () => {
    expect(ids(filterDispatchCodes(codes, { assetType: 'Patente', query: 'concessao' }))).toEqual([2])
  })
})

describe('countByType', () => {
  it('conta os códigos de cada tipo', () => {
    expect(countByType([code(), code({ id: 2 }), code({ id: 3, asset_type: 'Programa de Computador' })])).toEqual({
      Patente: 2,
      'Programa de Computador': 1,
    })
  })

  it('funciona com o glossário vazio', () => {
    expect(countByType([])).toEqual({})
  })
})
