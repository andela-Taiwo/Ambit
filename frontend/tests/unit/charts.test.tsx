import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BarChart, LineChart } from '@/components/charts';

const points = [
  { label: 'Jan', value: 100 },
  { label: 'Feb', value: 250 },
];

describe('LineChart', () => {
  it('renders an accessible image and data table', () => {
    render(
      <LineChart points={points} label="Net worth" formatValue={(value) => `£${String(value)}`} />,
    );

    expect(screen.getByRole('img', { name: 'Net worth' })).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Net worth' })).toBeInTheDocument();
    expect(screen.getAllByText('Jan').length).toBeGreaterThan(0);
    expect(screen.getByText('£250')).toBeInTheDocument();
  });

  it('shows an empty message without points', () => {
    render(<LineChart points={[]} label="Net worth" formatValue={String} />);

    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });
});

describe('BarChart', () => {
  it('renders bars and an accessible table', () => {
    render(
      <BarChart points={points} label="Cash flow" formatValue={(value) => `£${String(value)}`} />,
    );

    expect(screen.getByRole('img', { name: 'Cash flow' })).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Cash flow' })).toBeInTheDocument();
    expect(screen.getByText('£100')).toBeInTheDocument();
  });

  it('shows an empty message without points', () => {
    render(<BarChart points={[]} label="Cash flow" formatValue={String} />);

    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });
});
