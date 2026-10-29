import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'

const tabs = [
  { to: '/', label: '信号', end: true },
  { to: '/history', label: '历史' },
  { to: '/validation', label: '验证' },
  { to: '/rules', label: '规则' },
]

export function Layout({ children, version }: { children: ReactNode; version?: string }) {
  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <small>ETF ROTATION · WEEKLY</small>
          <h1>轮动信号</h1>
        </div>
        {version && <span className="version">{version}</span>}
      </header>

      <nav className="tabs">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => (isActive ? 'active' : '')}>
            {t.label}
          </NavLink>
        ))}
      </nav>

      <main>{children}</main>

      <footer className="foot">
        <p>历史回测不代表未来收益。本应用只提供规则信号，不构成投资建议。</p>
      </footer>
    </div>
  )
}
