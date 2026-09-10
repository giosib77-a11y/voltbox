/**
 * CategoryList: the category tree with its filter configuration.
 *
 * What it does: lists categories as an indented tree, and edits one in a dialog
 * that includes the filters editor.
 * Where it fits: /admin/categories.
 * Notes: deleting is offered but the API refuses while products or children
 * point at the category, and says how many - so the admin learns what to fix
 * instead of seeing a foreign-key error.
 */

import { useCallback, useEffect, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';

import Button from '../../components/common/Button.jsx';
import EmptyState from '../../components/common/EmptyState.jsx';
import ErrorState from '../../components/common/ErrorState.jsx';
import DataTable from '../components/DataTable.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import CategoryDialog from '../components/CategoryDialog.jsx';
import * as adminApi from '../adminApi.js';

/** Roots first, each followed by its children — a flat list that reads as a tree. */
function asTree(categories) {
  const roots = categories.filter((item) => !item.parentId);
  const childrenOf = (id) => categories.filter((item) => item.parentId === id);
  return roots.flatMap((root) => [
    { ...root, depth: 0 },
    ...childrenOf(root.id).map((child) => ({ ...child, depth: 1 })),
  ]);
}

export default function CategoryList() {
  const [categories, setCategories] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteError, setDeleteError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    adminApi.listCategories().then(setCategories).catch(setError);
  }, []);

  useEffect(load, [load]);

  async function handleDelete() {
    setDeleteError(null);
    try {
      await adminApi.deleteCategory(deleting.id);
      setDeleting(null);
      load();
    } catch (caught) {
      setDeleteError(caught);
    }
  }

  const columns = [
    {
      key: 'name',
      header: 'კატეგორია',
      render: (category) => (
        <span style={{ paddingLeft: `${category.depth * 1.25}rem` }}>
          <span className="font-medium text-ink-900">{category.name}</span>
          <span className="block text-xs text-ink-500">{category.slug}</span>
        </span>
      ),
    },
    {
      key: 'filters',
      header: 'ფილტრები',
      render: (category) => (
        <span className="text-ink-700">
          {category.filters?.length ? `${category.filters.length} ფილტრი` : '—'}
        </span>
      ),
    },
    {
      key: 'products',
      header: 'პროდუქტები',
      align: 'right',
      render: (category) => <span className="tabular-nums">{category.productsCount}</span>,
    },
    {
      key: 'position',
      header: 'რიგი',
      align: 'right',
      render: (category) => <span className="tabular-nums text-ink-600">{category.position}</span>,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (category) => (
        <span className="flex justify-end gap-1">
          <Button variant="ghost" size="xs" onClick={() => setEditing(category)} aria-label="რედაქტირება">
            <Pencil className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              setDeleteError(null);
              setDeleting(category);
            }}
            aria-label="წაშლა"
          >
            <Trash2 className="h-4 w-4 text-danger-600" aria-hidden="true" />
          </Button>
        </span>
      ),
    },
  ];

  if (error) return <ErrorState title="კატეგორიები ვერ ჩაიტვირთა" error={error} onRetry={load} />;

  return (
    <div>
      <header className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-ink-900">კატეგორიები</h1>
        <Button variant="accent" size="sm" onClick={() => setEditing({})}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          ახალი კატეგორია
        </Button>
      </header>

      <DataTable
        caption="კატეგორიების სია"
        columns={columns}
        rows={categories ? asTree(categories) : []}
        loading={categories === null}
        empty={<EmptyState title="კატეგორია არ არის" description="დაამატეთ პირველი კატეგორია." />}
      />

      {editing ? (
        <CategoryDialog
          category={editing.id ? editing : null}
          categories={categories || []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(deleting)}
        title="კატეგორიის წაშლა"
        description={
          deleteError
            ? deleteError.message
            : `„${deleting?.name}“ სამუდამოდ წაიშლება. თუ მას პროდუქტები ან ქვეკატეგორიები აქვს, წაშლა უარყოფილი იქნება.`
        }
        confirmLabel="წაშლა"
        onConfirm={handleDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
