export default function StatsCards({ stats }) {
  const cards = [
    { label: 'Ofertas activas', value: stats.total_ofertas, color: 'text-blue-600' },
    { label: '% Buybox', value: `${stats.pct_buybox}%`, color: 'text-green-600' },
    { label: 'Cambios hoy', value: stats.cambios_hoy, color: 'text-purple-600' },
    { label: 'Alertas', value: stats.alertas, color: stats.alertas > 0 ? 'text-red-600' : 'text-gray-400' },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(c => (
        <div key={c.label} className="bg-white rounded-lg border p-5">
          <p className="text-sm text-gray-500">{c.label}</p>
          <p className={`text-2xl font-bold mt-1 ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </div>
  )
}
