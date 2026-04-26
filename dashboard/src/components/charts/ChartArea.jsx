import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export default function ChartArea({
  data,
  xKey = "day",
  yKey = "cum_pnl",
  height = 240,
  color = "#22c55e",
  negativeColor = "#ef4444",
}) {
  const lastValue = data?.length ? data[data.length - 1][yKey] : 0;
  const strokeColor = lastValue >= 0 ? color : negativeColor;
  const fillId = `area-fill-${strokeColor.replace("#", "")}`;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data || []} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity={0.3} />
            <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
          </linearGradient>
        </defs>
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
        <Area
          type="monotone"
          dataKey={yKey}
          stroke={strokeColor}
          strokeWidth={2}
          fill={`url(#${fillId})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
