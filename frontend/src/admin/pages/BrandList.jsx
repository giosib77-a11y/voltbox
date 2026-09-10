/**
 * BrandList: brands with their product counts.
 *
 * What it does: lists brands and edits one inline in a dialog.
 * Where it fits: /admin/brands.
 * Notes: counts come from a single aggregate on the server, so this page stays
 * one request regardless of how many brands there are.
 */

import { useCallback, useEffect, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';

import Modal from '../../components/common/Modal.jsx';
import Button from '../../components/common/Button.jsx';
import Input from '../../components/common/Input.jsx';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import DataTable from '../components/DataTable.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import * as adminApi from '../adminApi.js';

function BrandDialog({ brand, onClose, onSaved }) {
  const isEdit = Boolean(brand?.id);
  const [values, setValues] = useState({
    name: brand?.name || '',
    slug: brand?.slug || '',
    country: brand?.country || '',
  });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);

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
        country: values.country.trim() || null,
      };
      if (values.slug.trim()) payload.slug = values.slug.trim();

      if (isEdit) await adminApi.updateBrand(brand.id, payload);
      else await adminApi.createBrand(payload);
      onSaved();
    } catch (caught) {
      const code = caught?.details?.code;
      if (code === 'BRAND_NAME_TAKEN') setErrors({ name: 'ასეთი ბრენდი უკვე არსებობს' });
      else if (code === 'SLUG_TAKEN') setErrors({ slug: 'ეს slug უკვე დაკავებულია' });
      else setFormError(caught);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={isEdit ? 'ბრენდის რედაქტირება' : 'ახალი ბრენდი'}>
      <form onSubmit={handleSubmit} noValidate className="space-y-3">
        {formError ? (
          <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
            {formError.message}
          </p>
        ) : null}
        <Input
          label="სახელი"
          required
          value={values.name}
          error={errors.name}
          onChange={(event) => setValues((c) => ({ ...c, name: event.target.value }))}
        />
        <Input
          label="Slug"
          hint="ცარიელი — სახელიდან შეიქმნება"
          value={values.slug}
          error={errors.slug}
          onChange={(event) => setValues((c) => ({ ...c, slug: event.target.value }))}
        />
        <Input
          label="ქვეყანა"
          value={values.country}
          onChange={(event) => setValues((c) => ({ ...c, country: event.target.value }))}
        />
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

export default function BrandList() {
  const [brands, setBrands] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteError, setDeleteError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    adminApi.listBrands().then(setBrands).catch(setError);
  }, []);

  useEffect(load, [load]);

  async function handleDelete() {
    setDeleteError(null);
    try {
      await adminApi.deleteBrand(deleting.id);
      setDeleting(null);
      load();
    } catch (caught) {
      setDeleteError(caught);
    }
  }

  const columns = [
    {
      key: 'name',
      header: 'ბრენდი',
      render: (brand) => (
        <span>
          <span className="font-medium text-ink-900">{brand.name}</span>
          <span className="block text-xs text-ink-500">{brand.slug}</span>
        </span>
      ),
    },
    {
      key: 'country',
      header: 'ქვეყანა',
      render: (brand) => <span className="text-ink-700">{brand.country || '—'}</span>,
    },
    {
      key: 'products',
      header: 'პროდუქტები',
      align: 'right',
      render: (brand) => <span className="tabular-nums">{brand.productsCount}</span>,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (brand) => (
        <span className="flex justify-end gap-1">
          <Button variant="ghost" size="xs" onClick={() => setEditing(brand)} aria-label="რედაქტირება">
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              setDeleteError(null);
              setDeleting(brand);
            }}
            aria-label="წაშლა"
          >
            <Trash2 className="h-4 w-4 text-danger-600" aria-hidden="true" />
          </Button>
        </span>
      ),
    },
  ];

  if (error) return <ErrorState title="ბრენდები ვერ ჩაიტვირთა" error={error} onRetry={load} />;

  return (
    <div>
      <header className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-ink-900">ბრენდები</h1>
        <Button variant="accent" size="sm" onClick={() => setEditing({})}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          ახალი ბრენდი
        </Button>
      </header>

      <DataTable
        caption="ბრენდების სია"
        columns={columns}
        rows={brands || []}
        loading={brands === null}
        empty={<EmptyState title="ბრენდი არ არის" description="დაამატეთ პირველი ბრენდი." />}
      />

      {editing ? (
        <BrandDialog
          brand={editing.id ? editing : null}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(deleting)}
        title="ბრენდის წაშლა"
        description={
          deleteError
            ? deleteError.message
            : `„${deleting?.name}“ სამუდამოდ წაიშლება. თუ მას პროდუქტები აქვს, წაშლა უარყოფილი იქნება.`
        }
        confirmLabel="წაშლა"
        onConfirm={handleDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
