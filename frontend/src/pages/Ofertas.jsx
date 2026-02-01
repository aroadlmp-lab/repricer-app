import { useState, useEffect } from 'react'
import api from '../api'
import OfertasTable from '../components/OfertasTable'

const FILTERS = [
  { key: 'todas', label: 'Todas' },
  { key: 'activas', label: 'Activas' },
  { key: 'sin_buybox', label: 'Sin buybox' },
]

export default function Ofertas({ selectedMp }) {
  const [ofertas, setOfertas] = useState([])
  const [filtro, setFiltro] = useState('todas')

  const load = () => {
    const params = selectedMp ? { marketplace_id: selectedMp } : {}
    api.get('/ofertas', { params }).then(r => setOfertas(r.data))
  }

  useEffect(load, [selectedMp])

  const sorted = [...ofertas].sort((a, b) => (b.activo ? 1 : 0) - (a.activo ? 1 : 0))

  const filtered = sorted.filter(o => {
    if (filtro === 'activas') return o.activo
    if (filtro === 'sin_buybox') return !o.tiene_buybox
    return true
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Ofertas</h2>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setFiltro(f.key)}
              className={`px-3 py-1 text-sm rounded-md transition ${
                filtro === f.key
                  ? 'bg-white shadow text-gray-900 font-medium'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <OfertasTable ofertas={filtered} onRefresh={load} />
    </div>
  )
}
