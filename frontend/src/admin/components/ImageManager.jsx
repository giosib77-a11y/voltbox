/**
 * ImageManager: the Images section of the product form.
 *
 * What it does: upload, choose the primary image, reorder and delete.
 * Where it fits: ProductForm, but only in edit mode.
 * Notes: uploads need a product id, so on a new product this section stays
 * locked until the product is saved. That is what keeps orphaned objects out of
 * the bucket - a file uploaded for a product that was never created has nothing
 * pointing at it and nobody would ever find it again.
 */

import { useRef, useState } from 'react';
import { ImagePlus, Star, Trash2 } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import ProductImage from '../../components/common/ProductImage.jsx';
import * as adminApi from '../adminApi.js';

export default function ImageManager({ productId, images, onChange, onError }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setBusy(true);
    onError(null);
    try {
      await action();
    } catch (caught) {
      onError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    // Clear immediately so choosing the same file twice still fires a change.
    event.target.value = '';
    if (!file) return;
    await run(async () => {
      await adminApi.uploadProductImage(productId, file);
      onChange(await adminApi.getProduct(productId));
    });
  }

  async function handlePrimary(imageId) {
    await run(async () => {
      await adminApi.setPrimaryImage(productId, imageId);
      onChange(await adminApi.getProduct(productId));
    });
  }

  async function handleDelete(imageId) {
    await run(async () => {
      await adminApi.deleteProductImage(productId, imageId);
      onChange(await adminApi.getProduct(productId));
    });
  }

  async function move(index, direction) {
    const next = [...images];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    await run(async () => {
      await adminApi.reorderProductImages(
        productId,
        next.map((image) => image.id),
      );
      onChange(await adminApi.getProduct(productId));
    });
  }

  return (
    <div>
      <div className="flex flex-wrap gap-3">
        {images.map((image, index) => (
          <figure
            key={image.id}
            className="w-32 rounded-lg border border-ink-200 bg-white p-2 text-center"
          >
            <ProductImage
              src={image.url}
              alt={image.alt}
              className="h-24 w-full rounded object-cover"
            />
            <figcaption className="mt-1 text-xs text-ink-600">
              {image.isPrimary ? (
                <span className="font-medium text-accent-700">მთავარი</span>
              ) : (
                <button
                  type="button"
                  onClick={() => handlePrimary(image.id)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 hover:text-accent-700 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-700"
                >
                  <Star className="h-3 w-3" aria-hidden="true" />
                  მთავრად
                </button>
              )}
            </figcaption>
            <div className="mt-1 flex justify-center gap-1">
              <button
                type="button"
                onClick={() => move(index, -1)}
                disabled={busy || index === 0}
                aria-label="მარცხნივ გადატანა"
                className="rounded px-1.5 text-ink-600 hover:bg-ink-100 disabled:opacity-30"
              >
                ←
              </button>
              <button
                type="button"
                onClick={() => move(index, 1)}
                disabled={busy || index === images.length - 1}
                aria-label="მარჯვნივ გადატანა"
                className="rounded px-1.5 text-ink-600 hover:bg-ink-100 disabled:opacity-30"
              >
                →
              </button>
              <button
                type="button"
                onClick={() => handleDelete(image.id)}
                disabled={busy}
                aria-label="სურათის წაშლა"
                className="rounded px-1.5 text-danger-600 hover:bg-danger-50 disabled:opacity-30"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </figure>
        ))}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleUpload}
        className="sr-only"
        aria-label="სურათის ატვირთვა"
      />
      <Button
        variant="outline"
        size="sm"
        className="mt-3"
        onClick={() => inputRef.current?.click()}
        loading={busy}
      >
        <ImagePlus className="h-4 w-4" aria-hidden="true" />
        სურათის ატვირთვა
      </Button>
      <p className="mt-2 text-xs text-ink-500">JPEG, PNG ან WebP, მაქსიმუმ 5 MB.</p>
    </div>
  );
}
