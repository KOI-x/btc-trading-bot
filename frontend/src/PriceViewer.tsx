import React, { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

interface PriceRecord {
  date: string;
  price_usd: number;
  price_clp: number;
}

export default function PriceViewer() {
  const [coinId, setCoinId] = useState("bitcoin");
  const [prices, setPrices] = useState<PriceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPrices() {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(`/api/prices/${coinId}`);
        if (!resp.ok) {
          throw new Error("Failed to fetch prices");
        }
        const data = await resp.json();
        setPrices(data);
      } catch (err) {
        setError((err as Error).message);
        setPrices([]);
      } finally {
        setLoading(false);
      }
    }
    fetchPrices();
  }, [coinId]);

  return (
    <div className="p-6 max-w-3xl mx-auto font-sans">
      <div className="mb-4">
        <label className="mr-2 text-gray-700">Coin:</label>
        <select
          value={coinId}
          onChange={(e) => setCoinId(e.target.value)}
          className="border rounded p-2 bg-white text-gray-800"
        >
          <option value="bitcoin">bitcoin</option>
          <option value="ethereum">ethereum</option>
        </select>
      </div>
      {error && <div className="text-red-600 mb-2">{error}</div>}
      {loading ? (
        <div>Loading...</div>
      ) : (
        <>
          <div className="overflow-x-auto mb-8 rounded-lg border">
            <table className="min-w-full border-collapse">
              <thead className="bg-gray-200">
                <tr>
                  <th className="p-2 border-b text-left">Fecha</th>
                  <th className="p-2 border-b text-right">Precio USD</th>
                  <th className="p-2 border-b text-right">Precio CLP</th>
                </tr>
              </thead>
              <tbody>
                {prices.map((p) => (
                  <tr key={p.date} className="odd:bg-white even:bg-gray-50">
                    <td className="p-2 border-b">{p.date}</td>
                    <td className="p-2 border-b text-right">
                      {p.price_usd.toLocaleString()}
                    </td>
                    <td className="p-2 border-b text-right">
                      {p.price_clp.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border rounded p-4 bg-white">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={prices} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="price_usd" stroke="#3b82f6" />
                <Line type="monotone" dataKey="price_clp" stroke="#f97316" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
