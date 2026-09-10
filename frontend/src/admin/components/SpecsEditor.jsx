/**
 * SpecsEditor: product specifications, guided by the category's filters.
 *
 * What it does: when a category is chosen, the spec keys its filters rely on
 * appear as named fields; anything else is added as a free-form row.
 * Where it fits: the Specifications section of ProductForm.
 * Notes: this is the whole point of the component. `categories.filters`
 * addresses specs by exact key, so an admin typing "RAM" where the filter says
 * "ram" produces a product that silently disappears from that filter. Showing
 * the expected keys makes the mismatch impossible rather than merely unlikely.
 */

import { useMemo, useState } from 'react';
import { Plus, X } from 'lucide-react';

import Input from '../../components/common/Input.jsx';
import Button from '../../components/common/Button.jsx';

/** `specs.ram` → `ram`; `brand` is not a spec and is skipped by the caller. */
function specKey(filterKey) {
  return filterKey.startsWith('specs.') ? filterKey.slice('specs.'.length) : null;
}

export default function SpecsEditor({ value, onChange, categoryFilters = [] }) {
  const [newKey, setNewKey] = useState('');

  const expected = useMemo(
    () =>
      categoryFilters
        .map((filter) => ({ ...filter, key: specKey(filter.key) }))
        .filter((filter) => filter.key),
    [categoryFilters],
  );

  const expectedKeys = new Set(expected.map((filter) => filter.key));
  const extraKeys = Object.keys(value || {}).filter((key) => !expectedKeys.has(key));

  function setSpec(key, raw) {
    const next = { ...value };
    if (raw === '') delete next[key];
    else next[key] = raw;
    onChange(next);
  }

  function addExtra() {
    const key = newKey.trim();
    if (!key || key in (value || {})) return;
    onChange({ ...value, [key]: '' });
    setNewKey('');
  }

  return (
    <div className="space-y-4">
      {expected.length ? (
        <div>
          <p className="mb-2 text-xs text-ink-600">
            ამ კატეგორიის ფილტრები ამ მახასიათებლებზეა აგებული. ცარიელი ველი ნიშნავს, რომ
            პროდუქტი შესაბამის ფილტრში არ გამოჩნდება.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {expected.map((filter) => (
              <Input
                key={filter.key}
                label={filter.label}
                hint={filter.key}
                value={value?.[filter.key] ?? ''}
                onChange={(event) => setSpec(filter.key, event.target.value)}
              />
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-ink-600">
          აირჩიეთ კატეგორია — მისი ფილტრების მახასიათებლები აქ გამოჩნდება.
        </p>
      )}

      {extraKeys.length ? (
        <div>
          <p className="mb-2 text-xs text-ink-600">დამატებითი მახასიათებლები</p>
          <div className="space-y-2">
            {extraKeys.map((key) => (
              <div key={key} className="flex items-end gap-2">
                <Input
                  label={key}
                  containerClassName="flex-1"
                  value={String(value[key] ?? '')}
                  onChange={(event) => setSpec(key, event.target.value)}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSpec(key, '')}
                  aria-label={`${key} — წაშლა`}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex items-end gap-2">
        <Input
          label="ახალი მახასიათებელი"
          placeholder="მაგ. weight"
          containerClassName="flex-1"
          value={newKey}
          onChange={(event) => setNewKey(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              addExtra();
            }
          }}
        />
        <Button variant="outline" size="sm" onClick={addExtra} disabled={!newKey.trim()}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          დამატება
        </Button>
      </div>
    </div>
  );
}
