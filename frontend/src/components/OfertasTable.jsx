import { useState } from 'react'
import api from '../api'

export default function OfertasTable({ ofertas, onRefresh }) {
  const [editing, setEditing] = useState(null)
  const [values, setValues] = useState({})

  const startEdit = (o) => {
    setEditing(o.id)
    setValues({ precio_min: o.precio_min || '', precio_max: o.precio_max || '' })
  }

  const save = async (id) => {
    await api.put(`/ofertas/${id}`, {
      precio_min: values.precio_min ? Number(values.precio_min) : null,
      precio_max: values.precio_max ? Number(values.precio_max) : null,
    })
    setEditing(null)
    onRefresh()
  }

  const toggleActivo = async (o) => {
    await api.put(`/ofertas/${o.id}`, { activo: !o.activo })
    onRefresh()
  }

  return (
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
            <th className="px-4 py-3 text-center">Buybox</th>
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
              <td className="px-4 py-3 text-center">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${o.tiene_buybox ? 'bg-green-500' : 'bg-red-400'}`} />
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
  )
}
