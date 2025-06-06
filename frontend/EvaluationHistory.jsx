import { useEffect, useState } from "react";

export default function EvaluationHistory() {
  const [evaluations, setEvaluations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sortField, setSortField] = useState("date");
  const [sortDir, setSortDir] = useState("desc");
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch("/api/evaluations");
        if (!resp.ok) {
          throw new Error("Failed to fetch evaluations");
        }
        const data = await resp.json();
        setEvaluations(data);
      } catch (err) {
        setError(err.message);
        setEvaluations([]);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const sorted = [...evaluations].sort((a, b) => {
    let res = 0;
    if (sortField === "date") {
      res = new Date(a.date) - new Date(b.date);
    } else if (sortField === "coin_id") {
      res = a.coin_id.localeCompare(b.coin_id);
    }
    return sortDir === "asc" ? res : -res;
  });

  const toggleSort = (field) => {
    if (field === sortField) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  return (
    <div className="p-4">
      {error && <div className="text-red-600 mb-2">{error}</div>}
      {loading ? (
        <div>Loading...</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead className="bg-gray-200">
              <tr>
                <th
                  className="p-2 border-b cursor-pointer text-left"
                  onClick={() => toggleSort("date")}
                >
                  Fecha
                </th>
                <th
                  className="p-2 border-b cursor-pointer text-left"
                  onClick={() => toggleSort("coin_id")}
                >
                  Coin
                </th>
                <th className="p-2 border-b text-left">Estrategia</th>
                <th className="p-2 border-b text-right">Retorno vs Hold</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((ev, idx) => {
                const diff = (ev.return_strategy - ev.return_hold) * 100;
                const isExpanded = expandedId === idx;
                return (
                  <>
                    <tr
                      key={idx}
                      className="odd:bg-white even:bg-gray-50 hover:bg-gray-100 cursor-pointer"
                      onClick={() =>
                        setExpandedId(isExpanded ? null : idx)
                      }
                    >
                      <td className="p-2 border-b">{ev.date}</td>
                      <td className="p-2 border-b">{ev.coin_id}</td>
                      <td className="p-2 border-b">{ev.strategy}</td>
                      <td className="p-2 border-b text-right">
                        {diff.toFixed(2)}%
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-gray-50 text-xs" key={`${idx}-details`}>
                        <td colSpan={4} className="p-2 border-b">
                          <pre className="whitespace-pre-wrap">
                            {JSON.stringify(ev, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
