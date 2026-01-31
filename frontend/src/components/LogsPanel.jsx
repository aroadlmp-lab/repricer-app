export default function LogsPanel({ logs }) {
  return (
    <div className="bg-white rounded-lg border divide-y">
      {logs.map(log => (
        <div key={log.id} className="px-4 py-3 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">{log.oferta?.producto?.nombre || 'Producto'}</p>
            <p className="text-xs text-gray-500">{log.oferta?.marketplace_nombre} &middot; {log.motivo}</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-mono">
              <span className="text-gray-400">{log.precio_anterior?.toFixed(2)}</span>
              <span className="mx-1">&rarr;</span>
              <span className={log.precio_nuevo < log.precio_anterior ? 'text-red-600' : 'text-green-600'}>
                {log.precio_nuevo?.toFixed(2)}
              </span>
            </p>
            <p className="text-xs text-gray-400">{new Date(log.created_at).toLocaleString()}</p>
          </div>
        </div>
      ))}
      {logs.length === 0 && <p className="text-center text-gray-400 py-8">Sin cambios registrados</p>}
    </div>
  )
}
