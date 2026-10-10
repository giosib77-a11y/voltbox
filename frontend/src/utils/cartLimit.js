import { MAX_CART_LINES, MAX_LINE_QTY } from '../constants/index.js';
import { t } from '../i18n/index.js';

/** The sentence for a limit `cartLimitHit` reported: why the add did not go through whole. */
export function cartLimitMessage(limit) {
  return limit === 'lines'
    ? t('cart.maxLines', { count: MAX_CART_LINES })
    : t('cart.maxPerProduct', { count: MAX_LINE_QTY });
}
