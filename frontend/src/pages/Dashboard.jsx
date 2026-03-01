import { useState, useEffect, useRef } from 'react'
import api from '../api'
import StatsCards from '../components/StatsCards'
import LogsPanel from '../components/LogsPanel'

export default function Dashboard({ selectedMp }) {
  const [stats, setStats] = useState({ total_ofertas: 0, pct_buybox: 0, cambios_hoy: 0, alertas: 0 })
  const [logs, setLogs] = useState([])
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(null) // { marketplace, procesadas, total, cambios }
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef(null)
  const startTimeRef = useRef(null)

  const load = () => {
    api.get('/historico/stats').then(r => setStats(r.data))
    const params = selectedMp ? { marketplace_id: selectedMp, limit: 10 } : { limit: 10 }
    api.get('/historico', { params }).then(r => setLogs(r.data))
  }

  useEffect(load, [selectedMp])

  // Limpiar timer al desmontar
  useEffect(() => () => clearInterval(timerRef.current), [])

  const runRepricer = async () => {
    setRunning(true)
    setProgress({ marketplace: '', procesadas: 0, total: 0, cambios: 0 })
    setElapsed(0)
    startTimeRef.current = Date.now()

    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000))
    }, 1000)

    try {
      // Usamos fetch nativo porque Axios no soporta streaming
      const resp = await fetch('/api/repricer/run', {
        method: 'POST',
        credentials: 'include',
      })

      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // la última línea puede estar incompleta
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const event = JSON.parse(line)
            if (event.type === 'start') {
              setProgress({ marketplace: event.marketplace, procesadas: 0, total: 0, cambios: 0 })
            } else if (event.type === 'total') {
              setProgress(prev => ({ ...prev, marketplace: event.marketplace, total: event.total }))
            } else if (event.type === 'progress') {
              setProgress({
                marketplace: event.marketplace,
                procesadas: event.procesadas,
                total: event.total,
                cambios: event.cambios,
              })
            }
          } catch {
            // línea JSON inválida, ignorar
          }
        }
      }
    } catch (e) {
      console.error('Error ejecutando repricer:', e)
    } finally {
      clearInterval(timerRef.current)
      setRunning(false)
      load()
    }
  }

  const pct = progress && progress.total > 0
    ? Math.min(100, Math.round((progress.procesadas / progress.total) * 100))
    : null

  const formatElapsed = (s) => {
    if (s < 60) return `${s}s`
    return `${Math.floor(s / 60)}m ${s % 60}s`
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Dashboard</h2>
        <button
          onClick={runRepricer}
          disabled={running}
          className="bg-gray-900 text-white px-4 py-2 rounded text-sm hover:bg-gray-800 disabled:opacity-50"
        >
          {running ? 'Ejecutando...' : 'Ejecutar repricer'}
        </button>
      </div>

      {/* Panel de progreso — solo visible mientras ejecuta */}
      {running && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-gray-700">
              {/* Spinner */}
              <svg className="animate-spin h-4 w-4 text-gray-500 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>

              {/* Texto de estado */}
              <span>
                {progress?.marketplace && (
                  <span className="font-medium text-gray-900 mr-1">{progress.marketplace}</span>
                )}
                {progress?.total > 0
                  ? <>{progress.procesadas} / {progress.total} ofertas</>
                  : 'Obteniendo ofertas de Mirakl...'}
                {progress?.cambios > 0 && (
                  <span className="ml-2 text-green-600 font-medium">· {progress.cambios} cambio{progress.cambios !== 1 ? 's' : ''}</span>
                )}
              </span>
            </div>

            {/* Tiempo transcurrido */}
            <span className="tabular-nums text-gray-400 text-xs">{formatElapsed(elapsed)}</span>
          </div>

          {/* Barra de progreso */}
          <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
            {pct !== null ? (
              /* Barra determinista */
              <div
                className="bg-gray-800 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            ) : (
              /* Barra indeterminada animada mientras obtenemos el total */
              <div className="h-1.5 relative">
                <div className="absolute inset-0 bg-gray-300 rounded-full animate-pulse" />
              </div>
            )}
          </div>
        </div>
      )}

      <StatsCards stats={stats} />
      <div>
        <h3 className="text-sm font-medium text-gray-500 mb-3">Cambios recientes</h3>
        <LogsPanel logs={logs} />
      </div>
    </div>
  )
}
