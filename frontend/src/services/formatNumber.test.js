import React from 'react';
import { render, screen } from '@testing-library/react';
import { formatDecimal, formatTooltipValue, MAX_DECIMALS } from './formatNumber';
import PublicationCard from '../components/PublicationCard';
import MetricComparison from '../components/comparison/MetricComparison';

test('decimal values show at most 3 decimals, without padding zeros', () => {
  expect(MAX_DECIMALS).toBe(3);
  expect(formatDecimal(77.12345)).toBe('77.123');
  expect(formatDecimal(1.23456)).toBe('1.235');
  expect(formatDecimal(0.1 + 0.2)).toBe('0.3'); // 0.30000000000000004
  expect(formatDecimal(2.5)).toBe('2.5');
  expect(formatDecimal(3)).toBe('3');
  expect(formatDecimal(1.0)).toBe('1');
  expect(formatDecimal(12345.6789)).toBe('12345.679');
  expect(formatDecimal('4.56789')).toBe('4.568');
  expect(formatDecimal(-0.0001)).toBe('0');
});

test('a missing value shows a dash, not NaN', () => {
  for (const value of [null, undefined, '', NaN, 'abc', Infinity]) {
    expect(formatDecimal(value)).toBe('—');
  }
});

test('chart tooltips round numbers and leave labels alone', () => {
  expect(formatTooltipValue(12.3456789)).toBe('12.346');
  expect(formatTooltipValue('2020')).toBe('2020');
});

const publication = {
  id: 'W1', title: 'A paper', publishedYear: 2024, authors: [], fieldDetails: [],
  authorOrdering: 'alphabetical', selfCitations: 2, totalCitations: 10,
  adjustedCitations: 12.345678, averageIsc: 0.1 + 0.2, authorContributionWeight: 0,
};

test('a publication card shows adjusted citations and ISC with at most 3 decimals', () => {
  render(<PublicationCard publication={publication} label="1" onToggleSave={() => {}} onToggleExpanded={() => {}} onSelectAuthor={() => {}} />);
  expect(screen.getByText('12.346')).toBeInTheDocument();
  expect(screen.getByText('0.3')).toBeInTheDocument();
});

test('the comparison shows index values with at most 3 decimals and counts as whole numbers', () => {
  render(<MetricComparison authors={[{
    authorId: 'A1', name: 'Ada', nmIndex: 77.123456, cScore: 1, adjustedCitations: 2.5,
    publications: 12, citations: 340, selfCitations: 4,
  }]} />);
  expect(screen.getByText('77.123')).toBeInTheDocument();
  expect(screen.getByText('1')).toBeInTheDocument();
  expect(screen.getByText('2.5')).toBeInTheDocument();
  expect(screen.getByText('340')).toBeInTheDocument();
});
