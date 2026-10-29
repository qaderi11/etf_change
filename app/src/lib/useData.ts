import { useEffect, useState } from 'react'
import type { AppData } from './types'

const BASE = import.meta.env.BASE_URL

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}data/${path}`, { cache: 'no-cache' })
  if (!res.ok) throw new Error(`${path} 加载失败 (${res.status})`)
  return (await res.json()) as T
}

export function useData() {
  const [data, setData] = useState<AppData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    Promise.all([
      getJson<AppData['latest']>('latest.json'),
      getJson<AppData['nav']>('nav.json'),
      getJson<AppData['history']>('history.json'),
      getJson<AppData['meta']>('meta.json'),
    ])
      .then(([latest, nav, history, meta]) => {
        if (alive) setData({ latest, nav, history, meta })
      })
      .catch((e: Error) => {
        if (alive) setError(e.message)
      })
    return () => {
      alive = false
    }
  }, [])

  return { data, error }
}
