import { useState } from "react";

export default function StrategySimulator() {
  const [coinId, setCoinId] = useState("bitcoin");
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState("");
  const [strategy, setStrategy] = useState("ema_s2f");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const resp = await fetch("/api/portfolio/eval", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          coin_id: coinId,
          purchase_date: date,
          amount: parseFloat(amount),
          strategy,
        }),
      });
      if (!resp.ok) {
        throw new Error(`Server error: ${resp.status}`);
      }
      const data = await resp.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto p-4">
      <form
        onSubmit={handleSubmit}
        className="grid grid-cols-1 gap-4 bg-white shadow-md rounded p-4"
      >
        <div>
          <label className="block text-sm font-medium mb-1">Coin ID</label>
          <input
            type="text"
            className="mt-1 block w-full border rounded p-2"
            value={coinId}
            onChange={(e) => setCoinId(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Fecha de compra</label>
          <input
            type="date"
            className="mt-1 block w-full border rounded p-2"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Monto invertido</label>
          <input
            type="number"
            className="mt-1 block w-full border rounded p-2"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Estrategia</label>
          <select
            className="mt-1 block w-full border rounded p-2"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
          >
            <option value="ema_s2f">EMA S2F</option>
            <option value="rsi">RSI</option>
          </select>
        </div>
        <button
          type="submit"
          className="bg-blue-500 text-white py-2 px-4 rounded disabled:opacity-50"
          disabled={loading}
        >
          {loading ? "Procesando..." : "Simular"}
        </button>
      </form>
      {error && <p className="mt-4 text-red-600">{error}</p>}
      {result && (
        <div className="mt-4 bg-gray-50 p-4 rounded shadow">
          <p>
            <strong>Retorno estrategia:</strong> {result.return_strategy}
          </p>
          <p>
            <strong>Retorno hold:</strong> {result.return_hold}
          </p>
          <p className="mt-2 italic">{result.suggestion}</p>
        </div>
      )}
    </div>
  );
}
