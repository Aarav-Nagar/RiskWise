import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const palette = ["#6bbcff", "#16e1c4", "#ffd166", "#ff8a65", "#a78bfa", "#6ee7b7"];

export default function PortfolioPie({ holdings }) {
  const sectorTotals = holdings.reduce((accumulator, holding) => {
    const key = holding.sector || "Unknown";
    accumulator[key] = (accumulator[key] || 0) + holding.currentValue;
    return accumulator;
  }, {});

  const data = Object.entries(sectorTotals).map(([name, value]) => ({ name, value }));

  if (!data.length) {
    return <div>No holdings yet. Add a position to generate the sector allocation chart.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={72} outerRadius={100}>
          {data.map((entry, index) => (
            <Cell key={entry.name} fill={palette[index % palette.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(value) => `$${Number(value).toFixed(2)}`} />
      </PieChart>
    </ResponsiveContainer>
  );
}
