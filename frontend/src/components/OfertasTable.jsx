import { useState } from 'react'
import api from '../api'

function CazaBadge({ o }) {
  const estado = o.estado_caza
  if (estado === 'cazando') {
    return (
      <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded font-medium whitespace-nowrap">
        -{o.paso_caza}€/ciclo
      </span>
    )
  }
  if (estado === 'completado') {
    return (
      <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-medium whitespace-nowrap" title="Precio mínimo del competidor detectado">
        Min: {o.precio_minimo_detectado != null ? o.precio_minimo_detectado.toFixed(2) + '€' : '—'}
      </span>
    )
  }
  if (estado === 'abortado') {
    return (
      <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium" title="Llegó a precio_min sin ganar buybox">
        Abortada
      </span>
    )
  }
  return null
}

export default function OfertasTable({ ofertas, onRefresh }) {
  const [editing, setEditing] = useState(null)
  const [values, setValues] = useState({})
  const [cazaModal, setCazaModal] = useState(null)
  const [cazaPaso, setCazaPaso] = useState('20')

  const startEdit = (o) => {
    setEditing(o.id)
    setValues({ precio_min: o.precio_min || '', precio_max: o.precio_max || '' })
  }

  const save = async (id) => {
    try {
      await api.put(`/ofertas/${id}`, {
        precio_min: values.precio_min ? Number(values.precio_min) : null,
        precio_max: values.precio_max ? Number(values.precio_max) : null,
      })
      setEditing(null)
      onRefresh()
    } catch (e) {
      const msg = e.response?.data?.error || 'Error al guardar'
      alert(msg)
    }
  }

  const toggleActivo = async (o) => {
    await api.put(`/ofertas/${o.id}`, { activo: !o.activo })
    onRefresh()
  }

  const abrirCazaModal = (o) => {
    setCazaModal(o)
    setCazaPaso('20')
  }

  const iniciarCaza = async () => {
    if (!cazaModal) return
    try {
      await api.post(`/ofertas/${cazaModal.id}/caza`, { paso_caza: Number(cazaPaso) })
      setCazaModal(null)
      onRefresh()
    } catch (e) {
      alert(e.response?.data?.error || 'Error al iniciar caza')
    }
  }

  const cancelarCaza = async (o) => {
    await api.delete(`/ofertas/${o.id}/caza`)
    onRefresh()
  }

  const cazaActiva = (o) => o.estado_caza === 'cazando'
  const cazaTerminada = (o) => o.estado_caza === 'completado' || o.estado_caza === 'abortado'

  return (
    <>
      <div className="bg-white rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-500">
            <tr>
              <th className="px-4 py-3">Producto</th>
              <th className="px-4 py-3">SKU</th>
              <th className="px-4 py-3 text-right">Precio</th>
              <th className="px-4 py-3 text-right">Min</th>
              <th className="px-4 py-3 text-right">Max</th>
              <th className="px-4 py-3 text-center">Stock</th>
              <th className="px-4 py-3 text-right">Mejor precio</th>
              <th className="px-4 py-3 text-center">Buybox</th>
              <th className="px-4 py-3 text-center">Caza mín.</th>
              <th className="px-4 py-3 text-center">Activo</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {ofertas.map(o => (
              <tr key={o.id} className={!o.activo ? 'opacity-50' : ''}>
                <td className="px-4 py-3 font-medium">{o.producto?.nombre}</td>
                <td className="px-4 py-3 text-gray-500">{o.producto?.sku}</td>
                <td className="px-4 py-3 text-right font-mono">{o.precio_actual?.toFixed(2)}</td>
                <td className="px-4 py-3 text-right">
                  {editing === o.id ? (
                    <input type="number" step="0.01" value={values.precio_min}
                      onChange={e => setValues({ ...values, precio_min: e.target.value })}
                      className="w-24 border rounded px-2 py-1 text-right" />
                  ) : (
                    <span className="font-mono text-gray-500">{o.precio_min?.toFixed(2) || '-'}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {editing === o.id ? (
                    <input type="number" step="0.01" value={values.precio_max}
                      onChange={e => setValues({ ...values, precio_max: e.target.value })}
                      className="w-24 border rounded px-2 py-1 text-right" />
                  ) : (
                    <span className="font-mono text-gray-500">{o.precio_max?.toFixed(2) || '-'}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">{o.stock}</td>
                <td className="px-4 py-3 text-right font-mono">
                  {o.precio_buybox
                    ? <span className={o.tiene_buybox ? 'text-green-600' : 'text-blue-600'}>{o.precio_buybox.toFixed(2)}</span>
                    : <span className="text-gray-300">—</span>
                  }
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`inline-block w-2.5 h-2.5 rounded-full ${o.tiene_buybox ? 'bg-green-500' : 'bg-red-400'}`} />
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex items-center justify-center gap-1.5">
                    <CazaBadge o={o} />
                    {cazaActiva(o) ? (
                      <button onClick={() => cancelarCaza(o)} className="text-xs text-gray-400 hover:text-red-500 hover:underline">
                        Parar
                      </button>
                    ) : (
                      <button
                        onClick={() => abrirCazaModal(o)}
                        className={`text-xs hover:underline ${cazaTerminada(o) ? 'text-gray-400' : 'text-purple-600'}`}
                        title="Descubrir precio mínimo del competidor"
                      >
                        {cazaTerminada(o) ? 'Repetir' : 'Cazar'}
                      </button>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => toggleActivo(o)}
                    className={`w-8 h-5 rounded-full relative transition ${o.activo ? 'bg-green-500' : 'bg-gray-300'}`}>
                    <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${o.activo ? 'left-3.5' : 'left-0.5'}`} />
                  </button>
                </td>
                <td className="px-4 py-3">
                  {editing === o.id ? (
                    <div className="flex gap-1">
                      <button onClick={() => save(o.id)} className="text-green-600 hover:underline text-xs">Guardar</button>
                      <button onClick={() => setEditing(null)} className="text-gray-400 hover:underline text-xs">Cancelar</button>
                    </div>
                  ) : (
                    <button onClick={() => startEdit(o)} className="text-blue-600 hover:underline text-xs">Editar</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {ofertas.length === 0 && <p className="text-center text-gray-400 py-8">Sin ofertas</p>}
      </div>

      {cazaModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setCazaModal(null)}>
          <div className="bg-white rounded-xl shadow-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-gray-800 mb-0.5">Cazar precio mínimo del competidor</h3>
            <p className="text-sm text-gray-500 mb-4 truncate">{cazaModal.producto?.nombre}</p>

            <div className="bg-purple-50 rounded-lg p-3 mb-4 text-xs text-purple-700 space-y-1">
              <p>Cada 15 min, si no tenemos la buybox, el repricer bajará el precio en el paso configurado.</p>
              <p>Cuando ganemos la buybox, el competidor habrá llegado a su mínimo y subiremos a <strong>mínimo_competidor − 0,01€</strong>.</p>
            </div>

            <label className="block text-sm font-medium text-gray-700 mb-1">
              Paso de bajada (€ por ciclo)
            </label>
            <input
              type="number"
              step="1"
              min="0.01"
              value={cazaPaso}
              onChange={e => setCazaPaso(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 mb-1"
              autoFocus
            />
            <p className="text-xs text-gray-400 mb-4">
              Precio actual: <strong>{cazaModal.precio_actual?.toFixed(2)}€</strong>
              {cazaModal.precio_min != null && <> · Mínimo propio: <strong>{cazaModal.precio_min.toFixed(2)}€</strong></>}
            </p>

            <div className="flex gap-2">
              <button
                onClick={iniciarCaza}
                disabled={!cazaPaso || Number(cazaPaso) <= 0}
                className="flex-1 bg-purple-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Iniciar caza
              </button>
              <button
                onClick={() => setCazaModal(null)}
                className="flex-1 border rounded-lg py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
