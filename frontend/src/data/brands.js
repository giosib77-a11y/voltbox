/**
 * ბრენდების ცნობარი — ლოგოს ასოსა და ბრენდის გვერდისთვის.
 * პროდუქტის `brand` ველი ამ სიის `name`-ს ეყრდნობა.
 */
export const brands = [
  { id: 'apple', name: 'Apple', country: 'აშშ' },
  { id: 'samsung', name: 'Samsung', country: 'სამხრეთ კორეა' },
  { id: 'xiaomi', name: 'Xiaomi', country: 'ჩინეთი' },
  { id: 'anker', name: 'Anker', country: 'ჩინეთი' },
  { id: 'baseus', name: 'Baseus', country: 'ჩინეთი' },
  { id: 'ugreen', name: 'Ugreen', country: 'ჩინეთი' },
  { id: 'jbl', name: 'JBL', country: 'აშშ' },
  { id: 'sony', name: 'Sony', country: 'იაპონია' },
  { id: 'belkin', name: 'Belkin', country: 'აშშ' },
  { id: 'hoco', name: 'Hoco', country: 'ჩინეთი' },
];

/** { Apple: { id, name, country }, ... } — data layer-ის სწრაფი ძებნისთვის */
export const brandsByName = Object.fromEntries(brands.map((b) => [b.name, b]));
