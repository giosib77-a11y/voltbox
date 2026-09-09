import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Check, RotateCcw, ShieldCheck, ShoppingCart, Truck } from 'lucide-react';
import Breadcrumbs from '../components/common/Breadcrumbs.jsx';
import Button from '../components/common/Button.jsx';
import EmptyState from '../components/common/EmptyState.jsx';
import ErrorState from '../components/common/ErrorState.jsx';
import { Skeleton, TextSkeleton } from '../components/common/Skeleton.jsx';
import ProductGallery from '../components/product/ProductGallery.jsx';
import PriceTag from '../components/product/PriceTag.jsx';
import RatingStars from '../components/product/RatingStars.jsx';
import StockBadge from '../components/product/StockBadge.jsx';
import QuantityStepper from '../components/cart/QuantityStepper.jsx';
import ProductCarousel from '../components/product/ProductCarousel.jsx';
import { useProduct, useRelatedProducts, useCategories } from '../hooks/useProducts.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { useCart } from '../hooks/useCart.js';
import { useToast } from '../hooks/useToast.js';
import { formatPrice, formatSpecValue } from '../utils/format.js';
import { DELIVERY_INFO, SHIPPING, SPEC_LABELS, TEXT } from '../constants/index.js';

const TABS = [
  { id: 'description', label: 'აღწერა' },
  { id: 'specs', label: 'მახასიათებლები' },
  { id: 'delivery', label: 'მიწოდება' },
];

export default function ProductDetails() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { data: product, loading, error, reload } = useProduct(slug);
  const { data: related, loading: relatedLoading } = useRelatedProducts(product?.id, 4);
  const { data: categories } = useCategories();
  const { addItem, quantities } = useCart();
  const toast = useToast();

  const [qty, setQty] = useState(1);
  const [tab, setTab] = useState('description');

  // ახალ პროდუქტზე გადასვლისას რაოდენობა თავიდან იწყება
  useEffect(() => {
    setQty(1);
  }, [slug]);

  useDocumentTitle(product?.name || (loading ? 'იტვირთება…' : 'პროდუქტი'));

  const category = useMemo(
    () => (categories || []).find((c) => c.id === product?.category) || null,
    [categories, product],
  );

  if (loading) return <ProductDetailsSkeleton />;

  if (error) {
    const isNotFound = error.status === 404;
    return (
      <div className="container-page py-14">
        {isNotFound ? (
          <EmptyState
            title="პროდუქტი ვერ მოიძებნა"
            description="შესაძლოა ის აღარ იყიდება ან მისამართი არასწორია."
            actionLabel={TEXT.backToShop}
            actionTo="/"
          />
        ) : (
          <ErrorState error={error} onRetry={reload} />
        )}
      </div>
    );
  }

  if (!product) return null;

  const inCartQty = quantities[product.id] || 0;
  const savings = product.hasDiscount ? product.oldPrice - product.price : 0;

  function handleAddToCart() {
    addItem(product, qty);
    toast.success(`${product.name} — ${TEXT.addedToCart}`, {
      action: { label: 'კალათაში გადასვლა', onClick: () => navigate('/cart') },
    });
  }

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs
        items={[
          ...(category ? [{ label: category.name, to: `/category/${category.slug}` }] : []),
          { label: product.name },
        ]}
        className="mb-5"
      />

      <div className="grid gap-7 lg:grid-cols-2 lg:gap-10">
        <ProductGallery images={product.images} alt={product.name} />

        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-primary-700">
            {product.brand}
          </p>
          <h1 className="mt-1.5 text-2xl font-bold leading-tight tracking-tight text-ink-900 sm:text-3xl">
            {product.name}
          </h1>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <RatingStars
              rating={product.rating}
              reviewsCount={product.reviewsCount}
              size="md"
              showValue
              showReviewsLabel
            />
            <StockBadge stock={product.stock} isLowStock={product.isLowStock} />
          </div>

          <p className="mt-4 text-sm leading-relaxed text-ink-600">{product.shortDescription}</p>

          <div className="mt-5 rounded-card border border-ink-200 bg-white p-4">
            <PriceTag
              price={product.price}
              oldPrice={product.oldPrice}
              discountPercent={product.discountPercent}
              size="lg"
              showBadge
            />
            {savings > 0 && (
              <p className="mt-1.5 text-sm font-medium text-accent-600">
                დაზოგავთ {formatPrice(savings)}
              </p>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <QuantityStepper
                value={qty}
                min={1}
                max={product.stock > 0 ? product.stock : 1}
                onChange={setQty}
                disabled={!product.inStock}
              />
              <Button
                size="lg"
                className="min-w-[12rem] flex-1"
                onClick={handleAddToCart}
                disabled={!product.inStock}
              >
                <ShoppingCart className="h-4 w-4" aria-hidden="true" />
                {product.inStock ? TEXT.addToCart : TEXT.outOfStock}
              </Button>
            </div>

            {inCartQty > 0 && (
              <p className="mt-3 flex items-center gap-1.5 text-sm font-medium text-success-700">
                <Check className="h-4 w-4" aria-hidden="true" />
                კალათაშია {inCartQty} ცალი
              </p>
            )}
          </div>

          <ul className="mt-5 grid gap-2.5 text-sm text-ink-600 sm:grid-cols-2">
            <li className="flex items-start gap-2.5">
              <Truck className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" aria-hidden="true" />
              მიწოდება {SHIPPING.etaDays}
            </li>
            <li className="flex items-start gap-2.5">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" aria-hidden="true" />
              გარანტია {formatSpecValue(product.specs?.warranty || '12 თვე')}
            </li>
            <li className="flex items-start gap-2.5">
              <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" aria-hidden="true" />
              დაბრუნება 14 დღეში
            </li>
            <li className="flex items-start gap-2.5">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" aria-hidden="true" />
              ორიგინალი პროდუქცია
            </li>
          </ul>
        </div>
      </div>

      <ProductTabs product={product} tab={tab} onTabChange={setTab} />

      <ProductCarousel
        title="მსგავსი პროდუქტები"
        products={related || []}
        loading={relatedLoading}
      />
    </div>
  );
}

