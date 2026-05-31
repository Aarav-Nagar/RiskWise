import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency } from "../lib/formatters.js";

export default function StockChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6bbcff" stopOpacity={0.7} />
            <stop offset="100%" stopColor="#6bbcff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(124, 154, 193, 0.12)" vertical={false} />
        <XAxis dataKey="date" stroke="#93a6c7" tick={{ fill: "#93a6c7" }} />
        <YAxis stroke="#93a6c7" tick={{ fill: "#93a6c7" }} domain={["auto", "auto"]} />
        <Tooltip formatter={(value) => formatCurrency(value)} />
        <Area type="monotone" dataKey="close" stroke="#6bbcff" fill="url(#priceFill)" strokeWidth={2.4} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
