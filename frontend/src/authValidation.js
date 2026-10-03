// Shared client-side validation for the auth forms (register, add-password).
// The backend still verifies identity through Firebase ID tokens; these checks
// only give the user immediate feedback.

// Standard address format: local part, a single @, dot-separated domain labels
// (no leading/trailing hyphen) and a TLD of 2+ letters.
const EMAIL_PATTERN = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$/;

export const sanitizeEmail = (value) => String(value || '').trim().toLowerCase();

export const isValidEmail = (value) => {
  const email = sanitizeEmail(value);
  if (email.length > 254 || !EMAIL_PATTERN.test(email)) return false;
  const [local] = email.split('@');
  return local.length <= 64 && !local.startsWith('.') && !local.endsWith('.') && !local.includes('..');
};

export const PASSWORD_RULES = [
  { id: 'length', label: 'At least 8 characters', test: (p) => p.length >= 8 },
  { id: 'upper', label: 'One uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { id: 'lower', label: 'One lowercase letter', test: (p) => /[a-z]/.test(p) },
  { id: 'digit', label: 'One number', test: (p) => /\d/.test(p) },
  { id: 'special', label: 'One special character', test: (p) => /[^A-Za-z0-9\s]/.test(p) },
];

export const checkPassword = (password) => {
  const rules = PASSWORD_RULES.map((rule) => ({ ...rule, met: rule.test(password) }));
  return { rules, strong: rules.every((rule) => rule.met) };
};
