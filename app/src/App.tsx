import { HashRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { useData } from './lib/useData'
import { HistoryPage } from './pages/HistoryPage'
import { RulesPage } from './pages/RulesPage'
import { SignalPage } from './pages/SignalPage'
import { ValidationPage } from './pages/ValidationPage'

export default function App() {
  const { data, error } = useData()

  if (error) {
    return (
      <div className="app">
        <div className="alert">数据加载失败：{error}</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="app">
        <div className="loading">
          <span className="spinner" />
          正在读取信号…
        </div>
      </div>
    )
  }

  return (
    <HashRouter>
      <Layout version="v2 · 周频">
        <Routes>
          <Route path="/" element={<SignalPage latest={data.latest} meta={data.meta} />} />
          <Route
            path="/history"
            element={<HistoryPage nav={data.nav} meta={data.meta} history={data.history} />}
          />
          <Route path="/validation" element={<ValidationPage meta={data.meta} />} />
          <Route path="/rules" element={<RulesPage meta={data.meta} />} />
        </Routes>
      </Layout>
    </HashRouter>
  )
}
