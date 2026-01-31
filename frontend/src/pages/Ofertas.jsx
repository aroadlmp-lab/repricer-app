import { useState, useEffect } from 'react'
import api from '../api'
import OfertasTable from '../components/OfertasTable'

export default function Ofertas({ selectedMp }) {
  const [ofertas, setOfertas] = useState([])

  const load = () => {
    const params = selectedMp ? { marketplace_id: selectedMp } : {}
    api.get('/ofertas', { params }).then(r => setOfertas(r.data))
  }

  useEffect(load, [selectedMp])

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Ofertas</h2>
      <OfertasTable ofertas={ofertas} onRefresh={load} />
    </div>
  )
}
