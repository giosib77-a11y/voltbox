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

export default function CategoryIcon({ name, className = 'h-5 w-5', ...rest }) {
  const Icon = ICONS[name] || Package;
  return <Icon className={className} aria-hidden="true" {...rest} />;
}
