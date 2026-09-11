/**
 * CategoryDialog: create or edit a category, including its filter config.
 *
 * What it does: the category's own fields plus a filters editor that produces
 * exactly the structure the storefront reads.
 * Where it fits: opened from CategoryList.
 * Notes: the filter shape is not a free-form JSON box on purpose. FilterSidebar
 * resolves `specs.<key>` against a product's specs, and `match` only means
 * something for a toggle - a hand-written JSON blob gets those wrong silently.
 */

import { useState } from 'react';
import { Plus, X } from 'lucide-react';

import Modal from '../../components/common/Modal.jsx';
import Button from '../../components/common/Button.jsx';
import Input from '../../components/common/Input.jsx';
import Select from '../../components/common/Select.jsx';
import Textarea from '../../components/common/Textarea.jsx';
import * as adminApi from '../adminApi.js';

const FILTER_TYPES = [
  { value: 'checkbox', label: 'მრავლობითი არჩევანი' },
  { value: 'toggle', label: 'ჩართვა/გამორთვა' },
  { value: 'swatch', label: 'ფერები' },
];

const BLANK_FILTER = { key: 'specs.', label: '', type: 'checkbox', match: '' };

/**
 * ფილტრის მწკრივის სვეტები.
 *
 * `minmax(0,1fr)` და არა `auto`: `auto` სვეტი შიგთავსით იზომება, ამიტომ ტიპის
 * გრძელი ტექსტი სიგანეს ართმევდა „გასაღებსა“ და „ლეიბლს“ — სწორედ იმ ორ ველს,
 * რომელსაც ავსებ.
 */
const GRID = 'sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_14rem_2.5rem]';

