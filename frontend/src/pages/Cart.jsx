import { useRef } from 'react';
import { ShoppingCart } from 'lucide-react';
import Breadcrumbs from '../components/common/Breadcrumbs.jsx';
import Button from '../components/common/Button.jsx';
import EmptyState from '../components/common/EmptyState.jsx';
import CartItem from '../components/cart/CartItem.jsx';
import CartSummary from '../components/cart/CartSummary.jsx';
import { useCart } from '../hooks/useCart.js';
import { useToast } from '../hooks/useToast.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import { useDeliveryRules } from '../hooks/useDeliveryRules.js';
import { amountToFreeDelivery, deliveryFee, totalWithDelivery } from '../utils/pricing.js';
import { useGuestCartQuote } from '../hooks/useGuestCartQuote.js';
import { t } from '../i18n/index.js';

/**
 * კალათის გვერდი. ავტორიზაცია არ არის საჭირო.
 */
export default function Cart() {
  useDocumentTitle(t('cart.title'));
  useGuestCartQuote();

  const { items, itemsCount, subtotal, savings, setQty, removeItem, restoreItem, clear } = useCart();
  // The cart does not know the city yet: the fee is known only once the basket
  // is free everywhere, and otherwise each city's fee is listed.
  const { rules } = useDeliveryRules();
  const shipping = deliveryFee(subtotal, rules);
  const toast = useToast();
  const lastRemoved = useRef(null);

  function handleRemove(productId) {
    const item = items.find((i) => i.productId === productId);
    if (!item) return;

    lastRemoved.current = item;
    removeItem(productId);

    toast.info(t('cart.removedNamed', { name: item.snapshot.name }), {
      action: {
        label: t('common.undo'),
        onClick: () => {
          if (lastRemoved.current) restoreItem(lastRemoved.current);
          lastRemoved.current = null;
        },
      },
    });
  }

  if (items.length === 0) {
    return (
      <div className="container-page py-5 lg:py-7">
        <Breadcrumbs items={[{ label: t('cart.title') }]} className="mb-4" />
        <EmptyState
          icon={ShoppingCart}
          title={t('cart.emptyTitle')}
          description={t('cart.emptyText')}
          actionLabel={t('common.backToShop')}
          actionTo="/"
        />
      </div>
    );
  }

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs items={[{ label: t('cart.title') }]} className="mb-4" />

      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-serif text-[28px] font-light leading-tight text-ink-900 lg:text-4xl">
          {t('cart.title')}
          <span className="ml-2 font-sans text-base font-normal text-ink-500">{t('cart.units', { count: itemsCount })}</span>
        </h1>
        <Button variant="link" size="sm" className="px-0" onClick={clear}>
          {t('cart.clear')}
        </Button>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_22.5rem] lg:gap-7">
        <div className="rounded-card border border-line bg-surface px-4 sm:px-6">
          <ul className="divide-y divide-line">
            {items.map((item) => (
              <CartItem
                key={item.productId}
                item={item}
                onQtyChange={setQty}
                onRemove={handleRemove}
              />
            ))}
          </ul>
        </div>

        <div>
          <div className="lg:sticky lg:top-[8.75rem]">
            <CartSummary
              subtotal={subtotal}
              shipping={shipping}
              total={totalWithDelivery(subtotal, shipping)}
              cities={rules?.cities}
              remaining={amountToFreeDelivery(subtotal, rules)}
              freeFrom={rules?.freeFrom}
              itemsCount={itemsCount}
              savings={savings}
              actionLabel={t('common.checkout')}
              actionTo="/checkout"
            >
              <Button variant="ghost" fullWidth className="mt-2" to="/">
                {t('common.continueShopping')}
              </Button>
            </CartSummary>
          </div>
        </div>
      </div>
    </div>
  );
}
