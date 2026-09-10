import { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

/**
 * ერთიანი ღილაკი — ყველა ვარიანტი და ზომა აქ ცხოვრობს.
 * `to` პროპით ავტომატურად ხდება <Link>, `href`-ით — <a>.
 */

const VARIANTS = {
  primary:
    'bg-primary-600 text-white shadow-sm hover:bg-primary-700 active:bg-primary-800 disabled:bg-primary-300',
  secondary:
    'bg-ink-900 text-white shadow-sm hover:bg-ink-800 active:bg-ink-950 disabled:bg-ink-400',
  accent:
    'bg-accent-600 text-white shadow-sm hover:bg-accent-700 active:bg-accent-800 disabled:bg-accent-200',
  outline:
    'border border-ink-300 bg-white text-ink-800 hover:border-primary-400 hover:bg-primary-50 hover:text-primary-700 active:bg-primary-100 disabled:text-ink-400',
  ghost:
    'text-ink-700 hover:bg-ink-100 active:bg-ink-200 disabled:text-ink-400',
  danger:
    'bg-danger-600 text-white shadow-sm hover:bg-danger-700 active:bg-danger-700 disabled:bg-danger-500/50',
  link: 'text-primary-700 underline-offset-4 hover:underline disabled:text-ink-400',
};

const SIZES = {
  xs: 'h-8 px-3 text-xs gap-1.5 rounded-control',
  sm: 'h-9 px-3.5 text-sm gap-2 rounded-control',
  md: 'h-11 px-5 text-sm gap-2 rounded-control',
  lg: 'h-12 px-6 text-base gap-2.5 rounded-control',
  icon: 'h-10 w-10 rounded-control',
};

const BASE =
  'inline-flex items-center justify-center font-semibold transition-colors duration-150 ' +
  'disabled:cursor-not-allowed select-none whitespace-nowrap';

const Button = forwardRef(function Button(
  {
    variant = 'primary',
    size = 'md',
    className = '',
    fullWidth = false,
    loading = false,
    disabled = false,
    to,
    href,
    type = 'button',
    children,
    ...rest
  },
  ref,
) {
  const classes = [
    BASE,
    VARIANTS[variant] || VARIANTS.primary,
    SIZES[size] || SIZES.md,
    fullWidth ? 'w-full' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </>
  );

  if (to && !disabled && !loading) {
    return (
      <Link ref={ref} to={to} className={classes} {...rest}>
        {content}
      </Link>
    );
  }

  if (href && !disabled && !loading) {
    return (
      <a ref={ref} href={href} className={classes} {...rest}>
        {content}
      </a>
    );
  }

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {content}
    </button>
  );
});

export default Button;
