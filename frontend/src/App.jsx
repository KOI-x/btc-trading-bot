import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [coinId, setCoinId] = useState('bitcoin')
  const [amount, setAmount] = useState('')
  const [buyDate, setBuyDate] = useState('')
  const [strategy, setStrategy] = useState('ema_s2f')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState(() => {
    try {
      const val = localStorage.getItem('evaluations')
      return val ? JSON.parse(val) : []
    } catch {
      return []
    }
  })

  const saveHistory = (entry) => {
    const newHistory = [entry, ...history]
    setHistory(newHistory)
    try {
      localStorage.setItem('evaluations', JSON.stringify(newHistory))
    } catch {
      // ignore storage errors
    }
  }

  const handleEval = async (e) => {
    e.preventDefault()
    setError(null)
    setResult(null)
    if (!buyDate || !amount) {
      setError('Todos los campos son obligatorios')
      return
    }
    const amt = parseFloat(amount)
    if (isNaN(amt) || amt <= 0) {
      setError('El monto debe ser mayor a 0')
      return
    }
    const payload = {
      portfolio: [{ coin_id: coinId, amount: amt, buy_date: buyDate }],
      strategy
    }
    try {
      const resp = await fetch('/api/portfolio/eval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!resp.ok) {
        throw new Error('Error ' + resp.status)
      }
      const data = await resp.json()
      setResult(data)
      saveHistory({ request: payload, response: data, ts: new Date().toISOString() })
    } catch (err) {
      setError(err.message)
    }
  }

  const handleExport = async () => {
    if (!result) return
    const payload = {
      portfolio: [{ coin_id: coinId, amount: parseFloat(amount), buy_date: buyDate }],
      strategy,
      format: 'csv'
    }
    try {
      const resp = await fetch('/api/evaluation/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!resp.ok) throw new Error('Export failed')
      const blob = await resp.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'evaluation.csv'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="container">
      <h1>Evaluar Portafolio</h1>
      <form onSubmit={handleEval} className="form">
        <div className="field">
          <label>Coin ID</label>
          <input value={coinId} onChange={e => setCoinId(e.target.value)} />
        </div>
        <div className="field">
          <label>Monto</label>
          <input type="number" value={amount} onChange={e => setAmount(e.target.value)} required min="0" step="any" />
        </div>
        <div className="field">
          <label>Fecha de compra</label>
          <input type="date" value={buyDate} onChange={e => setBuyDate(e.target.value)} required />
        </div>
        <div className="field">
          <label>Estrategia</label>
          <select value={strategy} onChange={e => setStrategy(e.target.value)}>
            <option value="ema_s2f">EMA S2F</option>
          </select>
        </div>
        <button type="submit">Evaluar</button>
        <button type="button" onClick={handleExport} disabled={!result}>Exportar CSV</button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <table className="result">
          <thead>
            <tr>
              <th>Total USD</th>
              <th>Comparación</th>
              <th>Comentario</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{result.total_value_now}</td>
              <td>{result.estrategia_vs_hold}</td>
              <td>{result.comentario}</td>
            </tr>
          </tbody>
        </table>
      )}
      {history.length > 0 && (
        <div className="history">
          <h2>Historial</h2>
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Coin</th>
                <th>Monto</th>
                <th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, idx) => (
                <tr key={idx}>
                  <td>{new Date(h.ts).toLocaleDateString()}</td>
                  <td>{h.request.portfolio[0].coin_id}</td>
                  <td>{h.request.portfolio[0].amount}</td>
                  <td>{h.response.estrategia_vs_hold}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default App
