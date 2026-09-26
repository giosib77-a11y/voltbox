import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { LogIn, ShieldCheck } from 'lucide-react';
import Breadcrumbs from '../components/common/Breadcrumbs.jsx';
import Input from '../components/common/Input.jsx';
import Select from '../components/common/Select.jsx';
import Textarea from '../components/common/Textarea.jsx';
import EmptyState from '../components/common/EmptyState.jsx';
import CartSummary from '../components/cart/CartSummary.jsx';
import ProductImage from '../components/common/ProductImage.jsx';
import { useCart } from '../hooks/useCart.js';
import { useAuth } from '../hooks/useAuth.js';
import { useIdempotencyKey } from '../hooks/useIdempotencyKey.js';
import { loadDeliveryRules, useDeliveryRules } from '../hooks/useDeliveryRules.js';
import { useToast } from '../hooks/useToast.js';
import { useDocumentTitle } from '../hooks/useDocumentTitle.js';
import * as api from '../services/api.js';
import { formatPhone, formatPrice } from '../utils/format.js';
import { amountToFreeDelivery, deliveryFee, totalWithDelivery } from '../utils/pricing.js';
import { CHECKOUT_FIELDS, digitsOnly, validateField, validateForm } from '../utils/validate.js';
import { OFFERED_PAYMENT_METHODS, TEXT } from '../constants/index.js';

const EMPTY_FORM = {
  firstName: '',
  lastName: '',
  phone: '',
  city: '',
  address: '',
  comment: '',
  paymentMethod: OFFERED_PAYMENT_METHODS[0].value,
};

/**
 * შეკვეთის გაფორმება. რეგისტრაცია სავალდებულო *არ* არის —
 * შესვლის ბანერი ინფორმაციულია და ფორმას არ ბლოკავს.
 */
