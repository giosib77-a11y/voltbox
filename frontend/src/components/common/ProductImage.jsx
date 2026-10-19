import { useEffect, useState } from 'react';

/**
 * პროდუქტის სურათი lazy-loading-ით, skeleton-ითა და fallback-ით.
 * გარე სერვისზე დამოკიდებულება არ არსებობს — fallback ლოკალური SVG-ია.
 */

const FALLBACK_SRC = '/images/placeholder.svg';
// DESIGN.md §8: the shop's drawing for a missing photo, with no ground of its
// own (the tile gives it). Opt-in through `shopPlaceholder`; the admin shows
// the old file and does not pass it.
const SHOP_FALLBACK_SRC = '/images/placeholder-shop.svg';

export default function ProductImage({
  src,
  alt,
  className = '',
  imgClassName = '',
  loading = 'lazy',
  sizes,
  shopPlaceholder = false,
}) {
  const fallbackSrc = shopPlaceholder ? SHOP_FALLBACK_SRC : FALLBACK_SRC;
  const [status, setStatus] = useState('loading');
  const [currentSrc, setCurrentSrc] = useState(src || fallbackSrc);

  useEffect(() => {
    setCurrentSrc(src || fallbackSrc);
    setStatus('loading');
  }, [src, fallbackSrc]);

  return (
    <div className={`relative overflow-hidden bg-media ${className}`}>
      {status === 'loading' && (
        <div className="absolute inset-0 animate-pulse bg-media-shade/60" aria-hidden="true" />
      )}
      <img
        src={currentSrc}
        alt={alt}
        loading={loading}
        decoding="async"
        sizes={sizes}
        onLoad={() => setStatus('loaded')}
        onError={() => {
          if (currentSrc !== fallbackSrc) {
            setCurrentSrc(fallbackSrc);
          } else {
            setStatus('loaded');
          }
        }}
        className={`h-full w-full object-cover transition-opacity storefront:mix-blend-multiply duration-300 ${
          status === 'loaded' ? 'opacity-100' : 'opacity-0'
        } ${imgClassName}`}
      />
    </div>
  );
}
