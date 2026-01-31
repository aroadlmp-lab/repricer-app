import { useState, useEffect } from 'react'
import api from '../api'
import StatsCards from '../components/StatsCards'
import LogsPanel from '../components/LogsPanel'

export default function Dashboard({ selectedMp }) {
  const [stats, setStats] = useState({ total_ofertas: 0, pct_buybox: 0, cambios_hoy: 0, alertas: 0 })
  const [logs, setLogs] = useState([])
  const [running, setRunning] = useState(false)

  const load = () => {
    api.get('/historico/stats').then(r => setStats(r.data))
    const params = selectedMp ? { marketplace_id: selectedMp, limit: 10 } : { limit: 10 }
    api.get('/historico', { params }).then(r => setLogs(r.data))
  }

  useEffect(load, [selectedMp])

  const runRepricer = async () => {
    setRunning(true)
    try {
      await api.post('/repricer/run')
      load()
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Dashboard</h2>
        <button onClick={runRepricer} disabled={running}
          className="bg-gray-900 text-white px-4 py-2 rounded text-sm hover:bg-gray-800 disabled:opacity-50">
          {running ? 'Ejecutando...' : 'Ejecutar repricer'}
        </button>
      </div>
      <StatsCards stats={stats} />
      <div>
        <h3 className="text-sm font-medium text-gray-500 mb-3">Cambios recientes</h3>
        <LogsPanel logs={logs} />
      </div>
    </div>
  )
}
