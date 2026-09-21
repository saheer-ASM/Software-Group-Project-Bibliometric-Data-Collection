import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PublicationYearRange from './PublicationYearRange';

test('selects a range dynamically, prevents crossed bounds, and restores all years', () => {
  const change = jest.fn();
  const { rerender } = render(<PublicationYearRange years={[2020, 2026]} value={null} onChange={change} />);
  expect(screen.getByLabelText('All years')).toBeChecked();
  fireEvent.change(screen.getByRole('slider', { name: /Start Year/ }), { target: { value: '2022' } });
  expect(change).toHaveBeenLastCalledWith([2022, 2026]);
  rerender(<PublicationYearRange years={[2020, 2026]} value={[2022, 2025]} onChange={change} />);
  fireEvent.change(screen.getByRole('slider', { name: /Start Year/ }), { target: { value: '2026' } });
  expect(change).toHaveBeenLastCalledWith([2025, 2025]);
  fireEvent.change(screen.getByRole('slider', { name: /End Year/ }), { target: { value: '2020' } });
  expect(change).toHaveBeenLastCalledWith([2022, 2022]);
  fireEvent.click(screen.getByLabelText('All years'));
  expect(change).toHaveBeenLastCalledWith(null);
});

test('handles unavailable and single-year datasets', () => {
  const { rerender } = render(<PublicationYearRange years={[]} value={null} onChange={() => {}} />);
  expect(screen.getByText('No publication years available')).toBeInTheDocument();
  expect(screen.getByLabelText('All years')).toBeDisabled();
  rerender(<PublicationYearRange years={[2024]} value={null} onChange={() => {}} />);
  screen.getAllByRole('slider').forEach(slider => expect(slider).toBeDisabled());
});
