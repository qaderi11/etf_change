export const pct = (v: number, digits = 1) =>
  `${v >= 0 ? '' : '-'}${Math.abs(v * 100).toFixed(digits)}%`

export const signedPct = (v: number, digits = 1) =>
  `${v >= 0 ? '+' : '-'}${Math.abs(v * 100).toFixed(digits)}%`

export const num = (v: number, digits = 2) => v.toFixed(digits)

export const cnDate = (iso: string) => {
  const [y, m, d] = iso.split('-')
  return `${y}年${Number(m)}月${Number(d)}日`
}

export const shortDate = (iso: string) => {
  const [, m, d] = iso.split('-')
  return `${Number(m)}/${Number(d)}`
}

export const weekday = (iso: string) =>
  ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][new Date(`${iso}T00:00:00`).getDay()]

export const assetName = (code: string): string =>
  ({
    '159915': '创业板',
    '510300': '沪深300',
    '510500': '中证500',
    '513500': '标普500',
    '518880': '黄金',
    '511010': '国债',
  })[code] ?? code

export const assetColor = (code: string): string =>
  ({
    '159915': '#b23a2f',
    '510300': '#2c5282',
    '510500': '#6b7f99',
    '513500': '#1f7a5c',
    '518880': '#b7791f',
    '511010': '#8a8578',
  })[code] ?? '#8a8578'
