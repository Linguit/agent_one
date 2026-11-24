import { expect, expectTypeOf, it } from 'vitest'
import { ACTIVE_ALERTS_PATH, ERROR_CATALOG } from '../src/index'
import type { ActiveAlert, ActiveAlertsResponse } from '../src/index'

it('定义标准告警 items，不包含 provider 状态集合', () => {
  expect(ACTIVE_ALERTS_PATH).toBe('/aiops/alerts/active')
  expect(ERROR_CATALOG.AIOPS_ALERTS_UNAVAILABLE.httpStatus).toBe(503)
  expect(ERROR_CATALOG.AUTH_UNAUTHORIZED.httpStatus).toBe(401)
  expect(ERROR_CATALOG.AUTH_FORBIDDEN.httpStatus).toBe(403)
  expectTypeOf<Extract<ActiveAlertsResponse, { ok: true }>['data']>()
    .toEqualTypeOf<{ items: ActiveAlert[] }>()
  expectTypeOf<ActiveAlert['source']>().toEqualTypeOf<string>()
  expectTypeOf<ActiveAlert['status']>()
    .toEqualTypeOf<'pending' | 'firing' | 'active' | 'suppressed' | 'unprocessed'>()
})
