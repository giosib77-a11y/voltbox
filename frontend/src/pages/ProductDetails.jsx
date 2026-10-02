import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
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
import { productStructuredData, usePageMeta } from '../hooks/usePageMeta.js';
import { useCart } from '../hooks/useCart.js';
import { useToast } from '../hooks/useToast.js';
import { formatPrice, formatSpecValue } from '../utils/format.js';
import { useDeliveryRules } from '../hooks/useDeliveryRules.js';
import { i18n, t } from '../i18n/index.js';

// Each tab's label is `product.tabs.<id>`.
const TABS = ['description', 'specs', 'delivery'];

/** The returns and warranty cards of the delivery tab, which hold no prices. */
const DELIVERY_INFO = [
  { title: 'deliveryInfo.returnsTitle', text: 'deliveryInfo.returnsText' },
  { title: 'deliveryInfo.warrantyTitle', text: 'deliveryInfo.warrantyText' },
];

/** A spec key's label, or the key itself when there is none. */
function specLabel(key) {
  return i18n.exists(`specs.${key}`) ? t(`specs.${key}`) : key;
}

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

  useDocumentTitle(product?.name || (loading ? t('common.loading') : t('product.title')));
  usePageMeta({
    description: product?.shortDescription,
    canonical: product ? `/product/${product.slug}` : undefined,
    // Google renders the page, so this reaches it. The price and the
    // availability are the two fields it shows beside a result.
    structuredData: productStructuredData(product),
  });

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
            title={t('product.notFound')}
            description={t('product.notFoundText')}
            actionLabel={t('common.backToShop')}
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
    toast.success(t('product.addedNamed', { name: product.name }), {
      action: { label: t('product.goToCart'), onClick: () => navigate('/cart') },
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

          <div className="mt-5 rounded-card border border-ink-200 bg-surface p-4">
            <PriceTag
              price={product.price}
              oldPrice={product.oldPrice}
              discountPercent={product.discountPercent}
              size="lg"
              showBadge
            />
            {savings > 0 && (
              <p className="mt-1.5 text-sm font-medium text-accent-fg">
                {t('product.youSave', { price: formatPrice(savings) })}
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
                {product.inStock ? t('common.addToCart') : t('common.outOfStock')}
              </Button>
            </div>

            {inCartQty > 0 && (
              <p className="mt-3 flex items-center gap-1.5 text-sm font-medium text-success-700">
                <Check className="h-4 w-4" aria-hidden="true" />
                {t('product.inCartUnits', { count: inCartQty })}
              </p>
            )}
          </div>

          <ul className="mt-5 grid gap-2.5 text-sm text-ink-600 sm:grid-cols-2">
            <li className="flex items-start gap-2.5">
              <Truck className="mt-0.5 h-4 w-4 shrink-0 text-primary-700" aria-hidden="true" />
              {t('product.delivery', { eta: t('shipping.etaDays') })}
            </li>
            <li className="flex items-start gap-2.5">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary-700" aria-hidden="true" />
              {t('product.warranty', { period: formatSpecValue(product.specs?.warranty || t('product.defaultWarranty')) })}
            </li>
            <li className="flex items-start gap-2.5">
              <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-primary-700" aria-hidden="true" />
              {t('product.returns')}
            </li>
            <li className="flex items-start gap-2.5">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary-700" aria-hidden="true" />
              {t('product.original')}
            </li>
          </ul>
        </div>
      </div>

      <ProductTabs product={product} tab={tab} onTabChange={setTab} />

      <ProductCarousel
        title={t('product.related')}
        products={related || []}
        loading={relatedLoading}
      />
    </div>
  );
}

/** Tab-ები: აღწერა | მახასიათებლები | მიწოდება */
function ProductTabs({ product, tab, onTabChange }) {
  // Where the shop delivers and for how much, from GET /delivery - the table the
  // checkout charges by. The static entries after it hold no prices.
  const { rules } = useDeliveryRules();
  const translatedInfo = DELIVERY_INFO.map((info) => ({ title: t(info.title), text: t(info.text) }));
  const deliveryInfo = rules
    ? [
        {
          title: t('product.courierTitle'),
          text: t('product.courierText', {
            cities: rules.cities.map((c) => `${c.name} — ${formatPrice(c.fee)}`).join(', '),
            price: formatPrice(rules.freeFrom),
          }),
        },
        ...translatedInfo,
      ]
    : translatedInfo;
  const specEntries = Object.entries(product.specs || {});

  return (
    <section className="mt-10 rounded-card border border-ink-200 bg-surface">
      <div role="tablist" aria-label={t('product.detailsLabel')} className="flex overflow-x-auto border-b border-ink-200">
        {TABS.map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            onClick={() => onTabChange(id)}
            className={`shrink-0 border-b-2 px-5 py-3.5 text-sm font-semibold transition-colors ${
              tab === id
                ? 'border-primary-600 text-primary-700'
                : 'border-transparent text-ink-600 hover:text-ink-900'
            }`}
          >
            {t(`product.tabs.${id}`)}
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
              <caption className="sr-only">{t('product.specsCaption', { name: product.name })}</caption>
              <tbody>
                {specEntries.map(([key, value]) => (
                  <tr key={key} className="border-b border-ink-100 last:border-b-0">
                    <th scope="row" className="w-1/2 py-2.5 pr-4 text-left font-medium text-ink-500">
                      {specLabel(key)}
                    </th>
                    <td className="py-2.5 font-semibold text-ink-900">{formatSpecValue(value)}</td>
                  </tr>
                ))}
                <tr className="border-t border-ink-100">
                  <th scope="row" className="py-2.5 pr-4 text-left font-medium text-ink-500">
                    {t('search.filterBrand')}
                  </th>
                  <td className="py-2.5 font-semibold text-ink-900">{product.brand}</td>
                </tr>
                {product.brandCountry && (
                  <tr className="border-t border-ink-100">
                    <th scope="row" className="py-2.5 pr-4 text-left font-medium text-ink-500">
                      {t('specs.origin')}
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
            {deliveryInfo.map((info) => (
              <div key={info.title}>
                {/* h2, not h3: the page has one h1 (the product name) and nothing
                    between, and a reader navigating by heading level should not
                    find a gap. The size comes from the class either way. */}
                <h2 className="text-sm font-bold text-ink-900">{info.title}</h2>
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
