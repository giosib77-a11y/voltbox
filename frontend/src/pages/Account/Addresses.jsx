import { useState } from 'react';
import { MapPin, Plus, Star, Trash2 } from 'lucide-react';
import Button from '../../components/common/Button.jsx';
import Input from '../../components/common/Input.jsx';
import Select from '../../components/common/Select.jsx';
import Modal from '../../components/common/Modal.jsx';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import { Skeleton } from '../../components/common/Skeleton.jsx';
import Badge from '../../components/common/Badge.jsx';
import { useAsync } from '../../hooks/useProducts.js';
import { useToast } from '../../hooks/useToast.js';
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js';
import * as api from '../../services/api.js';
import { ADDRESS_FIELDS, validateField, validateForm } from '../../utils/validate.js';
import { CITIES } from '../../constants/index.js';

const EMPTY = { label: '', city: '', address: '', isDefault: false };

export default function Addresses() {
  useDocumentTitle('მისამართები');

  const toast = useToast();
  const { data: addresses, loading, error, reload, setData } = useAsync(() => api.getAddresses(), [], {
    initialData: [],
  });

  const [open, setOpen] = useState(false);
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  function openNew() {
    setValues(EMPTY);
    setErrors({});
    setOpen(true);
  }

  async function handleSave(event) {
    event.preventDefault();
    const nextErrors = validateForm(values, ADDRESS_FIELDS);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    try {
      const next = await api.saveAddress(values);
      setData(next);
      setOpen(false);
      toast.success('მისამართი შენახულია');
    } catch (err) {
      toast.error(err?.message || 'შენახვა ვერ მოხერხდა');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    try {
      const next = await api.deleteAddress(id);
      setData(next);
      toast.info('მისამართი წაიშალა');
    } catch (err) {
      toast.error(err?.message || 'წაშლა ვერ მოხერხდა');
    }
  }

  if (loading) return <Skeleton className="h-48 w-full" rounded="rounded-card" />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-bold text-ink-900">შენახული მისამართები</h2>
        <Button size="sm" onClick={openNew}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          დამატება
        </Button>
      </div>

      {addresses.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title="მისამართები ჯერ არ დაგიმატებიათ"
          description="შეინახეთ მისამართი, რომ შეკვეთის გაფორმებისას ხელახლა არ შეავსოთ."
          actionLabel="მისამართის დამატება"
          onAction={openNew}
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {addresses.map((address) => (
            <li key={address.id} className="rounded-card border border-ink-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-sm font-semibold text-ink-900">
                    {address.label || 'მისამართი'}
                    {address.isDefault && (
                      <Badge tone="success" size="sm">
                        <Star className="h-3 w-3" aria-hidden="true" />
                        ძირითადი
                      </Badge>
                    )}
                  </p>
                  <p className="mt-1.5 text-sm text-ink-600">
                    {address.city}, {address.address}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(address.id)}
                  aria-label="მისამართის წაშლა"
                  className="-mr-1.5 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-danger-50 hover:text-danger-600"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="ახალი მისამართი">
        <form id="address-form" onSubmit={handleSave} noValidate className="space-y-4 p-5">
          <Input
            label="დასახელება"
            placeholder="მაგ. სახლი ან ოფისი"
            value={values.label}
            onChange={(e) => setValues((c) => ({ ...c, label: e.target.value }))}
          />
          <Select
            label="ქალაქი"
            required
            placeholder="აირჩიეთ ქალაქი"
            options={CITIES.map((city) => ({ value: city, label: city }))}
            value={values.city}
            error={errors.city}
            onChange={(e) => setValues((c) => ({ ...c, city: e.target.value }))}
            onBlur={(e) => setErrors((c) => ({ ...c, city: validateField('city', e.target.value) }))}
          />
          <Input
            label="მისამართი"
            required
            placeholder="ქუჩა, ნომერი, ბინა"
            value={values.address}
            error={errors.address}
            onChange={(e) => setValues((c) => ({ ...c, address: e.target.value }))}
            onBlur={(e) => setErrors((c) => ({ ...c, address: validateField('address', e.target.value) }))}
          />
          <label className="flex cursor-pointer items-center gap-2.5 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={values.isDefault}
              onChange={(e) => setValues((c) => ({ ...c, isDefault: e.target.checked }))}
              className="h-4 w-4 accent-primary-600"
            />
            ძირითად მისამართად დაყენება
          </label>

          <div className="flex gap-3 pt-1">
            <Button type="button" variant="outline" fullWidth onClick={() => setOpen(false)}>
              გაუქმება
            </Button>
            <Button type="submit" fullWidth loading={saving}>
              შენახვა
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
