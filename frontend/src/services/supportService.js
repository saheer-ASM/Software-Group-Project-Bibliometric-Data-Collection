// Feedback and issue reports, stored in Cloud Firestore.
//
// Identity (userId, userEmail) always comes from the signed-in Firebase user and
// timestamps from the Firestore server. firestore.rules rejects any document whose
// identity, status or timestamps do not match, so the browser cannot forge them.
import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  updateDoc,
} from 'firebase/firestore';
import { auth, firestore } from '../firebase';

export const FEEDBACK_TYPES = ['Suggestion', 'General Feedback', 'Feature Request', 'Other'];
export const FEEDBACK_STATUSES = ['New', 'In Review', 'Resolved'];

export const ISSUE_CATEGORIES = ['Bug', 'Login/Authentication', 'Dashboard', 'Data Explorer', 'Other'];
export const ISSUE_STATUSES = ['Open', 'In Progress', 'Resolved', 'Closed'];

// Limits mirrored in firestore.rules.
export const LIMITS = {
  messageMin: 10,
  messageMax: 5000,
  titleMin: 5,
  titleMax: 150,
  adminResponseMax: 2000,
};

const requireUser = () => {
  const user = auth?.currentUser;
  if (!user) {
    const err = new Error('You need to be logged in.');
    err.code = 'app/not-signed-in';
    throw err;
  }
  return user;
};

const owner = (user) => ({
  userId: user.uid,
  userEmail: user.email,
  createdAt: serverTimestamp(),
  updatedAt: serverTimestamp(),
});

export const submitFeedback = ({ feedbackType, message }) => {
  const user = requireUser();
  return addDoc(collection(firestore, 'feedback'), {
    ...owner(user),
    feedbackType,
    message: message.trim(),
    status: 'New',
  });
};

export const submitIssue = ({ title, category, description }) => {
  const user = requireUser();
  return addDoc(collection(firestore, 'issues'), {
    ...owner(user),
    title: title.trim(),
    category,
    description: description.trim(),
    status: 'Open',
  });
};

// Admin only (enforced by firestore.rules). Live list, newest first.
export const watchSubmissions = (collectionName, onData, onError) =>
  onSnapshot(
    query(collection(firestore, collectionName), orderBy('createdAt', 'desc')),
    (snap) => onData(snap.docs.map((d) => ({ id: d.id, ...d.data() }))),
    onError,
  );

export const updateSubmission = (collectionName, id, { status, adminResponse }) =>
  updateDoc(doc(firestore, collectionName, id), {
    status,
    adminResponse: (adminResponse || '').trim(),
    updatedAt: serverTimestamp(),
  });

export const deleteSubmission = (collectionName, id) => deleteDoc(doc(firestore, collectionName, id));

export const supportErrorMessage = (err, fallback) => {
  switch (err?.code) {
    case 'app/not-signed-in':
    case 'unauthenticated':
      return 'Your session has expired. Please log in again.';
    case 'permission-denied':
      return 'You do not have permission to do this. If you were just made an admin, log out and log in again.';
    case 'unavailable':
      return 'Cannot reach the server. Check your internet connection and try again.';
    case 'resource-exhausted':
      return 'Too many requests. Please wait a moment and try again.';
    case 'failed-precondition':
      return 'The database is not ready yet. Please try again shortly.';
    default:
      return fallback;
  }
};
