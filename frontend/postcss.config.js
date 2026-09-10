import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';
import { fileURLToPath, URL } from 'node:url';

/**
 * Tailwind-ის კონფიგი აშკარა გზით გადაეცემა.
 *
 * ნაგულისხმევად Tailwind `tailwind.config.js`-ს `process.cwd()`-იდან ეძებს.
 * monorepo-ში, თუ ბრძანება repo-ს ძირიდან გაეშვა, ვერ პოულობს — და **შეცდომას
 * არ აგდებს**: `content` ცარიელი რჩება, გამოდის warning და ბანდლი უსტილოდ
 * აიწყობა. აშკარა გზა ამ ჩუმ ხარვეზს კეტავს.
 */
const configPath = fileURLToPath(new URL('./tailwind.config.js', import.meta.url));

export default {
  plugins: [tailwindcss(configPath), autoprefixer()],
};
