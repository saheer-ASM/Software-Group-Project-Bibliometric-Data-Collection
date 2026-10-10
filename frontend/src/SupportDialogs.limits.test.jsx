// Feedback and Report an Issue: limits, counters, trimming.
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SupportDialogs from './SupportDialogs';
import { submitFeedback, submitIssue, LIMITS } from './services/supportService';

jest.mock('./firebase', () => ({ auth: { currentUser: { uid: 'u1', email: 'u1@example.com' } }, firestore: {} }));
jest.mock('firebase/auth', () => ({ onAuthStateChanged: (auth, callback) => { callback(auth.currentUser); return () => {}; } }));
jest.mock('./services/supportService', () => ({
  ...jest.requireActual('./services/supportService'),
  submitFeedback: jest.fn(() => Promise.resolve()),
  submitIssue: jest.fn(() => Promise.resolve()),
}));

beforeEach(() => jest.clearAllMocks());

const renderDialog = (kind) => render(<SupportDialogs kind={kind} onClose={jest.fn()} onRequireLogin={jest.fn()} />);
const type = (element, value) => fireEvent.change(element, { target: { value } });
const submit = (label) => fireEvent.click(screen.getByRole('button', { name: label }));

test('limits match the target configuration (and firestore.rules)', () => {
  expect(LIMITS).toMatchObject({
    feedbackMin: 10, feedbackMax: 1000, titleMin: 5, titleMax: 120, descriptionMin: 20, descriptionMax: 2000,
  });
});

describe('feedback', () => {
  const message = () => screen.getByPlaceholderText(/Tell us what you think/);

  test('the input stops at 1,000 and a live counter shows the length', () => {
    renderDialog('feedback');
    expect(message()).toHaveAttribute('maxLength', '1000');
    expect(screen.getByText('0 / 1,000')).toBeInTheDocument();
    type(message(), 'x'.repeat(245));
    expect(screen.getByText('245 / 1,000')).toBeInTheDocument();
    expect(message()).toHaveAttribute('aria-describedby', 'support-message-count');
  });

  test('the counter counts what is saved: surrounding whitespace excluded', () => {
    renderDialog('feedback');
    type(message(), '   twelve chars   ');
    expect(screen.getByText('12 / 1,000')).toBeInTheDocument();
  });

  test('below the minimum (9 real characters, padded with spaces) is refused', () => {
    renderDialog('feedback');
    type(message(), `     ${'a'.repeat(9)}     `);
    submit('Send Feedback');
    expect(screen.getByText('Please write at least 10 characters.')).toBeInTheDocument();
    expect(submitFeedback).not.toHaveBeenCalled();
  });

  test('whitespace only is refused', () => {
    renderDialog('feedback');
    type(message(), ' '.repeat(50));
    submit('Send Feedback');
    expect(screen.getByText('Please write at least 10 characters.')).toBeInTheDocument();
    expect(submitFeedback).not.toHaveBeenCalled();
  });

  test.each([10, 1000])('exactly %i characters is sent', async (n) => {
    renderDialog('feedback');
    type(message(), 'a'.repeat(n));
    submit('Send Feedback');
    await waitFor(() => expect(submitFeedback).toHaveBeenCalledTimes(1));
  });

  test('1,001 characters (maxLength bypassed, e.g. by script) is refused', () => {
    renderDialog('feedback');
    type(message(), 'a'.repeat(1001));
    submit('Send Feedback');
    expect(screen.getByText('Please keep it to 1,000 characters or fewer.')).toBeInTheDocument();
    expect(submitFeedback).not.toHaveBeenCalled();
  });

  test('Unicode text is accepted', async () => {
    renderDialog('feedback');
    type(message(), 'Très bien — 日本語でも大丈夫 ✓');
    submit('Send Feedback');
    await waitFor(() => expect(submitFeedback).toHaveBeenCalledTimes(1));
  });
});

describe('report an issue', () => {
  const title = () => screen.getByPlaceholderText(/Dashboard does not load/);
  const description = () => screen.getByPlaceholderText(/What happened/);
  const fill = (t, d) => { type(title(), t); type(description(), d); };

  test('title and description each cap their input and count live', () => {
    renderDialog('issue');
    expect(title()).toHaveAttribute('maxLength', '120');
    expect(description()).toHaveAttribute('maxLength', '2000');
    type(title(), 't'.repeat(48));
    type(description(), 'd'.repeat(450));
    expect(screen.getByText('48 / 120')).toBeInTheDocument();
    expect(screen.getByText('450 / 2,000')).toBeInTheDocument();
  });

  test('title: 4 refused, 5 and 120 accepted, 121 refused', async () => {
    renderDialog('issue');
    fill('tttt', 'd'.repeat(30));
    submit('Submit Issue');
    expect(screen.getByText('Please give the issue a title (at least 5 characters).')).toBeInTheDocument();

    fill('t'.repeat(121), 'd'.repeat(30));
    submit('Submit Issue');
    expect(screen.getByText('Please keep the title to 120 characters or fewer.')).toBeInTheDocument();
    expect(submitIssue).not.toHaveBeenCalled();

    fill('t'.repeat(5), 'd'.repeat(30));
    submit('Submit Issue');
    await waitFor(() => expect(submitIssue).toHaveBeenCalledTimes(1));
  });

  test('title at 120 is accepted', async () => {
    renderDialog('issue');
    fill('t'.repeat(120), 'd'.repeat(30));
    submit('Submit Issue');
    await waitFor(() => expect(submitIssue).toHaveBeenCalledTimes(1));
  });

  test('description: 19 refused (not the old 10), 20 and 2,000 accepted, 2,001 refused', async () => {
    renderDialog('issue');
    fill('Valid title', 'd'.repeat(19));
    submit('Submit Issue');
    expect(screen.getByText('Please describe the issue (at least 20 characters).')).toBeInTheDocument();

    fill('Valid title', 'd'.repeat(2001));
    submit('Submit Issue');
    expect(screen.getByText('Please keep it to 2,000 characters or fewer.')).toBeInTheDocument();
    expect(submitIssue).not.toHaveBeenCalled();

    fill('Valid title', 'd'.repeat(20));
    submit('Submit Issue');
    await waitFor(() => expect(submitIssue).toHaveBeenCalledTimes(1));
  });

  test('description at 2,000 is accepted', async () => {
    renderDialog('issue');
    fill('Valid title', 'd'.repeat(2000));
    submit('Submit Issue');
    await waitFor(() => expect(submitIssue).toHaveBeenCalledTimes(1));
  });

  test('padding cannot satisfy the minimums', () => {
    renderDialog('issue');
    fill(`      x      `, `${' '.repeat(30)}short${' '.repeat(30)}`);
    submit('Submit Issue');
    expect(screen.getByText('Please give the issue a title (at least 5 characters).')).toBeInTheDocument();
    expect(screen.getByText('Please describe the issue (at least 20 characters).')).toBeInTheDocument();
    expect(submitIssue).not.toHaveBeenCalled();
  });
});
