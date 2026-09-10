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
import { TEXT } from '../constants/index.js';

/**
 * კალათის გვერდი. ავტორიზაცია არ არის საჭირო.
 */
export default function Cart() {
  useDocumentTitle('კალათა');

  const { items, itemsCount, subtotal, shipping, total, savings, setQty, removeItem, restoreItem, clear } =
    useCart();
  const toast = useToast();
  const lastRemoved = useRef(null);

  function handleRemove(productId) {
    const item = items.find((i) => i.productId === productId);
    if (!item) return;

    lastRemoved.current = item;
    removeItem(productId);

    toast.info(`${item.snapshot.name} — ${TEXT.removedFromCart}`, {
      action: {
        label: TEXT.undo,
        onClick: () => {
          if (lastRemoved.current) restoreItem(lastRemoved.current);
          lastRemoved.current = null;
        },
      },
    });
  }

  if (items.length === 0) {
    return (
      <div className="container-page py-6 lg:py-10">
        <Breadcrumbs items={[{ label: 'კალათა' }]} className="mb-5" />
        <EmptyState
          icon={ShoppingCart}
          title="თქვენი კალათა ცარიელია"
          description="დაათვალიერეთ კატალოგი და დაამატეთ პროდუქტები — შეკვეთისთვის რეგისტრაცია საჭირო არ არის."
          actionLabel={TEXT.backToShop}
          actionTo="/"
        />
      </div>
    );
  }

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs items={[{ label: 'კალათა' }]} className="mb-4" />

      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
          კალათა
          <span className="ml-2 text-base font-medium text-ink-500">{itemsCount} ცალი</span>
        </h1>
        <Button variant="link" size="sm" className="px-0" onClick={clear}>
          კალათის გასუფთავება
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem] lg:gap-7">
        <div className="rounded-card border border-ink-200 bg-white px-4 sm:px-5">
          <ul className="divide-y divide-ink-100">
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
          <div className="lg:sticky lg:top-[8.5rem]">
            <CartSummary
              subtotal={subtotal}
              shipping={shipping}
              total={total}
              itemsCount={itemsCount}
              savings={savings}
              actionLabel={TEXT.checkout}
              actionTo="/checkout"
            >
              <Button variant="ghost" fullWidth className="mt-2" to="/">
                {TEXT.continueShopping}
              </Button>
            </CartSummary>
          </div>
        </div>
      </div>
    </div>
  );
}
