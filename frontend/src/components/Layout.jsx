import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/ofertas', label: 'Ofertas' },
  { to: '/historico', label: 'Historico' },
  { to: '/marketplaces', label: 'Marketplaces' },
]

export default function Layout({ children, marketplaces, selectedMp, onSelectMp }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <h1 className="text-xl font-bold text-gray-900">Repricer</h1>
          <nav className="flex gap-1">
            {navItems.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium ${isActive ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <select
          value={selectedMp || ''}
          onChange={e => onSelectMp(Number(e.target.value))}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {marketplaces.map(mp => (
            <option key={mp.id} value={mp.id}>{mp.nombre}</option>
          ))}
        </select>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  )
}
