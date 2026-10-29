import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface RetPoint {
  date: string
  ret: number
}

const fmtDate = (iso: string) => iso.slice(0, 7).replace('-', '/')

function ticksOf(data: { date: string }[], stepMonths: number): string[] {
  const out: string[] = []
  let lastKey = ''
  for (const p of data) {
    const key = stepMonths > 0 ? p.date.slice(0, 7) : p.date.slice(0, 4)
    if (key === lastKey) continue
    lastKey = key
    if (stepMonths > 0) {
      const m = Number(key.slice(5, 7))
      if ((m - 1) % stepMonths === 0) out.push(p.date)
    } else {
      const y = Number(key.slice(0, 4))
      if (y % 2 === 0) out.push(p.date)
    }
  }
  return out
}

export function NavChart({ data, stepMonths = 0 }: { data: RetPoint[]; stepMonths?: number }) {
  const ticks = useMemo(() => ticksOf(data, stepMonths), [data, stepMonths])
  const { domain, yticks } = useMemo(() => {
    if (!data.length) return { domain: [-0.01, 0.01] as [number, number], yticks: [-0.01, 0, 0.01] }
    const vals = data.map((d) => d.ret)
    const lo = Math.min(0, ...vals)
    const hi = Math.max(0, ...vals)
    const span = hi - lo || 1
    const lower = lo < -0.005 ? lo - span * 0.01 : 0
    const upper = hi + span * 0.03
    const n = 4
    const step = (upper - lower) / n
    const yticks = Array.from({ length: n + 1 }, (_, i) => lower + step * i)
    return { domain: [lower, upper] as [number, number], yticks }
  }, [data])

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data} margin={{ top: 8, right: 6, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="navFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#b23a2f" stopOpacity={0.22} />
              <stop offset="100%" stopColor="#b23a2f" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e6e2d8" vertical={false} />
          <XAxis
            dataKey="date"
            ticks={ticks}
            tickFormatter={(v: string) =>
              stepMonths > 0 ? `${Number(v.slice(5, 7))}月` : v.slice(2, 4)
            }
            tick={{ fontSize: 11, fill: '#8a8578' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={domain}
            ticks={yticks}
            tick={{ fontSize: 11, fill: '#8a8578' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            width={48}
          />
          <ReferenceLine y={0} stroke="#c9c3b6" />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: '1px solid #e6e2d8',
              fontSize: 12,
              boxShadow: '0 8px 24px rgba(0,0,0,.06)',
            }}
            labelFormatter={(v) => fmtDate(String(v))}
            formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, '区间收益']}
          />
          <Area type="monotone" dataKey="ret" stroke="#b23a2f" strokeWidth={2} fill="url(#navFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
