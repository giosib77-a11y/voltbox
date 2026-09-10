/**
 * ProductForm: the shared create/edit form for admin products.
 *
 * What it does: renders the product's sections, validates locally and maps the
 * API's 400 and 409 answers onto the fields that caused them.
 * Where it fits: /admin/products/new and /admin/products/:id.
 * Notes: stock is editable only on create. On edit it is shown read-only with a
 * link to the inventory adjustment, because every later change has to go
 * through the ledger. Images unlock only after the product exists.
 *
 * Uses the storefront's form pattern (useState plus explicit validation) rather
 * than a form library: one paradigm in the codebase is worth more than the
 * convenience of a second.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useBlocker, useNavigate, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, Archive, ArchiveRestore } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import Input from '../../components/common/Input.jsx';
import Select from '../../components/common/Select.jsx';
import Textarea from '../../components/common/Textarea.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import Skeleton from '../../components/common/Skeleton.jsx';
import SpecsEditor from '../components/SpecsEditor.jsx';
import ImageManager from '../components/ImageManager.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import { money } from '../format.js';
import * as adminApi from '../adminApi.js';

const EMPTY = {
  name: '',
  slug: '',
  sku: '',
  categoryId: '',
  brandId: '',
  price: '',
  oldPrice: '',
  shortDescription: '',
  description: '',
  specs: {},
  tags: '',
  lowStockThreshold: '3',
  stock: '0',
  isActive: false,
  isFeatured: false,
  isNew: false,
};

/** Maps the API's error details onto field names the form knows. */
function fieldErrorsFrom(error) {
  const details = error?.details?.details;
  const code = error?.details?.code;

  if (code === 'SKU_TAKEN') return { sku: 'ეს SKU სხვა პროდუქტს უკვე უკავია' };
  if (code === 'SLUG_TAKEN') return { slug: 'ეს slug უკვე დაკავებულია' };
  if (code === 'INVALID_OLD_PRICE') {
    return { oldPrice: 'ძველი ფასი მიმდინარეზე მაღალი უნდა იყოს' };
  }
  if (code === 'CATEGORY_NOT_FOUND') return { categoryId: 'კატეგორია ვერ მოიძებნა' };
  if (code === 'BRAND_NOT_FOUND') return { brandId: 'ბრენდი ვერ მოიძებნა' };

  if (Array.isArray(details)) {
    return Object.fromEntries(
      details.filter((item) => item.field).map((item) => [item.field, item.message || 'არასწორია']),
    );
  }
  return {};
}

