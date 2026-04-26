import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";

export default function ChartBar({
  data,
  xKey = "count",
  yKey = "label",
  height = 200,
  color = "#a855f7",
  cellColors,
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data || []} layout="vertical" margin={{ top: 8, right: 16, left: 24, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" />
        <XAxis type="number" stroke="#6b7280" fontSize={11} tickLine={false} />
        <YAxis dataKey={yKey} type="category" stroke="#6b7280" fontSize={11} tickLine={false} width={60} />
        <Tooltip
          contentStyle={{
            background: "#12121a",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Bar dataKey={xKey} radius={[0, 4, 4, 0]}>
          {(data || []).map((_, i) => (
            <Cell key={i} fill={cellColors ? cellColors[i] : color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
