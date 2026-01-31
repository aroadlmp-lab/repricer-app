import { useState, useEffect } from 'react'
import api from '../api'
import LogsPanel from '../components/LogsPanel'

export default function Historico({ selectedMp }) {
  const [logs, setLogs] = useState([])
  const [ejecuciones, setEjecuciones] = useState([])

  useEffect(() => {
    const params = selectedMp ? { marketplace_id: selectedMp } : {}
    api.get('/historico', { params: { ...params, limit: 50 } }).then(r => setLogs(r.data))
    api.get('/historico/ejecuciones', { params }).then(r => setEjecuciones(r.data))
  }, [selectedMp])

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Historico</h2>

      <div>
        <h3 className="text-sm font-medium text-gray-500 mb-3">Ejecuciones</h3>
        <div className="bg-white rounded-lg border divide-y">
          {ejecuciones.map(e => (
            <div key={e.id} className="px-4 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{e.marketplace_nombre}</p>
                <p className="text-xs text-gray-500">{new Date(e.created_at).toLocaleString()}</p>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <span className="text-gray-500">{e.ofertas_procesadas} procesadas</span>
                <span className="text-purple-600">{e.cambios_realizados} cambios</span>
                <span className={`px-2 py-0.5 rounded text-xs ${e.estado === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  {e.estado}
                </span>
              </div>
            </div>
          ))}
          {ejecuciones.length === 0 && <p className="text-center text-gray-400 py-8">Sin ejecuciones</p>}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-500 mb-3">Cambios de precio</h3>
        <LogsPanel logs={logs} />
      </div>
    </div>
  )
}
