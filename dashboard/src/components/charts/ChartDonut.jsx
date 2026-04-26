import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";

export default function ChartDonut({
  data,
  height = 160,
  colors = ["#22c55e", "#ef4444", "#6b7280"],
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data || []}
          dataKey="value"
          nameKey="name"
          innerRadius={50}
          outerRadius={70}
          paddingAngle={2}
        >
          {(data || []).map((_, i) => (
            <Cell key={i} fill={colors[i % colors.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "#12121a",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
