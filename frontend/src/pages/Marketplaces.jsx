import { useState, useEffect } from 'react'
import api from '../api'

export default function Marketplaces({ onRefresh }) {
  const [items, setItems] = useState([])
  const [form, setForm] = useState({ nombre: '', url_api: '', api_key: '', shop_id: '', shop_name: '', channel_code: '', ignorar_state_code: false, margen_competencia: 0 })
  const [editingId, setEditingId] = useState(null)
  const [testResult, setTestResult] = useState({})
  const [syncResult, setSyncResult] = useState({})
  const [syncing, setSyncing] = useState({})

  const load = () => api.get('/marketplaces').then(r => setItems(r.data))
  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    try {
      if (editingId) {
        await api.put(`/marketplaces/${editingId}`, form)
      } else {
        await api.post('/marketplaces', form)
      }
      setForm({ nombre: '', url_api: '', api_key: '', shop_id: '', shop_name: '', channel_code: '', ignorar_state_code: false, margen_competencia: 0 })
      setEditingId(null)
      load()
      onRefresh()
    } catch (e) {
      alert(e.response?.data?.error || 'Error al guardar marketplace')
    }
  }

  const startEdit = (mp) => {
    setEditingId(mp.id)
    setForm({ nombre: mp.nombre, url_api: mp.url_api, api_key: '', shop_id: mp.shop_id || '', shop_name: mp.shop_name || '', channel_code: mp.channel_code || '', ignorar_state_code: mp.ignorar_state_code || false, margen_competencia: mp.margen_competencia || 0 })
    setTestResult({})
    setSyncResult({})
  }

  const testConnection = async (id) => {
    const r = await api.post(`/marketplaces/${id}/test`)
    setTestResult(prev => ({ ...prev, [id]: r.data }))
  }

  const syncOffers = async (id) => {
    setSyncing(prev => ({ ...prev, [id]: true }))
    try {
      const r = await api.post(`/marketplaces/${id}/sync`)
      setSyncResult(prev => ({ ...prev, [id]: r.data }))
    } catch (e) {
      const message = e.response?.data?.message || 'Error de conexion'
      setSyncResult(prev => ({ ...prev, [id]: { status: 'error', message } }))
    }
    setSyncing(prev => ({ ...prev, [id]: false }))
  }

  const toggleActivo = async (mp) => {
    await api.put(`/marketplaces/${mp.id}`, { activo: !mp.activo })
    load()
    onRefresh()
  }

  const deleteMp = async (id) => {
    if (!confirm('Eliminar marketplace?')) return
    await api.delete(`/marketplaces/${id}`)
    load()
    onRefresh()
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Marketplaces</h2>

      <form onSubmit={submit} className="bg-white rounded-lg border p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <input placeholder="Nombre" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })}
            className="border rounded px-3 py-2 text-sm" required />
          <input placeholder="URL API" value={form.url_api} onChange={e => setForm({ ...form, url_api: e.target.value })}
            className="border rounded px-3 py-2 text-sm" required />
          <input placeholder="API Key" value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })}
            className="border rounded px-3 py-2 text-sm" type="password" />
          <input placeholder="Shop ID" value={form.shop_id} onChange={e => setForm({ ...form, shop_id: e.target.value })}
            className="border rounded px-3 py-2 text-sm" />
          <input placeholder="Nombre tienda en marketplace (ej: iRenovo)" value={form.shop_name} onChange={e => setForm({ ...form, shop_name: e.target.value })}
            className="border rounded px-3 py-2 text-sm" />
          <input placeholder="Channel code (ej: ES_B2C, B2C)" value={form.channel_code} onChange={e => setForm({ ...form, channel_code: e.target.value })}
            className="border rounded px-3 py-2 text-sm" />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
          <input type="checkbox" checked={form.ignorar_state_code} onChange={e => setForm({ ...form, ignorar_state_code: e.target.checked })}
            className="w-4 h-4 rounded" />
          Ignorar estado estético (competir contra todos los reacondicionados, excluye Nuevo)
        </label>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-700 whitespace-nowrap">Margen competencia (%):</label>
          <input type="number" step="0.5" min="0" max="20" value={form.margen_competencia}
            onChange={e => setForm({ ...form, margen_competencia: parseFloat(e.target.value) || 0 })}
            className="border rounded px-3 py-2 text-sm w-24" />
          <span className="text-xs text-gray-400">0 = estándar (−0.01€). &gt;0 = % por debajo del competidor (ej: 5 para Pixmania)</span>
        </div>
        <div className="flex gap-2">
          <button type="submit" className="bg-gray-900 text-white px-4 py-2 rounded text-sm">
            {editingId ? 'Actualizar' : 'Crear'}
          </button>
          {editingId && <button type="button" onClick={() => { setEditingId(null); setForm({ nombre: '', url_api: '', api_key: '', shop_id: '', shop_name: '', channel_code: '', ignorar_state_code: false, margen_competencia: 0 }); setTestResult({}); setSyncResult({}) }}
            className="text-gray-500 text-sm">Cancelar</button>}
        </div>
      </form>

      <div className="bg-white rounded-lg border divide-y">
        {items.map(mp => (
          <div key={mp.id} className="px-4 py-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{mp.nombre}</p>
              <p className="text-xs text-gray-500">{mp.url_api} &middot; {mp.tipo}{mp.channel_code ? ` · ${mp.channel_code}` : ''}</p>
            </div>
            <div className="flex items-center gap-3">
              {testResult[mp.id] && (
                <span className={`text-xs px-2 py-0.5 rounded ${testResult[mp.id].ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  {testResult[mp.id].ok ? 'OK' : 'Error'}{testResult[mp.id].mock_mode ? ' (mock)' : ''}
                </span>
              )}
              {syncResult[mp.id] && (
                <span className={`text-xs px-2 py-0.5 rounded ${syncResult[mp.id].status === 'ok' ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                  {syncResult[mp.id].status === 'ok'
                    ? `${syncResult[mp.id].ofertas_api} de API · ${syncResult[mp.id].nuevas} nuevas · ${syncResult[mp.id].actualizadas} actualizadas · ${syncResult[mp.id].ignoradas_sin_stock} sin stock`
                    : syncResult[mp.id].message}
                </span>
              )}
              <button onClick={() => syncOffers(mp.id)} disabled={syncing[mp.id]}
                className="text-xs text-purple-600 hover:underline disabled:opacity-50">
                {syncing[mp.id] ? 'Sincronizando...' : 'Sincronizar'}
              </button>
              <button onClick={() => testConnection(mp.id)} className="text-xs text-blue-600 hover:underline">Test</button>
              <button onClick={() => startEdit(mp)} className="text-xs text-blue-600 hover:underline">Editar</button>
              <button onClick={() => toggleActivo(mp)}
                className={`w-8 h-5 rounded-full relative transition ${mp.activo ? 'bg-green-500' : 'bg-gray-300'}`}>
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${mp.activo ? 'left-3.5' : 'left-0.5'}`} />
              </button>
              <button onClick={() => deleteMp(mp.id)} className="text-xs text-red-500 hover:underline">Eliminar</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
