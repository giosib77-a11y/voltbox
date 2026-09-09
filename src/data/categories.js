/**
 * კატეგორიების კონფიგი.
 *
 * `filters` არის *ერთადერთი* წყარო იმისა, თუ რა ფილტრები დაიხატება.
 * `FilterSidebar` გენერიკულია — ახალი კატეგორიის დამატება ნიშნავს მხოლოდ
 * ახალი ჩანაწერის დამატებას ამ მასივში.
 *
 * filter.type:
 *   checkbox — მრავლობითი არჩევანი (OR ჯგუფის შიგნით)
 *   toggle   — ჩართვა/გამორთვა; `match` განსაზღვრავს „ჩართულის“ მნიშვნელობას
 *   swatch   — ფერების ბადე (მნიშვნელობები COLOR_SWATCHES-იდან ხატავს ფერს)
 */

/** @type {import('../types.js').Category[]} */
export const categories = [
  {
    id: 'phones',
    name: 'ტელეფონები',
    slug: 'phones',
    icon: 'Smartphone',
    shortName: 'ტელეფონები',
    description: 'სმარტფონები ოფიციალური გარანტიით — Apple, Samsung, Xiaomi და სხვა.',
    filters: [
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      { key: 'specs.ram', label: 'ოპერატიული მეხსიერება', type: 'checkbox' },
      { key: 'specs.storage', label: 'მეხსიერება', type: 'checkbox' },
      { key: 'specs.screen', label: 'ეკრანის ზომა', type: 'checkbox' },
      { key: 'specs.network', label: '5G', type: 'toggle', match: '5G' },
      { key: 'specs.color', label: 'ფერი', type: 'swatch' },
    ],
  },
  {
    id: 'cables',
    name: 'კაბელები',
    slug: 'cables',
    icon: 'Cable',
    shortName: 'კაბელები',
    description: 'დამტენი და მონაცემთა კაბელები ყველა ტიპის კონექტორით.',
    filters: [
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      { key: 'specs.connector', label: 'კონექტორი', type: 'checkbox' },
      { key: 'specs.length', label: 'სიგრძე', type: 'checkbox' },
      { key: 'specs.fastCharge', label: 'სწრაფი დატენვა', type: 'toggle', match: true },
      { key: 'specs.material', label: 'მასალა', type: 'checkbox' },
      { key: 'specs.color', label: 'ფერი', type: 'swatch' },
    ],
  },
  {
    id: 'powerbanks',
    name: 'Power Bank-ები',
    slug: 'powerbanks',
    icon: 'BatteryCharging',
    shortName: 'Power Bank',
    description: 'პორტატული დამტენები 5 000-დან 30 000 mAh-მდე.',
    filters: [
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      { key: 'specs.capacity', label: 'ტევადობა', type: 'checkbox' },
      { key: 'specs.output', label: 'გამომავალი სიმძლავრე', type: 'checkbox' },
      { key: 'specs.wireless', label: 'უსადენო დატენვა', type: 'toggle', match: true },
      { key: 'specs.color', label: 'ფერი', type: 'swatch' },
    ],
  },
  {
    id: 'chargers',
    name: 'დამტენები',
    slug: 'chargers',
    icon: 'PlugZap',
    shortName: 'დამტენები',
    description: 'ქსელური და უსადენო დამტენები GaN ტექნოლოგიით.',
    filters: [
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      { key: 'specs.power', label: 'სიმძლავრე', type: 'checkbox' },
      { key: 'specs.ports', label: 'პორტები', type: 'checkbox' },
      { key: 'specs.wireless', label: 'უსადენო', type: 'toggle', match: true },
      { key: 'specs.color', label: 'ფერი', type: 'swatch' },
    ],
  },
  {
    id: 'headphones',
    name: 'ყურსასმენები',
    slug: 'headphones',
    icon: 'Headphones',
    shortName: 'ყურსასმენები',
    description: 'უსადენო და სადენიანი ყურსასმენები, TWS და over-ear მოდელები.',
    filters: [
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      { key: 'specs.type', label: 'ტიპი', type: 'checkbox' },
      { key: 'specs.wireless', label: 'უსადენო', type: 'toggle', match: true },
      { key: 'specs.anc', label: 'ხმაურის შთანთქმა (ANC)', type: 'toggle', match: true },
      { key: 'specs.playtime', label: 'მუშაობის დრო', type: 'checkbox' },
      { key: 'specs.color', label: 'ფერი', type: 'swatch' },
    ],
  },
  {
    id: 'accessories',
    name: 'აქსესუარები',
    slug: 'accessories',
    icon: 'Package',
    shortName: 'აქსესუარები',
    description: 'ქეისები, დამჭერები, ადაპტერები და დამცავი მინები.',
    filters: [
      { key: 'brand', label: 'ბრენდი', type: 'checkbox' },
      { key: 'specs.type', label: 'ტიპი', type: 'checkbox' },
      { key: 'specs.material', label: 'მასალა', type: 'checkbox' },
      { key: 'specs.compatibility', label: 'თავსებადობა', type: 'checkbox' },
      { key: 'specs.color', label: 'ფერი', type: 'swatch' },
    ],
  },
];

/** { phones: 'ტელეფონები', ... } — ძებნისა და breadcrumbs-ისთვის */
export const categoryLabels = Object.fromEntries(categories.map((c) => [c.id, c.name]));

export function getCategoryBySlug(slug) {
  return categories.find((c) => c.slug === slug) || null;
}
