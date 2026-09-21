import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DataExplorer from './DataExplorer';

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => children,
  LineChart: () => null, Line: () => null, XAxis: () => null, YAxis: () => null,
  CartesianGrid: () => null, Tooltip: () => null, Legend: () => null,
}));

const paper = (id, year, field, adjusted) => ({
  id, title: `Publication ${id}`, publishedYear: year, fields: [field], fieldDetails: [],
  authors: [{ id: 'researcher', name: 'Researcher', position: 1, weight: 0.5 }],
  authorContributionWeight: 0.5, totalCitations: 12, selfCitations: 2,
  adjustedCitations: adjusted, averageIsc: 0.2,
});
const profile = {
  authorId: 'researcher', author: 'Researcher', totalPublications: 3,
  totalCitations: 36, totalSelfCitations: 6, totalAdjustedCitations: 12,
  nmIndex: 77.123, hIndex: 3, cScore: 88.456, careerCompensation: 1,
  trendData: [], publications: [paper('A', 2022, 'Computer Science', 7), paper('B', 2025, 'Computer Science', 0), paper('C', 2020, 'Biology', 5)],
};

afterEach(() => { delete global.fetch; localStorage.clear(); });

test('loads the profile, combines filters and clears filters without changing metrics or refetching', async () => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => profile });
  render(<DataExplorer authorName="Researcher" />);
  await screen.findByRole('heading', { name: 'Publication A' });
  expect(screen.getByRole('heading', { name: 'Publication B' })).toBeInTheDocument();
  expect(screen.getByRole('slider', { name: /Start Year/ })).toHaveAttribute('min', '2020');
  fireEvent.change(screen.getByLabelText('FIELD'), { target: { value: 'Computer Science' } });
  fireEvent.change(screen.getByRole('slider', { name: /Start Year/ }), { target: { value: '2022' } });
  fireEvent.change(screen.getByLabelText('CITATION TYPE'), { target: { value: 'adjusted' } });
  expect(screen.queryByRole('heading', { name: 'Publication B' })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Publication C' })).not.toBeInTheDocument();
  expect(screen.getByText('Showing', { exact: false }).textContent).toBe('Showing 1 of 3 publications');
  expect(screen.getByText('Adjusted citations')).toBeInTheDocument();
  expect(screen.queryByRole('group', { name: 'Citation View' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('PUBLICATION IMPACT'), { target: { value: 'low' } });
  expect(screen.getByText('No publications match these filters')).toBeInTheDocument();
  expect(screen.getByText('77.123')).toBeInTheDocument();
  expect(screen.getByText('88.456')).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole('button', { name: 'Clear filters' })[0]);
  await waitFor(() => expect(screen.getAllByRole('heading', { name: /^Publication [ABC]$/ })).toHaveLength(3));
  expect(screen.getByLabelText('All years')).toBeChecked();
  expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  expect(screen.getAllByRole('combobox').filter(el => el.tagName === 'SELECT')).toHaveLength(4);
  expect(screen.queryByRole('option', { name: 'Calculated' })).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Not calculated' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Citation Impact')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Impact Level')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('PUBLICATION IMPACT'), { target: { value: 'uncited' } });
  expect(screen.getByText('No publications match these filters')).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
