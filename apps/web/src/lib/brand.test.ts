import { describe, expect, it } from 'vitest'

import { BRAND, PRODUCT_NAME } from './brand'
import indexCss from '../index.css?raw'
import tokensCss from '../styles/tokens.css?raw'

describe('brand tokens', () => {
  it('uses the exact UI design system palette', () => {
    expect(BRAND.oat).toBe('#F4F0E6')
    expect(BRAND.forest).toBe('#21483B')
    expect(BRAND.terracotta).toBe('#D9844B')
    expect(BRAND.paper).toBe('#FFFFFF')
    expect(BRAND.charcoal).toBe('#1C1B18')
    expect(BRAND.inkSoft).toBe('#5F5C53')
    expect(BRAND.line).toBe('#D9D3C4')
    expect(BRAND.lineStrong).toBe('#B9B2A0')
    expect(BRAND.oatDeep).toBe('#EAE4D5')
  })

  it('spells out the full product name without a monogram', () => {
    expect(PRODUCT_NAME).toBe(
      'Smart Food Supply Chain & Surplus Redistribution System',
    )
  })

  it('maps the palette and typography into Tailwind tokens', () => {
    expect(tokensCss).toMatch(/--oat:\s*#f4f0e6;/i)
    expect(tokensCss).toMatch(/--forest:\s*#21483b;/i)
    expect(tokensCss).toMatch(/--terracotta:\s*#d9844b;/i)
    expect(tokensCss).toContain('--primary: var(--forest)')
    expect(tokensCss).toContain('--font-sans: "Manrope Variable"')
    expect(tokensCss).toContain('--font-heading: "Fraunces Variable"')
    expect(indexCss).toContain('@fontsource-variable/manrope')
    expect(indexCss).toContain('@fontsource-variable/fraunces')
  })
})
