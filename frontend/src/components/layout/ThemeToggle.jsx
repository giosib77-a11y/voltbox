import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme.js';

/**
 * ღია/მუქი თემის გადამრთველი header-ში.
 * სახელი ამბობს, რაზე გადაერთვება და არა რა არის ახლა — ეკრანის მკითხველი
 * ღილაკის ქმედებას კითხულობს. ხატულაც დანიშნულებას აჩვენებს.
 */
export default function ThemeToggle({ className = '' }) {
  const [theme, setTheme] = useTheme();
  const next = theme === 'dark' ? 'light' : 'dark';
  const label = next === 'dark' ? 'მუქ თემაზე გადართვა' : 'ღია თემაზე გადართვა';
  const Icon = next === 'dark' ? Moon : Sun;

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={label}
      title={label}
      className={`flex h-10 w-10 items-center justify-center rounded-control text-ink-700 transition-colors hover:bg-ink-100 hover:text-fg ${className}`}
    >
      <Icon className="h-5 w-5" aria-hidden="true" />
    </button>
  );
}