export default function CategoryDialog({ category, categories, onClose, onSaved }) {
  const isEdit = Boolean(category);
  const [values, setValues] = useState({
    name: category?.name || '',
    slug: category?.slug || '',
    shortName: category?.shortName || '',
    description: category?.description || '',
    icon: category?.icon || 'Package',
    parentId: category?.parentId || '',
    position: String(category?.position ?? 0),
    filters: (category?.filters || []).map((filter) => ({ match: '', ...filter })),
  });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);

  function set(field, value) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: '' }));
  }

  function setFilter(index, patch) {
    setValues((current) => ({
      ...current,
      filters: current.filters.map((filter, i) => (i === index ? { ...filter, ...patch } : filter)),
    }));
  }

  /** Strips `match` from anything that is not a toggle - the API rejects it. */
  function filtersPayload() {
    return values.filters
      .filter((filter) => filter.key.trim() && filter.label.trim())
      .map((filter) => {
        const base = { key: filter.key.trim(), label: filter.label.trim(), type: filter.type };
        if (filter.type !== 'toggle') return base;
        const raw = String(filter.match).trim();
        // `true` is a real value in live data (specs.fastCharge), so the literal
        // string has to become a boolean rather than staying "true".
        const match = raw === 'true' ? true : raw === 'false' ? false : raw;
        return { ...base, match };
      });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (saving) return;
    if (!values.name.trim()) {
      setErrors({ name: 'სახელი სავალდებულოა' });
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        name: values.name.trim(),
        shortName: values.shortName.trim() || values.name.trim(),
        description: values.description,
        icon: values.icon.trim() || 'Package',
        parentId: values.parentId || null,
        position: Number(values.position) || 0,
        filters: filtersPayload(),
      };
      if (values.slug.trim()) payload.slug = values.slug.trim();

      if (isEdit) await adminApi.updateCategory(category.id, payload);
      else await adminApi.createCategory(payload);
      onSaved();
    } catch (caught) {
      if (caught?.details?.code === 'SLUG_TAKEN') setErrors({ slug: 'ეს slug უკვე დაკავებულია' });
      else setFormError(caught);
    } finally {
      setSaving(false);
    }
  }

  const parentOptions = categories
    .filter((item) => item.id !== category?.id && !item.parentId)
    .map((item) => ({ value: item.id, label: item.name }));

  return (
    <Modal
      open
      onClose={onClose}
      size="2xl"
      title={isEdit ? 'კატეგორიის რედაქტირება' : 'ახალი კატეგორია'}
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-5 p-5">
        {formError ? (
          <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
            {formError.message}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="სახელი"
            required
            value={values.name}
            error={errors.name}
            onChange={(event) => set('name', event.target.value)}
          />
          <Input
            label="Slug"
            hint="ცარიელი — სახელიდან შეიქმნება"
            value={values.slug}
            error={errors.slug}
            onChange={(event) => set('slug', event.target.value)}
          />
          <Input
            label="მოკლე სახელი"
            value={values.shortName}
            onChange={(event) => set('shortName', event.target.value)}
          />
          <Input
            label="აიქონი"
            hint="lucide-react-ის სახელი"
            value={values.icon}
            onChange={(event) => set('icon', event.target.value)}
          />
          <Select
            label="მშობელი კატეგორია"
            value={values.parentId}
            placeholder="არცერთი"
            options={parentOptions}
            onChange={(event) => set('parentId', event.target.value)}
          />
          <Input
            label="რიგი"
            inputMode="numeric"
            value={values.position}
            onChange={(event) => set('position', event.target.value)}
          />
        </div>

        <Textarea
          label="აღწერა"
          rows={2}
          value={values.description}
          onChange={(event) => set('description', event.target.value)}
        />

        <div>
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <h3 className="text-sm font-semibold text-ink-900">ფილტრები</h3>
            <span className="text-xs text-ink-500">
              {values.filters.length ? `${values.filters.length} ფილტრი` : null}
            </span>
          </div>
          <p className="mb-3 text-xs leading-relaxed text-ink-600">
            გასაღები არის <code className="rounded bg-ink-100 px-1 py-0.5">brand</code> ან{' '}
            <code className="rounded bg-ink-100 px-1 py-0.5">specs.რაღაც</code> — ზუსტად ისე,
            როგორც პროდუქტის მახასიათებელს ჰქვია. ლეიბლს მყიდველი დაინახავს.
          </p>

          {values.filters.length === 0 ? (
            <p className="rounded-xl border border-dashed border-ink-300 px-3 py-5 text-center text-sm text-ink-500">
              ფილტრი არ არის. კატეგორიის გვერდზე გვერდითა პანელი ცარიელი დარჩება.
            </p>
          ) : (
            <>
              {/* Column headings once, above the list - not repeated on every
                  row. A filter is three short values; per-filter cards with
                  their own titles and hints turned eight of them into a page of
                  scrolling. */}
              <div className={`mb-1.5 hidden px-1 text-xs font-medium text-ink-600 sm:grid ${GRID}`}>
                <span>გასაღები</span>
                <span>ლეიბლი</span>
                <span>ტიპი</span>
                <span className="sr-only">მოქმედება</span>
              </div>

              <div className="space-y-2">
                {values.filters.map((filter, index) => (
                  <div key={index} className={`grid grid-cols-2 items-center gap-2 ${GRID}`}>
                    <Input
                      aria-label="გასაღები"
                      placeholder="specs.ram"
                      value={filter.key}
                      onChange={(event) => setFilter(index, { key: event.target.value })}
                    />
                    <Input
                      aria-label="ლეიბლი"
                      placeholder="ოპერატიული მეხსიერება"
                      value={filter.label}
                      onChange={(event) => setFilter(index, { label: event.target.value })}
                    />
                    <Select
                      aria-label="ტიპი"
                      value={filter.type}
                      options={FILTER_TYPES}
                      onChange={(event) => setFilter(index, { type: event.target.value })}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="justify-self-end"
                      aria-label={`ფილტრის წაშლა — ${(filter.label || '').trim() || index + 1}`}
                      onClick={() =>
                        setValues((current) => ({
                          ...current,
                          filters: current.filters.filter((_, i) => i !== index),
                        }))
                      }
                    >
                      <X className="h-4 w-4 text-ink-500" aria-hidden="true" />
                    </Button>

                    {/* `match` means something only for a toggle. It sits under
                        the type it belongs to, and is absent everywhere else
                        rather than disabled and taking up a column. */}
                    {filter.type === 'toggle' ? (
                      <Input
                        aria-label="ჩართვის მნიშვნელობა"
                        placeholder="მაგ. true"
                        hint="ჩაირთოს, როცა უდრის"
                        containerClassName="sm:col-start-3"
                        value={String(filter.match ?? '')}
                        onChange={(event) => setFilter(index, { match: event.target.value })}
                      />
                    ) : null}
                  </div>
                ))}
              </div>
            </>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() =>
              setValues((current) => ({
                ...current,
                filters: [...current.filters, { ...BLANK_FILTER }],
              }))
            }
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            ფილტრის დამატება
          </Button>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={saving}>
            გაუქმება
          </Button>
          <Button type="submit" variant="accent" size="sm" loading={saving}>
            შენახვა
          </Button>
        </div>
      </form>
    </Modal>
  );
}
