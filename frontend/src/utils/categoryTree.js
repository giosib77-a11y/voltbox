/**
 * კატეგორიების ბრტყელი სიიდან — ფესვები, თითოეულს `children`-ით.
 *
 * `/categories` ყველა კატეგორიას ერთ სიაში აბრუნებს, `parentId`-ით. ადმინი
 * მშობლად მხოლოდ ფესვს უშვებს, ამიტომ ხე ორ დონეზე მეტი არ არის. კატეგორია,
 * რომლის მშობელიც სიაში არ ჩანს, ფესვად რჩება — ნავიგაციიდან არ უნდა გაქრეს.
 * რიგი სერვერისაა (position, name) და ორივე დონეზე ნარჩუნდება.
 */
export function categoryTree(categories) {
  const ids = new Set(categories.map((category) => category.id));
  const isRoot = (category) => !category.parentId || !ids.has(category.parentId);
  return categories.filter(isRoot).map((root) => ({
    ...root,
    children: categories.filter((item) => !isRoot(item) && item.parentId === root.id),
  }));
}
