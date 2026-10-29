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

export function DrawdownChart({
  data,
  stepMonths = 0,
}: {
  data: { date: string; dd: number }[]
  stepMonths?: number
}) {
  const ticks = useMemo(() => ticksOf(data, stepMonths), [data, stepMonths])
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 8, right: 6, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a12a22" stopOpacity={0.05} />
              <stop offset="100%" stopColor="#a12a22" stopOpacity={0.22} />
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
            labelFormatter={(v) => String(v).slice(0, 7).replace('-', '/')}
            formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, '回撤']}
          />
          <Area type="monotone" dataKey="dd" stroke="#a12a22" strokeWidth={1.5} fill="url(#ddFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
