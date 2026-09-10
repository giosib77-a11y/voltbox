import { useEffect, useState } from 'react';

/**
 * პროდუქტის სურათი lazy-loading-ით, skeleton-ითა და fallback-ით.
 * გარე სერვისზე დამოკიდებულება არ არსებობს — fallback ლოკალური SVG-ია.
 */

const FALLBACK_SRC = '/images/placeholder.svg';

export default function ProductImage({
  src,
  alt,
  className = '',
  imgClassName = '',
  loading = 'lazy',
  sizes,
}) {
  const [status, setStatus] = useState('loading');
  const [currentSrc, setCurrentSrc] = useState(src || FALLBACK_SRC);

  useEffect(() => {
    setCurrentSrc(src || FALLBACK_SRC);
    setStatus('loading');
  }, [src]);

  return (
    <div className={`relative overflow-hidden bg-ink-100 ${className}`}>
      {status === 'loading' && (
        <div className="absolute inset-0 animate-pulse bg-ink-200/60" aria-hidden="true" />
      )}
      <img
        src={currentSrc}
        alt={alt}
        loading={loading}
        decoding="async"
        sizes={sizes}
        onLoad={() => setStatus('loaded')}
        onError={() => {
          if (currentSrc !== FALLBACK_SRC) {
            setCurrentSrc(FALLBACK_SRC);
          } else {
            setStatus('loaded');
          }
        }}
        className={`h-full w-full object-cover transition-opacity duration-300 ${
          status === 'loaded' ? 'opacity-100' : 'opacity-0'
        } ${imgClassName}`}
      />
    </div>
  );
}
