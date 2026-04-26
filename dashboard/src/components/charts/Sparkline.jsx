import { ResponsiveContainer, AreaChart, Area } from "recharts";

export default function Sparkline({ data, dataKey = "value", color = "#f97316", height = 32 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data || []} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={1.5}
          fill={color}
          fillOpacity={0.15}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
