/**
 * frontend-ის mock მონაცემებს JSON-ად აქცევს, რომ Python-ის seed-მა წაიკითხოს.
 *
 * ერთადერთი წყარო რჩება `src/data/*.js` — JSON არსად არ კომიტდება, ყოველ
 * seed-ზე თავიდან გენერირდება. ასე ორი წყარო ვერ დაშორდება ერთმანეთს.
 *
 * გამოძახება:  node scripts/export_mock_data.mjs > out.json
 */
import { products } from '../../src/data/products.js';
import { categories } from '../../src/data/categories.js';
import { brands } from '../../src/data/brands.js';

process.stdout.write(JSON.stringify({ products, categories, brands }, null, 0));
