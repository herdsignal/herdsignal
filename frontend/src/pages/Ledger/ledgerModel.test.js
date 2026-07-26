import { describe, expect, it } from 'vitest'
import { entryPayload } from './ledgerModel'

describe('ledgerModel', () => {
  it('builds a server-authoritative trade payload', () => {
    expect(entryPayload({
      entryType: 'BUY',
      ticker: ' nvda ',
      occurredOn: '2026-01-02',
      quantity: '2.5',
      unitPrice: '100',
      amount: '',
      fee: '1.25',
      note: ' first lot ',
    })).toEqual({
      entryType: 'BUY',
      ticker: 'NVDA',
      occurredOn: '2026-01-02',
      quantity: 2.5,
      unitPrice: 100,
      fee: 1.25,
      note: 'first lot',
    })
  })

  it('does not attach a ticker to deposits', () => {
    expect(entryPayload({
      entryType: 'DEPOSIT',
      ticker: 'NVDA',
      occurredOn: '2026-01-02',
      amount: '500',
      note: '',
    })).toEqual({
      entryType: 'DEPOSIT',
      occurredOn: '2026-01-02',
      amount: 500,
      note: null,
    })
  })
})
