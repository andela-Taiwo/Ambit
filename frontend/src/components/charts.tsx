import type { JSX } from 'react';

export interface ChartPoint {
  label: string;
  value: number;
}

const padding = { left: 8, right: 8, top: 12, bottom: 8 };
const width = 600;
const height = 200;

const scaleY = (value: number, min: number, max: number): number => {
  const range = max - min || 1;
  return (
    height - padding.bottom - ((value - min) / range) * (height - padding.top - padding.bottom)
  );
};

const scaleX = (index: number, count: number): number => {
  if (count <= 1) return width / 2;
  const usable = width - padding.left - padding.right;
  return padding.left + (index / (count - 1)) * usable;
};

const DataTable = ({
  points,
  caption,
  formatValue,
}: {
  points: ChartPoint[];
  caption: string;
  formatValue: (value: number) => string;
}): JSX.Element => (
  <table className="sr-only">
    <caption>{caption}</caption>
    <thead>
      <tr>
        <th scope="col">Period</th>
        <th scope="col">Value</th>
      </tr>
    </thead>
    <tbody>
      {points.map((point) => (
        <tr key={point.label}>
          <th scope="row">{point.label}</th>
          <td>{formatValue(point.value)}</td>
        </tr>
      ))}
    </tbody>
  </table>
);

export const LineChart = ({
  points,
  label,
  formatValue,
}: {
  points: ChartPoint[];
  label: string;
  formatValue: (value: number) => string;
}): JSX.Element => {
  if (points.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No data for this period.</p>;
  }
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const path = points
    .map(
      (point, index) =>
        `${String(scaleX(index, points.length))},${String(scaleY(point.value, min, max))}`,
    )
    .join(' ');

  return (
    <figure>
      <svg
        role="img"
        aria-label={label}
        viewBox={`0 0 ${String(width)} ${String(height)}`}
        className="h-48 w-full"
        preserveAspectRatio="none"
      >
        <line
          x1="0"
          y1={height - padding.bottom}
          x2={width}
          y2={height - padding.bottom}
          stroke="#e2e8f0"
        />
        <polyline
          points={path}
          fill="none"
          stroke="#0f172a"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        {points.map((point, index) => (
          <circle
            key={point.label}
            cx={scaleX(index, points.length)}
            cy={scaleY(point.value, min, max)}
            r="3"
            fill="#0f172a"
          >
            <title>{`${point.label}: ${formatValue(point.value)}`}</title>
          </circle>
        ))}
      </svg>
      <figcaption className="mt-1 flex justify-between text-xs text-slate-500">
        <span>{points[0]?.label}</span>
        <span>{points[points.length - 1]?.label}</span>
      </figcaption>
      <DataTable points={points} caption={label} formatValue={formatValue} />
    </figure>
  );
};

export const BarChart = ({
  points,
  label,
  formatValue,
}: {
  points: ChartPoint[];
  label: string;
  formatValue: (value: number) => string;
}): JSX.Element => {
  if (points.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No data for this period.</p>;
  }
  const max = Math.max(...points.map((point) => Math.max(0, point.value)), 1);
  const usable = width - padding.left - padding.right;
  const barWidth = Math.max(4, usable / points.length - 8);

  return (
    <figure>
      <svg
        role="img"
        aria-label={label}
        viewBox={`0 0 ${String(width)} ${String(height)}`}
        className="h-48 w-full"
        preserveAspectRatio="none"
      >
        <line
          x1="0"
          y1={height - padding.bottom}
          x2={width}
          y2={height - padding.bottom}
          stroke="#e2e8f0"
        />
        {points.map((point, index) => {
          const barHeight =
            (Math.max(0, point.value) / max) * (height - padding.top - padding.bottom) || 0;
          const x = padding.left + index * (usable / points.length) + 4;
          return (
            <rect
              key={point.label}
              x={x}
              y={height - padding.bottom - barHeight}
              width={barWidth}
              height={barHeight}
              fill="#334155"
              rx="2"
            >
              <title>{`${point.label}: ${formatValue(point.value)}`}</title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="mt-1 flex justify-between text-xs text-slate-500">
        <span>{points[0]?.label}</span>
        <span>{points[points.length - 1]?.label}</span>
      </figcaption>
      <DataTable points={points} caption={label} formatValue={formatValue} />
    </figure>
  );
};
