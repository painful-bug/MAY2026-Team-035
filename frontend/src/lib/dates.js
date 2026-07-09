// Date formatting helpers — replace the repeated inline Date wrangling the old
// context did in every action.
export const todayISO = () => new Date().toISOString().split('T')[0];

export const longDate = (d = new Date()) =>
  d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

export const shortTime = (d = new Date()) =>
  d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
