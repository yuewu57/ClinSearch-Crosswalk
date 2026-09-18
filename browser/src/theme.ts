/** Appearance only. No strategies, results or identifiers are persisted. */
type ThemePreference = 'system' | 'light' | 'dark';
const STORAGE_KEY = 'clinsearch-crosswalk-theme';

function isTheme(value: unknown): value is ThemePreference {
  return value === 'system' || value === 'light' || value === 'dark';
}

export function initializeThemeControl(select: HTMLSelectElement): void {
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  let preference: ThemePreference = 'system';
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (isTheme(saved)) preference = saved;
  } catch {
    // Storage can be disabled. The selector still works for this page session.
  }

  const apply = () => {
    const theme = preference === 'system'
      ? (systemTheme.matches ? 'dark' : 'light')
      : preference;
    document.documentElement.dataset.theme = theme;
    select.value = preference;
  };

  select.addEventListener('change', () => {
    if (!isTheme(select.value)) return;
    preference = select.value;
    apply();
    try {
      if (preference === 'system') window.localStorage.removeItem(STORAGE_KEY);
      else window.localStorage.setItem(STORAGE_KEY, preference);
    } catch {
      // Persisting the appearance choice is optional, never a conversion gate.
    }
  });

  systemTheme.addEventListener('change', () => {
    if (preference === 'system') apply();
  });
  window.addEventListener('storage', event => {
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    preference = isTheme(event.newValue) ? event.newValue : 'system';
    apply();
  });
  apply();
}
