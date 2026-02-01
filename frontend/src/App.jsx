import { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Ofertas from './pages/Ofertas'
import Historico from './pages/Historico'
import Marketplaces from './pages/Marketplaces'
import api from './api'

export default function App() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)
  const [marketplaces, setMarketplaces] = useState([])
  const [selectedMp, setSelectedMp] = useState(null)

  useEffect(() => {
    api.get('/auth/me')
      .then(r => setUser(r.data.user))
      .catch(() => setUser(null))
      .finally(() => setChecking(false))
  }, [])

  useEffect(() => {
    if (!user) return
    api.get('/marketplaces').then(r => {
      setMarketplaces(r.data)
      if (r.data.length > 0) setSelectedMp(r.data[0].id)
    })
  }, [user])

  const refreshMps = () => api.get('/marketplaces').then(r => setMarketplaces(r.data))

  const handleLogout = () => {
    api.post('/auth/logout').then(() => {
      setUser(null)
      setMarketplaces([])
      setSelectedMp(null)
    })
  }

  if (checking) return null

  if (!user) return <Login onLogin={setUser} />

  return (
    <Layout marketplaces={marketplaces} selectedMp={selectedMp} onSelectMp={setSelectedMp} onLogout={handleLogout}>
      <Routes>
        <Route path="/" element={<Dashboard selectedMp={selectedMp} />} />
        <Route path="/ofertas" element={<Ofertas selectedMp={selectedMp} />} />
        <Route path="/historico" element={<Historico selectedMp={selectedMp} />} />
        <Route path="/marketplaces" element={<Marketplaces onRefresh={refreshMps} />} />
      </Routes>
    </Layout>
  )
}
