import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export function YearlyBars({ data }: { data: { year: number; ret: number }[] }) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 6, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#e6e2d8" vertical={false} />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 11, fill: '#8a8578' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#8a8578' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            width={44}
          />
          <ReferenceLine y={0} stroke="#c9c3b6" />
          <Tooltip
            cursor={{ fill: 'rgba(0,0,0,.03)' }}
            contentStyle={{
              borderRadius: 12,
              border: '1px solid #e6e2d8',
              fontSize: 12,
              boxShadow: '0 8px 24px rgba(0,0,0,.06)',
            }}
            formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, '收益']}
          />
          <Bar dataKey="ret" radius={[3, 3, 0, 0]}>
            {data.map((d) => (
              <Cell key={d.year} fill={d.ret >= 0 ? '#b23a2f' : '#2f6b57'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
