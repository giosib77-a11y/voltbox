import { Check, Clock, XCircle } from 'lucide-react';
import Badge from '../common/Badge.jsx';
import { t } from '../../i18n/index.js';

/**
 * მარაგის სტატუსი — მარაგშია / ბოლო ცალები / მარაგში არ არის.
 */
export default function StockBadge({ stock = 0, isLowStock = false, className = '' }) {
  if (stock <= 0) {
    return (
      <Badge tone="danger" className={className}>
        <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
        {t('common.outOfStock')}
      </Badge>
    );
  }

  if (isLowStock) {
    return (
      <Badge tone="warning" className={className}>
        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
        {t('product.lowStockCount', { count: stock })}
      </Badge>
    );
  }

  return (
    <Badge tone="success" className={className}>
      <Check className="h-3.5 w-3.5" aria-hidden="true" />
      {t('common.inStock')}
    </Badge>
  );
}