/** Tab-ები: აღწერა | მახასიათებლები | მიწოდება */
function ProductTabs({ product, tab, onTabChange }) {
  const specEntries = Object.entries(product.specs || {});

  return (
    <section className="mt-10 rounded-card border border-ink-200 bg-white">
      <div role="tablist" aria-label="პროდუქტის დეტალები" className="flex overflow-x-auto border-b border-ink-200">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`panel-${item.id}`}
            onClick={() => onTabChange(item.id)}
            className={`shrink-0 border-b-2 px-5 py-3.5 text-sm font-semibold transition-colors ${
              tab === item.id
                ? 'border-primary-600 text-primary-700'
                : 'border-transparent text-ink-600 hover:text-ink-900'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="p-5 sm:p-6">
        {tab === 'description' && (
          <div role="tabpanel" id="panel-description" aria-labelledby="tab-description">
            <p className="max-w-3xl text-sm leading-relaxed text-ink-700">{product.description}</p>
            {product.tags?.length > 0 && (
              <ul className="mt-5 flex flex-wrap gap-2">
                {product.tags.map((tag) => (
                  <li
                    key={tag}
                    className="rounded-pill bg-ink-100 px-2.5 py-1 text-xs font-medium text-ink-600"
                  >
                    #{tag}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === 'specs' && (
          <div role="tabpanel" id="panel-specs" aria-labelledby="tab-specs">
            <table className="w-full max-w-2xl text-sm">
              <caption className="sr-only">{product.name} — ტექნიკური მახასიათებლები</caption>
              <tbody>
                {specEntries.map(([key, value]) => (
                  <tr key={key} className="border-b border-ink-100 last:border-b-0">
                    <th scope="row" className="w-1/2 py-2.5 pr-4 text-left font-medium text-ink-500">
                      {SPEC_LABELS[key] || key}
                    </th>
                    <td className="py-2.5 font-semibold text-ink-900">{formatSpecValue(value)}</td>
                  </tr>
                ))}
                <tr className="border-t border-ink-100">
                  <th scope="row" className="py-2.5 pr-4 text-left font-medium text-ink-500">
                    ბრენდი
                  </th>
                  <td className="py-2.5 font-semibold text-ink-900">{product.brand}</td>
                </tr>
                {product.brandCountry && (
                  <tr className="border-t border-ink-100">
                    <th scope="row" className="py-2.5 pr-4 text-left font-medium text-ink-500">
                      {SPEC_LABELS.origin}
                    </th>
                    <td className="py-2.5 font-semibold text-ink-900">{product.brandCountry}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {tab === 'delivery' && (
          <div role="tabpanel" id="panel-delivery" aria-labelledby="tab-delivery" className="grid gap-5 sm:grid-cols-2">
            {DELIVERY_INFO.map((info) => (
              <div key={info.title}>
                <h3 className="text-sm font-bold text-ink-900">{info.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-600">{info.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function ProductDetailsSkeleton() {
  return (
    <div className="container-page py-5 lg:py-7">
      <Skeleton className="mb-5 h-4 w-64" />
      <div className="grid gap-7 lg:grid-cols-2 lg:gap-10">
        <ProductGallery loading images={[]} />
        <div className="space-y-4">
          <Skeleton className="h-3.5 w-24" />
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-4 w-40" />
          <TextSkeleton lines={2} />
          <Skeleton className="h-44 w-full" rounded="rounded-card" />
        </div>
      </div>
      <Skeleton className="mt-10 h-64 w-full" rounded="rounded-card" />
    </div>
  );
}