export default function Checkout() {
  useDocumentTitle('შეკვეთის გაფორმება');

  const navigate = useNavigate();
  const { items, itemsCount, subtotal, savings, clear } = useCart();
  const { rules, error: rulesError, reload: reloadRules } = useDeliveryRules();
  const { user, isAuthenticated } = useAuth();
  const toast = useToast();

  const [values, setValues] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);

  // ერთი შეკვეთის მცდელობის იდენტიფიკატორი. ხელახლა მხოლოდ მაშინ გენერირდება,
  // როცა თავად შეკვეთა იცვლება — ორმაგი დაჭერა და timeout-ის შემდეგი ცდა
  // იმავე გასაღებით მიდის, ამიტომ სერვერი მეორე შეკვეთას არ ქმნის.
  const attemptSignature = useMemo(
    () =>
      JSON.stringify({
        items: items.map((item) => [item.productId, item.qty]),
        firstName: values.firstName.trim(),
        lastName: values.lastName.trim(),
        phone: digitsOnly(values.phone),
        city: values.city,
        address: values.address.trim(),
        comment: values.comment.trim(),
        paymentMethod: values.paymentMethod,
      }),
    [items, values],
  );
  const [idempotencyKey, resetIdempotencyKey] = useIdempotencyKey(attemptSignature);

  // ავტორიზებულის მონაცემებით წინასწარი შევსება
  useEffect(() => {
    if (!user) return;
    setValues((current) => ({
      ...current,
      firstName: current.firstName || user.firstName || '',
      lastName: current.lastName || user.lastName || '',
      phone: current.phone || (user.phone ? formatPhone(user.phone) : ''),
    }));
  }, [user]);

  // მიწოდების ველებს მომხმარებელი თუ ერთხელ მაინც შეეხო (ბრაუზერის autofill-იც
  // ითვლება), შენახული მისამართი მათ აღარ ეხება — გვიან მოსული პასუხიც კი
  const deliveryEditedRef = useRef(false);

  // ნაგულისხმევი მისამართი ცალკე endpoint-ზეა და `user`-ში არ მოდის.
  // ქალაქი და მისამართი ერთად ივსება ან საერთოდ არა: აკრეფილ ქუჩასთან შენახული
  // ქალაქის მიწებება ორი სხვადასხვა მისამართის ნაზავს მისცემდა. ეს ერთადერთი
  // პირობა იდემპოტენტობის გასაღებსაც იცავს: სავალდებულო ველები ცარიელი ვერ
  // იქნება გაგზავნისას, ამიტომ პასუხი უკვე გაგზავნილ შეკვეთას ვეღარ შეცვლის.
  const userId = user?.id;
  useEffect(() => {
    if (!userId) return undefined;
    let cancelled = false;
    // The rules too: a saved city is filled in only if the shop delivers there.
    Promise.all([api.getAddresses(), loadDeliveryRules()])
      .then(([addresses, delivery]) => {
        const saved = Array.isArray(addresses) ? addresses.find((a) => a.isDefault) : null;
        if (cancelled || !saved || deliveryEditedRef.current) return;
        setValues((current) => {
          if (current.city || current.address) return current;
          return {
            ...current,
            // სიაში არმყოფ ქალაქს select ვერ აჩვენებს — მაშინ ირჩევს თავად
            city: delivery.cities.some((c) => c.name === saved.city) ? saved.city : '',
            address: saved.address || '',
          };
        });
      })
      .catch(() => {
        // შევსება მხოლოდ მოხერხებულობაა — ცარიელი ველებით შეკვეთა ისევ მუშაობს
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  // Only the cities the shop delivers to, each with its fee, from GET /delivery.
  const cityOptions = useMemo(
    () =>
      (rules?.cities || []).map((city) => ({
        value: city.name,
        label: `${city.name} — ${formatPrice(city.fee)}`,
      })),
    [rules],
  );
  // What this order will be charged, as the server will compute it; null until
  // a city is chosen (unless the basket is free everywhere).
  const shipping = deliveryFee(subtotal, rules, values.city);

  function handleChange(name, rawValue) {
    const value = name === 'phone' ? formatPhone(rawValue) : rawValue;
    if (name === 'city' || name === 'address') deliveryEditedRef.current = true;
    setValues((current) => ({ ...current, [name]: value }));
    if (touched[name]) {
      setErrors((current) => ({ ...current, [name]: validateField(name, value, values) }));
    }
  }

  function handleBlur(name) {
    setTouched((current) => ({ ...current, [name]: true }));
    setErrors((current) => ({ ...current, [name]: validateField(name, values[name], values) }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    // ღილაკი `loading`-ითაც იბლოკება, მაგრამ Enter-ით გაგზავნა მას გვერდს უვლის
    if (submitting) return;
    const nextErrors = validateForm(values, CHECKOUT_FIELDS);
    setErrors(nextErrors);
    setTouched(Object.fromEntries(CHECKOUT_FIELDS.map((field) => [field, true])));

    if (Object.keys(nextErrors).length > 0) {
      const firstField = CHECKOUT_FIELDS.find((field) => nextErrors[field]);
      document.getElementById(`checkout-${firstField}`)?.focus();
      toast.error('შეავსეთ სავალდებულო ველები სწორად');
      return;
    }

    setSubmitting(true);
    try {
      const order = await api.createOrder({
        items,
        customer: {
          firstName: values.firstName.trim(),
          lastName: values.lastName.trim(),
          phone: digitsOnly(values.phone),
          city: values.city,
          address: values.address.trim(),
          comment: values.comment.trim(),
        },
        paymentMethod: values.paymentMethod,
        idempotencyKey,
      });

      resetIdempotencyKey();
      clear();
      navigate(`/checkout/success/${order.orderNumber}`, { replace: true });
    } catch (error) {
      toast.error(error?.message || 'შეკვეთის გაფორმება ვერ მოხერხდა. სცადეთ ხელახლა.');
    } finally {
      setSubmitting(false);
    }
  }

  if (items.length === 0) {
    return (
      <div className="container-page py-6 lg:py-10">
        <Breadcrumbs items={[{ label: 'შეკვეთის გაფორმება' }]} className="mb-5" />
        <EmptyState
          title="კალათა ცარიელია"
          description="შეკვეთის გასაფორმებლად ჯერ დაამატეთ პროდუქტები კალათაში."
          actionLabel={TEXT.backToShop}
          actionTo="/"
        />
      </div>
    );
  }

  return (
    <div className="container-page py-5 lg:py-7">
      <Breadcrumbs
        items={[{ label: 'კალათა', to: '/cart' }, { label: 'შეკვეთის გაფორმება' }]}
        className="mb-4"
      />

      <h1 className="mb-5 text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
        შეკვეთის გაფორმება
      </h1>

      {!isAuthenticated && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-card border border-primary-200 bg-primary-50 px-4 py-3">
          <p className="flex items-center gap-2 text-sm text-primary-900">
            <LogIn className="h-4 w-4 shrink-0" aria-hidden="true" />
            უკვე გაქვთ ანგარიში? შესვლა შეკვეთის ისტორიას შეინახავს — თუმცა სავალდებულო არ არის.
          </p>
          <Link
            to="/login?redirect=/checkout"
            className="shrink-0 text-sm font-semibold text-primary-700 underline-offset-4 hover:underline"
          >
            შესვლა
          </Link>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="grid gap-6 lg:grid-cols-[1fr_22rem] lg:gap-7">
        <div className="space-y-5">
          <fieldset className="rounded-card border border-ink-200 bg-surface p-5">
            <legend className="px-1 text-base font-bold text-ink-900">მიმღების მონაცემები</legend>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Input
                id="checkout-firstName"
                label="სახელი"
                required
                value={values.firstName}
                error={touched.firstName ? errors.firstName : ''}
                onChange={(e) => handleChange('firstName', e.target.value)}
                onBlur={() => handleBlur('firstName')}
                autoComplete="given-name"
              />
              <Input
                id="checkout-lastName"
                label="გვარი"
                required
                value={values.lastName}
                error={touched.lastName ? errors.lastName : ''}
                onChange={(e) => handleChange('lastName', e.target.value)}
                onBlur={() => handleBlur('lastName')}
                autoComplete="family-name"
              />
              <Input
                id="checkout-phone"
                label="ტელეფონი"
                required
                inputMode="tel"
                placeholder="5XX XX XX XX"
                hint="ქართული მობილური ნომერი"
                value={values.phone}
                error={touched.phone ? errors.phone : ''}
                onChange={(e) => handleChange('phone', e.target.value)}
                onBlur={() => handleBlur('phone')}
                autoComplete="tel"
              />
              <Select
                id="checkout-city"
                label="ქალაქი"
                required
                placeholder="აირჩიეთ ქალაქი"
                options={cityOptions}
                value={values.city}
                hint={rulesError ? '' : 'მიწოდება ამ ეტაპზე მხოლოდ ამ ქალაქებშია'}
                error={
                  rulesError
                    ? 'ქალაქების სია ვერ ჩაიტვირთა.'
                    : touched.city
                      ? errors.city
                      : ''
                }
                onChange={(e) => handleChange('city', e.target.value)}
                onBlur={() => handleBlur('city')}
                autoComplete="address-level2"
              />
            </div>
            {rulesError && (
              <button
                type="button"
                onClick={reloadRules}
                className="mt-2 text-sm font-semibold text-primary-700 underline-offset-4 hover:underline"
              >
                {TEXT.retry}
              </button>
            )}

            <div className="mt-4 grid gap-4">
              <Input
                id="checkout-address"
                label="მისამართი"
                required
                placeholder="ქუჩა, ნომერი, სადარბაზო, ბინა"
                value={values.address}
                error={touched.address ? errors.address : ''}
                onChange={(e) => handleChange('address', e.target.value)}
                onBlur={() => handleBlur('address')}
                autoComplete="street-address"
              />
              <Textarea
                id="checkout-comment"
                label="კომენტარი"
                rows={3}
                placeholder="დამატებითი ინფორმაცია კურიერისთვის (არასავალდებულო)"
                value={values.comment}
                onChange={(e) => handleChange('comment', e.target.value)}
              />
            </div>
          </fieldset>

          <fieldset className="rounded-card border border-ink-200 bg-surface p-5">
            <legend className="px-1 text-base font-bold text-ink-900">გადახდის მეთოდი</legend>
            <div className="mt-4 space-y-2.5">
              {OFFERED_PAYMENT_METHODS.map((method) => (
                <label
                  key={method.value}
                  className={`flex cursor-pointer items-center gap-3 rounded-control border px-4 py-3 transition-colors ${
                    values.paymentMethod === method.value
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-ink-200 hover:border-ink-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="paymentMethod"
                    value={method.value}
                    checked={values.paymentMethod === method.value}
                    onChange={(e) => handleChange('paymentMethod', e.target.value)}
                    className="h-4 w-4 accent-primary-600"
                  />
                  <span className="text-sm font-medium text-ink-800">{method.label}</span>
                </label>
              ))}
            </div>
            <p className="mt-3 flex items-center gap-2 text-xs text-ink-500">
              <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
              ონლაინ გადახდა დროებით მიუწვდომელია — ანგარიშსწორება ხდება მიღებისას.
            </p>
          </fieldset>
        </div>

        <div>
          <div className="lg:sticky lg:top-[8.5rem]">
            <div className="mb-4 rounded-card border border-ink-200 bg-surface p-4">
              <h2 className="text-sm font-bold text-ink-900">შეკვეთა ({itemsCount} ცალი)</h2>
              <ul className="mt-3 space-y-3">
                {items.map((item) => (
                  <li key={item.productId} className="flex items-center gap-3">
                    <ProductImage
                      src={item.snapshot.image}
                      alt=""
                      className="h-12 w-12 shrink-0 rounded-control border border-ink-200"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-medium text-ink-800">
                        {item.snapshot.name}
                      </span>
                      <span className="block text-xs text-ink-500">
                        {item.qty} × {formatPrice(item.snapshot.price)}
                      </span>
                    </span>
                    <span className="shrink-0 text-sm font-semibold text-ink-900">
                      {formatPrice(item.snapshot.price * item.qty)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <CartSummary
              subtotal={subtotal}
              shipping={shipping}
              total={totalWithDelivery(subtotal, shipping)}
              cities={rules?.cities}
              remaining={amountToFreeDelivery(subtotal, rules)}
              freeFrom={rules?.freeFrom}
              itemsCount={itemsCount}
              savings={savings}
              actionLabel="შეკვეთის დადასტურება"
              onAction={handleSubmit}
              loading={submitting}
            />
          </div>
        </div>
      </form>
    </div>
  );
}
