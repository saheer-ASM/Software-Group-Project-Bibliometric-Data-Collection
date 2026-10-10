// What the Firestore write actually contains: trimmed text, as firestore.rules requires.
import { addDoc } from 'firebase/firestore';
import { submitFeedback, submitIssue } from './supportService';

jest.mock('../firebase', () => ({ auth: { currentUser: { uid: 'u1', email: 'u1@example.com' } }, firestore: {} }));
jest.mock('firebase/firestore', () => ({
  addDoc: jest.fn(() => Promise.resolve({ id: 'x' })),
  collection: jest.fn((db, name) => name),
  serverTimestamp: jest.fn(() => 'SERVER_TIME'),
  deleteDoc: jest.fn(), doc: jest.fn(), onSnapshot: jest.fn(), orderBy: jest.fn(), query: jest.fn(), updateDoc: jest.fn(),
}));

test('feedback is trimmed before it is written', async () => {
  await submitFeedback({ feedbackType: 'Suggestion', message: '  \n Great site, thanks!  \n' });
  expect(addDoc.mock.calls[0][1].message).toBe('Great site, thanks!');
});

test('issue title and description are trimmed; inner spacing is kept', async () => {
  await submitIssue({ title: '  Chart  broken ', category: 'Bug', description: '\tSteps:\n1. open\n2. click   ' });
  const written = addDoc.mock.calls[0][1];
  expect(written.title).toBe('Chart  broken');
  expect(written.description).toBe('Steps:\n1. open\n2. click');
});
