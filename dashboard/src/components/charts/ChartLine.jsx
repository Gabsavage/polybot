import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";

export default function ChartLine({ data, xKey = "day", series = [], height = 280 }) {
  // series: [{ key: "c1_pnl", color: "#f97316", name: "C1" }, ...]
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data || []} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" />
        <XAxis dataKey={xKey} stroke="#6b7280" fontSize={11} tickLine={false} />
        <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
        <Tooltip
          contentStyle={{
            background: "#12121a",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "12px", color: "#6b7280" }} />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
