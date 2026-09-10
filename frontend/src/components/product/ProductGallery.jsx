import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import ProductImage from '../common/ProductImage.jsx';
import { Skeleton } from '../common/Skeleton.jsx';

/**
 * პროდუქტის გალერეა: დიდი ფოტო zoom-ით, thumbnails, ისრები და swipe.
 * კლავიატურით ნავიგაცია: ← →
 */
export default function ProductGallery({ images = [], alt = '', loading = false }) {
  const [index, setIndex] = useState(0);
  const [zoom, setZoom] = useState(null);
  const touchStart = useRef(null);

  const total = images.length;

  const go = useCallback(
    (delta) => {
      if (total < 2) return;
      setIndex((current) => (current + delta + total) % total);
    },
    [total],
  );

  useEffect(() => {
    setIndex(0);
  }, [images]);

  function handleKeyDown(event) {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      go(1);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      go(-1);
    }
  }

  function handleMouseMove(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    setZoom({
      x: ((event.clientX - rect.left) / rect.width) * 100,
      y: ((event.clientY - rect.top) / rect.height) * 100,
    });
  }

  function handleTouchStart(event) {
    touchStart.current = event.touches[0].clientX;
  }

  function handleTouchEnd(event) {
    if (touchStart.current === null) return;
    const delta = event.changedTouches[0].clientX - touchStart.current;
    if (Math.abs(delta) > 45) go(delta < 0 ? 1 : -1);
    touchStart.current = null;
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="aspect-square w-full" rounded="rounded-card" />
        <div className="flex gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-20" rounded="rounded-control" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        role="group"
        aria-roledescription="გალერეა"
        aria-label={`${alt} — სურათი ${index + 1} / ${total}`}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setZoom(null)}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        className="group relative aspect-square overflow-hidden rounded-card border border-ink-200 bg-white"
      >
        <img
          src={images[index]}
          alt={`${alt} — სურათი ${index + 1}`}
          className="h-full w-full object-cover transition-transform duration-200"
          style={
            zoom
              ? { transform: 'scale(1.8)', transformOrigin: `${zoom.x}% ${zoom.y}%` }
              : undefined
          }
          onError={(event) => {
            event.currentTarget.src = '/images/placeholder.svg';
          }}
        />

        {total > 1 && (
          <>
            <button
              type="button"
              onClick={() => go(-1)}
              aria-label="წინა სურათი"
              className="absolute left-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-ink-700 shadow-card transition-opacity hover:bg-white lg:opacity-0 lg:group-hover:opacity-100"
            >
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => go(1)}
              aria-label="შემდეგი სურათი"
              className="absolute right-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-ink-700 shadow-card transition-opacity hover:bg-white lg:opacity-0 lg:group-hover:opacity-100"
            >
              <ChevronRight className="h-5 w-5" aria-hidden="true" />
            </button>

            <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-1.5 lg:hidden">
              {images.map((image, i) => (
                <span
                  key={image}
                  className={`h-1.5 rounded-pill transition-all ${
                    i === index ? 'w-5 bg-primary-600' : 'w-1.5 bg-ink-300'
                  }`}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {total > 1 && (
        <div className="flex gap-3 overflow-x-auto pb-1">
          {images.map((image, i) => (
            <button
              key={image}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`სურათი ${i + 1}`}
              aria-current={i === index}
              className={`shrink-0 overflow-hidden rounded-control border-2 transition-colors ${
                i === index ? 'border-primary-600' : 'border-ink-200 hover:border-ink-300'
              }`}
            >
              <ProductImage src={image} alt="" className="h-16 w-16 sm:h-20 sm:w-20" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
