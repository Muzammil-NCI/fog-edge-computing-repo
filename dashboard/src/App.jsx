import { useCallback, useEffect, useMemo, useState } from "react";
import AggregateChart from "./components/AggregateChart.jsx";

const API_BASE = import.meta.env.VITE_API_BASE || "https://u6fuze7uqf.execute-api.us-east-1.amazonaws.com";
const POLL_MS = Number(import.meta.env.VITE_POLL_MS) || 2000;

/** Must match `DEFAULT_CAMPUS_ZONES` in v2/lambdas/edge_app.py */
export const CAMPUS_ZONES = [
  "S1.02",
  "S2.04",
  "S3.05",
  "S3.06",
  "Theatre-1",
  "Theatre-2",
  "Theatre-3",
  "Spencer Library 05",
  "Spencer Library 04"
];

function sortSelectedZones(selected) {
  return CAMPUS_ZONES.filter((z) => selected.includes(z));
}

function readingsUrl(base, zone, metric) {
  const q = new URLSearchParams({ zone, metric, limit: "40" });
  return `${base}/readings?${q}`;
}

export default function App() {
  const [selectedZones, setSelectedZones] = useState(() => ["S1.02"]);
  const [metric, setMetric] = useState("temperature");
  const [seriesByZone, setSeriesByZone] = useState({});
  const [error, setError] = useState("");
  const [lastSync, setLastSync] = useState("-");

  const base = useMemo(() => API_BASE.replace(/\/$/, ""), []);

  const orderedZones = useMemo(() => sortSelectedZones(selectedZones), [selectedZones]);

  const onZonesSelectChange = useCallback((e) => {
    const next = [...e.target.selectedOptions].map((o) => o.value);
    if (next.length === 0) {
      setSelectedZones(["S1.02"]);
      return;
    }
    setSelectedZones(next);
  }, []);

  useEffect(() => {
    if (!base || orderedZones.length === 0) return undefined;

    let cancelled = false;

    async function loadAll() {
      try {
        const results = await Promise.all(
          orderedZones.map(async (zone) => {
            const res = await fetch(readingsUrl(base, zone, metric));
            if (!res.ok) throw new Error(`${zone}: ${res.status}`);
            const json = await res.json();
            return { zone, items: json.items || [] };
          })
        );
        if (cancelled) return;
        const next = {};
        for (const { zone, items } of results) next[zone] = items;
        setSeriesByZone(next);
        setLastSync(new Date().toLocaleTimeString());
        setError("");
      } catch {
        if (!cancelled) setError("Could not reach API. Check VITE_API_BASE and CORS.");
      }
    }

    loadAll();
    const id = setInterval(loadAll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [base, orderedZones, metric]);

  const singleZone = orderedZones.length === 1 ? orderedZones[0] : null;
  const latest = singleZone ? seriesByZone[singleZone]?.[0] : null;

  return (
    <div className="app">
      <h1>Smart campus monitoring</h1>
      <p className="subtitle">
        Select one or more campus zones below
      </p>

      <div className="controls">
        <label className="zone-multiselect-label">
          Campus zones
          <select
            className="zone-multiselect"
            multiple
            size={Math.min(9, CAMPUS_ZONES.length)}
            value={selectedZones}
            onChange={onZonesSelectChange}
            aria-label="Campus zones, select one or more"
          >
            {CAMPUS_ZONES.map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
        </label>
        <label>
          Metric
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="temperature">Temperature</option>
            <option value="humidity">Humidity</option>
            <option value="co2">CO2</option>
            <option value="light">Light</option>
          </select>
        </label>
      </div>

      {singleZone ? (
        <div className="cards">
          <div className="card">
            <h3>Zone</h3>
            <p style={{ fontSize: "1rem" }}>{singleZone}</p>
          </div>
          <div className="card">
            <h3>Latest avg</h3>
            <p>{latest?.avg != null ? latest.avg : "—"}</p>
          </div>
          <div className="card">
            <h3>Latest min</h3>
            <p>{latest?.min != null ? latest.min : "—"}</p>
          </div>
          <div className="card">
            <h3>Latest max</h3>
            <p>{latest?.max != null ? latest.max : "—"}</p>
          </div>
          <div className="card">
            <h3>Sample count</h3>
            <p>{latest?.count ?? "—"}</p>
          </div>
          <div className="card">
            <h3>Last sync</h3>
            <p style={{ fontSize: "0.95rem" }}>{lastSync}</p>
          </div>
        </div>
      ) : (
        <p className="sync-line">
          Last sync: {lastSync} · {orderedZones.length} zones selected
        </p>
      )}

      {error ? <p className="error">{error}</p> : null}

      <div className="charts-stack">
        {orderedZones.map((zone) => {
          const items = seriesByZone[zone] || [];
          const zLatest = items[0];
          return (
            <div key={zone} className="chart-wrap">
              <div className="chart-head">
                <h2>{zone}</h2>
                {zLatest ? (
                  <p className="chart-meta">
                    Latest avg {zLatest.avg ?? "—"} · min {zLatest.min ?? "—"} · max {zLatest.max ?? "—"} · n {zLatest.count ?? "—"}
                  </p>
                ) : (
                  <p className="chart-meta muted">No aggregate rows yet for this zone and metric.</p>
                )}
              </div>
              <div className="legend">
                <span style={{ color: "#38bdf8" }}>● Avg</span>
                <span style={{ color: "#4ade80" }}>● Min</span>
                <span style={{ color: "#f87171" }}>● Max</span>
              </div>
              <AggregateChart items={items} />
            </div>
          );
        })}
      </div>

    </div>
  );
}
