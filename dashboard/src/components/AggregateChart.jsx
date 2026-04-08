import { useEffect, useRef } from "react";
import { createChart } from "lightweight-charts";

const MAX = 60;

function toPoints(items, key) {
  return items
    .filter((r) => r.window_end != null && r[key] != null)
    .map((r) => ({
      time: Math.floor(new Date(r.window_end).getTime() / 1000),
      value: Number(r[key])
    }))
    .sort((a, b) => a.time - b.time)
    .filter((p, i, arr) => i === 0 || p.time !== arr[i - 1].time)
    .slice(-MAX);
}

export default function AggregateChart({ items }) {
  const ref = useRef(null);
  const chartRef = useRef(null);
  const avgRef = useRef(null);
  const minRef = useRef(null);
  const maxRef = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: "solid", color: "#1e293b" },
        textColor: "#94a3b8"
      },
      grid: {
        vertLines: { color: "#334155" },
        horzLines: { color: "#334155" }
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
        borderColor: "#334155"
      },
      rightPriceScale: { borderColor: "#334155" }
    });

    const avg = chart.addLineSeries({ color: "#38bdf8", lineWidth: 2 });
    const min = chart.addLineSeries({ color: "#4ade80", lineWidth: 1 });
    const max = chart.addLineSeries({ color: "#f87171", lineWidth: 1 });

    chartRef.current = chart;
    avgRef.current = avg;
    minRef.current = min;
    maxRef.current = max;

    const ro = new ResizeObserver(() => {
      const { width, height } = el.getBoundingClientRect();
      chart.applyOptions({ width, height });
    });
    ro.observe(el);
    chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const list = Array.isArray(items) ? items : [];
    const avg = avgRef.current;
    const min = minRef.current;
    const max = maxRef.current;
    const chart = chartRef.current;
    if (!avg || !min || !max || !chart) return;

    avg.setData(toPoints(list, "avg"));
    min.setData(toPoints(list, "min"));
    max.setData(toPoints(list, "max"));

    requestAnimationFrame(() => {
      if (list.length > 1) chart.timeScale().fitContent();
    });
  }, [items]);

  return <div ref={ref} className="chart-canvas" />;
}
