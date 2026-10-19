import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme.js';
import { t } from '../../i18n/index.js';

/**
 * ღია/მუქი თემის გადამრთველი header-ში.
 * სახელი ამბობს, რაზე გადაერთვება და არა რა არის ახლა — ეკრანის მკითხველი
 * ღილაკის ქმედებას კითხულობს. ხატულაც დანიშნულებას აჩვენებს.
 */
export default function ThemeToggle({ className = '' }) {
  const [theme, setTheme] = useTheme();
  const next = theme === 'dark' ? 'light' : 'dark';
  const label = next === 'dark' ? t('theme.toDark') : t('theme.toLight');
  const Icon = next === 'dark' ? Moon : Sun;

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={label}
      title={label}
      className={`flex h-11 w-11 items-center justify-center rounded-pill border border-outline text-primary-500 transition-colors hover:border-primary-500 hover:bg-primary-50 active:bg-primary-100 md:h-[46px] md:w-[46px] ${className}`}
    >
      <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
    </button>
  );
}