export default function ProductForm() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();

  const [values, setValues] = useState(EMPTY);
  const [product, setProduct] = useState(null);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);

  useEffect(() => {
    Promise.all([adminApi.listCategories(), adminApi.listBrands()])
      .then(([nextCategories, nextBrands]) => {
        setCategories(nextCategories);
        setBrands(nextBrands);
      })
      .catch(setLoadError);
  }, []);

  const hydrate = useCallback((fetched) => {
    setProduct(fetched);
    setValues({
      name: fetched.name,
      slug: fetched.slug,
      sku: fetched.sku || '',
      categoryId: fetched.categoryId,
      brandId: fetched.brandId,
      price: String(fetched.price),
      oldPrice: fetched.oldPrice === null ? '' : String(fetched.oldPrice),
      shortDescription: fetched.shortDescription,
      description: fetched.description,
      specs: fetched.specs || {},
      tags: (fetched.tags || []).join(', '),
      lowStockThreshold: String(fetched.lowStockThreshold),
      stock: String(fetched.stock),
      isActive: fetched.isActive,
      isFeatured: fetched.isFeatured,
      isNew: fetched.isNew,
    });
    setDirty(false);
  }, []);

  useEffect(() => {
    if (!isEdit) return undefined;
    let cancelled = false;
    setLoading(true);
    adminApi
      .getProduct(id)
      .then((fetched) => !cancelled && hydrate(fetched))
      .catch((caught) => !cancelled && setLoadError(caught))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id, isEdit, hydrate]);

  // Leaving with unsaved edits loses them silently otherwise. useBlocker covers
  // in-app navigation; beforeunload covers closing the tab.
  const blocker = useBlocker(dirty && !saving);
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  function set(field, value) {
    setValues((current) => ({ ...current, [field]: value }));
    setDirty(true);
    setErrors((current) => ({ ...current, [field]: '' }));
  }

  const selectedCategory = useMemo(
    () => categories.find((item) => item.id === values.categoryId),
    [categories, values.categoryId],
  );

  function validate() {
    const next = {};
    if (!values.name.trim()) next.name = 'სახელი სავალდებულოა';
    if (!values.categoryId) next.categoryId = 'აირჩიეთ კატეგორია';
    if (!values.brandId) next.brandId = 'აირჩიეთ ბრენდი';
    if (values.price === '' || Number(values.price) < 0) next.price = 'მიუთითეთ ფასი';
    if (values.oldPrice !== '' && Number(values.oldPrice) <= Number(values.price)) {
      next.oldPrice = 'ძველი ფასი მიმდინარეზე მაღალი უნდა იყოს';
    }
    return next;
  }

  /** The payload the API accepts — money as strings, never parsed here. */
  function payload() {
    const base = {
      name: values.name.trim(),
      categoryId: values.categoryId,
      brandId: values.brandId,
      // Money goes out exactly as typed. Parsing it into a float here is how
      // 10.10 becomes 10.099999999999999.
      price: values.price,
      oldPrice: values.oldPrice === '' ? null : values.oldPrice,
      shortDescription: values.shortDescription,
      description: values.description,
      specs: values.specs,
      tags: values.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
      lowStockThreshold: Number(values.lowStockThreshold) || 0,
      isActive: values.isActive,
      isFeatured: values.isFeatured,
      isNew: values.isNew,
    };
    if (values.slug.trim()) base.slug = values.slug.trim();
    if (values.sku.trim()) base.sku = values.sku.trim();
    return base;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (saving) return;

    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    setSaving(true);
    setFormError(null);
    try {
      if (isEdit) {
        const updated = await adminApi.updateProduct(id, payload());
        hydrate(updated);
      } else {
        // stock is create-only; afterwards it moves through the ledger.
        const created = await adminApi.createProduct({
          ...payload(),
          stock: Number(values.stock) || 0,
        });
        setDirty(false);
        navigate(`/admin/products/${created.id}`, { replace: true });
      }
    } catch (caught) {
      const mapped = fieldErrorsFrom(caught);
      setErrors(mapped);
      if (!Object.keys(mapped).length) setFormError(caught);
    } finally {
      setSaving(false);
    }
  }

  async function handleArchiveToggle() {
    setSaving(true);
    try {
      const next = product.archivedAt
        ? await adminApi.unarchiveProduct(id)
        : await adminApi.archiveProduct(id);
      hydrate(next);
      setConfirmArchive(false);
    } catch (caught) {
      setFormError(caught);
    } finally {
      setSaving(false);
    }
  }

  if (loadError) return <ErrorState title="ჩატვირთვა ვერ მოხერხდა" error={loadError} />;
  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const archived = Boolean(product?.archivedAt);

  return (
    <form onSubmit={handleSubmit} noValidate>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/admin/products"
            className="mb-1 inline-flex items-center gap-1 text-sm text-ink-600 hover:text-ink-900"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            პროდუქტები
          </Link>
          <h1 className="text-lg font-semibold text-ink-900">
            {isEdit ? values.name || 'პროდუქტი' : 'ახალი პროდუქტი'}
          </h1>
        </div>
        <div className="flex gap-2">
          {isEdit ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => (archived ? handleArchiveToggle() : setConfirmArchive(true))}
              disabled={saving}
            >
              {archived ? (
                <ArchiveRestore className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Archive className="h-4 w-4" aria-hidden="true" />
              )}
              {archived ? 'არქივიდან დაბრუნება' : 'არქივში გადატანა'}
            </Button>
          ) : null}
          <Button type="submit" variant="accent" size="sm" loading={saving}>
            შენახვა
          </Button>
        </div>
      </header>

      {archived ? (
        <p className="mb-4 flex items-start gap-2 rounded-lg bg-ink-100 px-3 py-2 text-sm text-ink-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          პროდუქტი არქივშია. გასააქტიურებლად ჯერ არქივიდან დააბრუნეთ.
        </p>
      ) : null}

      {formError ? (
        <p role="alert" className="mb-4 rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
          {formError.message}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-4">
          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">ძირითადი</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="სახელი"
                required
                containerClassName="sm:col-span-2"
                value={values.name}
                error={errors.name}
                onChange={(event) => set('name', event.target.value)}
              />
              <Input
                label="Slug"
                hint={isEdit ? 'შეცვლა ძველ ბმულებს გატეხავს' : 'ცარიელი — სახელიდან შეიქმნება'}
                value={values.slug}
                error={errors.slug}
                onChange={(event) => set('slug', event.target.value)}
              />
              <Input
                label="SKU"
                value={values.sku}
                error={errors.sku}
                onChange={(event) => set('sku', event.target.value)}
              />
              <Select
                label="კატეგორია"
                required
                value={values.categoryId}
                error={errors.categoryId}
                placeholder="აირჩიეთ"
                options={categories.map((item) => ({ value: item.id, label: item.name }))}
                onChange={(event) => set('categoryId', event.target.value)}
              />
              <Select
                label="ბრენდი"
                required
                value={values.brandId}
                error={errors.brandId}
                placeholder="აირჩიეთ"
                options={brands.map((item) => ({ value: item.id, label: item.name }))}
                onChange={(event) => set('brandId', event.target.value)}
              />
            </div>
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">ფასი</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="ფასი"
                required
                inputMode="decimal"
                value={values.price}
                error={errors.price}
                onChange={(event) => set('price', event.target.value)}
              />
              <Input
                label="ძველი ფასი"
                hint="ფასდაკლების საჩვენებლად"
                inputMode="decimal"
                value={values.oldPrice}
                error={errors.oldPrice}
                onChange={(event) => set('oldPrice', event.target.value)}
              />
            </div>
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">აღწერა</h2>
            <div className="space-y-3">
              <Input
                label="მოკლე აღწერა"
                value={values.shortDescription}
                onChange={(event) => set('shortDescription', event.target.value)}
              />
              <Textarea
                label="სრული აღწერა"
                rows={5}
                value={values.description}
                onChange={(event) => set('description', event.target.value)}
              />
              <Input
                label="ტეგები"
                hint="მძიმით გამოყოფილი"
                value={values.tags}
                onChange={(event) => set('tags', event.target.value)}
              />
            </div>
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">მახასიათებლები</h2>
            <SpecsEditor
              value={values.specs}
              onChange={(specs) => set('specs', specs)}
              categoryFilters={selectedCategory?.filters || []}
            />
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">სურათები</h2>
            {isEdit ? (
              <ImageManager
                productId={id}
                images={product?.images || []}
                onChange={hydrate}
                onError={setFormError}
              />
            ) : (
              <p className="text-sm text-ink-600">
                სურათების ატვირთვა პროდუქტის შენახვის შემდეგ გახდება შესაძლებელი.
              </p>
            )}
          </section>
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">მარაგი</h2>
            {isEdit ? (
              <div className="space-y-2 text-sm">
                <p className="text-ink-700">
                  მიმდინარე მარაგი:{' '}
                  <strong className="tabular-nums text-ink-900">{product?.stock}</strong>
                </p>
                <p className="text-xs text-ink-500">
                  მარაგი მხოლოდ კორექტირებით იცვლება — ყოველი ცვლილება ისტორიაში ინახება.
                </p>
                <Link
                  to={`/admin/inventory?productId=${id}`}
                  className="inline-block text-sm text-accent-700 underline-offset-4 hover:underline"
                >
                  მარაგის კორექტირება
                </Link>
              </div>
            ) : (
              <Input
                label="საწყისი მარაგი"
                inputMode="numeric"
                value={values.stock}
                onChange={(event) => set('stock', event.target.value)}
              />
            )}
            <Input
              label="ამოწურვის ზღვარი"
              containerClassName="mt-3"
              inputMode="numeric"
              value={values.lowStockThreshold}
              onChange={(event) => set('lowStockThreshold', event.target.value)}
            />
          </section>

          <section className="rounded-xl border border-ink-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">სტატუსი</h2>
            <div className="space-y-2 text-sm">
              {[
                ['isActive', 'აქტიური (ჩანს მაღაზიაში)'],
                ['isFeatured', 'რჩეული'],
                ['isNew', 'ახალი'],
              ].map(([field, label]) => (
                <label key={field} className="flex items-center gap-2 text-ink-700">
                  <input
                    type="checkbox"
                    checked={values[field]}
                    disabled={field === 'isActive' && archived}
                    onChange={(event) => set(field, event.target.checked)}
                    className="h-4 w-4 rounded border-ink-300 text-accent-600 focus:ring-accent-600/30 disabled:opacity-40"
                  />
                  {label}
                </label>
              ))}
            </div>
            {values.isActive && isEdit && !product?.images?.length ? (
              <p className="mt-3 flex items-start gap-1.5 text-xs text-warning-600">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                სურათის გარეშე პროდუქტი მაღაზიაში ცარიელი ბარათით გამოჩნდება.
              </p>
            ) : null}
          </section>

          {isEdit && product ? (
            <section className="rounded-xl border border-ink-200 bg-white p-4 text-sm text-ink-600">
              <h2 className="mb-2 text-sm font-semibold text-ink-900">ინფორმაცია</h2>
              <p>
                რეიტინგი: {product.rating} ({product.reviewsCount})
              </p>
              <p className="mt-1">მიმდინარე ფასი: {money(product.price)}</p>
            </section>
          ) : null}
        </aside>
      </div>

      <ConfirmDialog
        open={confirmArchive}
        title="არქივში გადატანა"
        description="პროდუქტი მაღაზიიდან გაქრება და გამორთული გახდება. შეკვეთების ისტორია ხელუხლებელი რჩება. დაბრუნება ნებისმიერ დროს შეიძლება."
        confirmLabel="არქივში გადატანა"
        onConfirm={handleArchiveToggle}
        onClose={() => setConfirmArchive(false)}
      />

      <ConfirmDialog
        open={blocker.state === 'blocked'}
        title="შენახვის გარეშე გასვლა"
        description="ფორმაში შენახული არ არის ცვლილებები. გვერდის დატოვებისას ისინი დაიკარგება."
        confirmLabel="დატოვება"
        cancelLabel="დარჩენა"
        onConfirm={() => blocker.proceed?.()}
        onClose={() => blocker.reset?.()}
      />
    </form>
  );
}
