export interface AssetStat {
  code: string
  name: string
  close: number
  ret12: number
  vol63: number
  ma200: number
  dist_ma: number
  eligible: boolean
}

export interface Gate {
  open: boolean
  index: string
  close: number
  ma200: number
}

export interface Latest {
  asof: string
  generated_at: string
  gate: Gate
  assets: AssetStat[]
  leader: string | null
  leader_name: string | null
  equity: number
  weights: Record<string, number>
  reason: string
}

export interface NavPoint {
  date: string
  nav: number
}

export interface SignalRow {
  date: string
  leader: string | null
  leader_name: string
  weights: Record<string, number>
  gate: boolean
}

export interface StartRow {
  start: number
  cagr: number
  sharpe: number
  mdd: number
}

export interface FreqRow {
  freq: string
  cagr: number
  sharpe: number
  mdd: number
  cost: number
}

export interface Meta {
  version: string
  freq: string
  band: number
  params: {
    pool: string[]
    lookback: number
    gate_ma: number
    vol_window: number
    vol_target: number
    gold_sleeve: number
    min_trend: number
    cost: number
  }
  expected: {
    cagr: number
    vol: number
    sharpe: number
    mdd: number
    calmar: number
    start: string
    end: string
  }
  yearly: { year: number; ret: number }[]
  validation: {
    start_sensitivity: StartRow[]
    frequency: FreqRow[]
    t_stat_vs_ew: number
    excess_vs_ew: number
    note: string
  }
  generated_at: string
}

export interface AppData {
  latest: Latest
  nav: NavPoint[]
  history: SignalRow[]
  meta: Meta
}
