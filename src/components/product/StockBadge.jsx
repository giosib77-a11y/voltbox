import { Check, Clock, XCircle } from 'lucide-react';
import Badge from '../common/Badge.jsx';
import { TEXT } from '../../constants/index.js';

/**
 * მარაგის სტატუსი — მარაგშია / ბოლო ცალები / მარაგში არ არის.
 */
export default function StockBadge({ stock = 0, isLowStock = false, className = '' }) {
  if (stock <= 0) {
    return (
      <Badge tone="danger" className={className}>
        <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
        {TEXT.outOfStock}
      </Badge>
    );
  }

  if (isLowStock) {
    return (
      <Badge tone="warning" className={className}>
        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
        {`${TEXT.lowStock} — ${stock}`}
      </Badge>
    );
  }

  return (
    <Badge tone="success" className={className}>
      <Check className="h-3.5 w-3.5" aria-hidden="true" />
      {TEXT.inStock}
    </Badge>
  );
}
