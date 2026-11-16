/**
 * The admin panel's own error texts, registered when the admin code loads.
 *
 * What it does: adds `apiErrors.<CODE>` for the errors only the panel can meet
 * (a taken SKU, a refused image, a category cycle...) to the Georgian texts.
 * Where it fits: imported by adminApi.js, which every admin request goes
 * through - so the texts are there before an admin error can come back, and
 * they ship in the admin chunk instead of the storefront's entry.
 * Notes: Georgian only; the panel has no English. Codes a customer can also
 * meet stay in i18n/ka.json.
 */

import { i18n } from '../i18n/index.js';
import adminKa from './i18n/ka.json';

i18n.addResourceBundle('ka', 'translation', adminKa, true, true);
