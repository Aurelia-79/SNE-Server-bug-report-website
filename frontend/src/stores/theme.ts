import { computed, ref } from 'vue';

const STORAGE_KEY = 'nls-admin-theme';
const MEDIA_QUERY = '(prefers-color-scheme: dark)';

function getSystemPreference(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia(MEDIA_QUERY).matches ? 'dark' : 'light';
}

const rawTheme = ref<'light' | 'dark'>(
  (localStorage.getItem(STORAGE_KEY) as 'light' | 'dark' | null) ?? getSystemPreference()
);

const theme = computed(() => rawTheme.value);

function toggle(): void {
  const next = rawTheme.value === 'light' ? 'dark' : 'light';
  rawTheme.value = next;
  localStorage.setItem(STORAGE_KEY, next);
  apply(next);
}

function apply(t: 'light' | 'dark'): void {
  if (typeof document === 'undefined') return;
  if (t === 'dark') {
    document.documentElement.classList.add('theme-dark');
  } else {
    document.documentElement.classList.remove('theme-dark');
  }
}

// Apply on load
apply(rawTheme.value);

// Listen to system theme changes
if (typeof window !== 'undefined') {
  window.matchMedia(MEDIA_QUERY).addEventListener('change', (e) => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      rawTheme.value = e.matches ? 'dark' : 'light';
      apply(rawTheme.value);
    }
  });
}

export function useTheme() {
  return {
    theme,
    isDark: computed(() => rawTheme.value === 'dark'),
    toggle,
  };
}
