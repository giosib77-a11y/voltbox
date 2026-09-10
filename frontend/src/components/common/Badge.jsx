/**
 * პატარა ბეჯი — „ახალი“, „-20%“, „მარაგში არ არის“ და ა.შ.
 */

const TONES = {
  new: 'bg-primary-600 text-white',
  discount: 'bg-accent-600 text-white',
  danger: 'bg-ink-800 text-white',
  success: 'bg-success-50 text-success-700 ring-1 ring-inset ring-success-500/25',
  warning: 'bg-warning-50 text-warning-600 ring-1 ring-inset ring-warning-500/30',
  neutral: 'bg-ink-100 text-ink-700',
  outline: 'bg-white text-ink-700 ring-1 ring-inset ring-ink-300',
};

const SIZES = {
  sm: 'px-1.5 py-0.5 text-2xs',
  md: 'px-2 py-0.5 text-xs',
};

export default function Badge({ tone = 'neutral', size = 'md', className = '', children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-pill font-semibold leading-tight ${
        TONES[tone] || TONES.neutral
      } ${SIZES[size] || SIZES.md} ${className}`}
    >
      {children}
    </span>
  );
}
