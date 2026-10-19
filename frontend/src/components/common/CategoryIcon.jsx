import {
  BatteryCharging,
  Cable,
  Headphones,
  Package,
  PlugZap,
  Smartphone,
} from 'lucide-react';

/**
 * `categories.js`-ის `icon` სტრიქონს აქცევს lucide-react კომპონენტად.
 * ახალი კატეგორიის დამატებისას აქ ემატება ერთი ჩანაწერი.
 */
const ICONS = {
  Smartphone,
  Cable,
  BatteryCharging,
  PlugZap,
  Headphones,
  Package,
};

/**
 * `framed` (opt-in, DESIGN.md §8): the icon at 28px (`icon-fine`) inside the
 * 70px ornamental diamond. The frame brightens when an ancestor `group` is
 * hovered. Without it the icon is drawn alone, as before.
 */
export default function CategoryIcon({ name, className = 'h-5 w-5', framed = false, frameClassName = '', ...rest }) {
  const Icon = ICONS[name] || Package;
  if (!framed) return <Icon className={className} aria-hidden="true" {...rest} />;

  return (
    <span
      className={`relative inline-flex h-[70px] w-[70px] shrink-0 items-center justify-center text-primary-500 ${frameClassName}`}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 70 70"
        className="absolute inset-0 h-full w-full opacity-60 transition-opacity group-hover:opacity-100"
        fill="none"
        stroke="currentColor"
        strokeWidth=".8"
        strokeLinejoin="round"
      >
        <path d="M35 2 68 35 35 68 2 35z" />
      </svg>
      <Icon className={`icon-fine h-7 w-7 ${className === 'h-5 w-5' ? '' : className}`} {...rest} />
    </span>
  );
}
