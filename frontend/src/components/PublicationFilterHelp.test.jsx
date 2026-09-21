import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PublicationFilterHelp from './PublicationFilterHelp';

test('opens accessible help and closes with Escape, outside click, and close button', () => {
  render(<PublicationFilterHelp />);
  const trigger = screen.getByRole('button', { name: /How these filters work/ });
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(trigger);
  expect(screen.getByRole('region', { name: 'How these filters work' })).toBeInTheDocument();
  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('region')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  fireEvent.click(trigger);
  fireEvent.pointerDown(document.body);
  expect(screen.queryByRole('region')).not.toBeInTheDocument();
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole('button', { name: 'Close filter help' }));
  expect(screen.queryByRole('region')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
