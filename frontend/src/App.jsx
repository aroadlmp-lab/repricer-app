import { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Ofertas from './pages/Ofertas'
import Historico from './pages/Historico'
import Marketplaces from './pages/Marketplaces'
import api from './api'

export default function App() {
  const [marketplaces, setMarketplaces] = useState([])
  const [selectedMp, setSelectedMp] = useState(null)

  useEffect(() => {
    api.get('/marketplaces').then(r => {
      setMarketplaces(r.data)
      if (r.data.length > 0) setSelectedMp(r.data[0].id)
    })
  }, [])

  const refreshMps = () => api.get('/marketplaces').then(r => setMarketplaces(r.data))

  return (
    <Layout marketplaces={marketplaces} selectedMp={selectedMp} onSelectMp={setSelectedMp}>
      <Routes>
        <Route path="/" element={<Dashboard selectedMp={selectedMp} />} />
        <Route path="/ofertas" element={<Ofertas selectedMp={selectedMp} />} />
        <Route path="/historico" element={<Historico selectedMp={selectedMp} />} />
        <Route path="/marketplaces" element={<Marketplaces onRefresh={refreshMps} />} />
      </Routes>
    </Layout>
  )
}
