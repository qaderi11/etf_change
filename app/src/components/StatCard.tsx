import type { Level } from '../lib/metrics'

export function Chip({ text, level = 'neutral' }: { text: string; level?: Level | 'neutral' }) {
  return <span className={`chip ${level}`}>{text}</span>
}

export function StatCard({
  label,
  value,
  sub,
  level = 'neutral',
}: {
  label: string
  value: string
  sub?: string
  level?: Level | 'neutral'
}) {
  return (
    <div className={`stat ${level}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}
