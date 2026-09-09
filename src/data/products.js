/**
 * Mock პროდუქტების ბაზა.
 *
 * ⚠️  UI-მ ეს ფაილი პირდაპირ *არასდროს* არ უნდა დაიმპორტოს — მხოლოდ
 *     `services/api.js`-ის გავლით. Backend-ის ჩართვისას ეს ფაილი უბრალოდ
 *     წყვეტს გამოყენებას.
 *
 * წარმოებული (derived) მნიშვნელობები — discountPercent, hasDiscount, inStock,
 * isLowStock — აქ ხელით არ იწერება; მათ `services/mockApi.js` ითვლის.
 */

const IMAGE_BASE = '/images/products';

/** ნაგულისხმევი ველები + სურათების და თარიღის აწყობა. */
function make(input) {
  const { created, imageCount = 3, ...rest } = input;
  return {
    oldPrice: null,
    isNew: false,
    isFeatured: false,
    tags: [],
    ...rest,
    images: Array.from({ length: imageCount }, (_, i) => `${IMAGE_BASE}/${rest.id}-${i + 1}.svg`),
    createdAt: `${created}T10:00:00.000Z`,
  };
}

/* ========================================================================== */
/*  ტელეფონები (15)                                                           */
/* ========================================================================== */

const phones = [
  {
    id: 'ph-001', slug: 'samsung-galaxy-s24-256gb', name: 'Samsung Galaxy S24 256GB',
    brand: 'Samsung', category: 'phones',
    shortDescription: '6.2" AMOLED, 8GB RAM, 5G',
    description: 'Samsung Galaxy S24 არის კომპაქტური ფლაგმანი 6.2 დიუიმიან Dynamic AMOLED 2X ეკრანით, Exynos 2400 პროცესორითა და Galaxy AI-ს ფუნქციებით. სამმაგი კამერა 50 MP ძირითადი სენსორით უზრუნველყოფს დეტალურ ფოტოებს ღამითაც.',
    price: 2499, oldPrice: 2799, rating: 4.6, reviewsCount: 128, stock: 12,
    isNew: true, isFeatured: true,
    specs: { ram: '8 GB', storage: '256 GB', screen: '6.2"', network: '5G', color: 'შავი', camera: '50 MP', battery: '4000 mAh', os: 'Android 14', warranty: '24 თვე' },
    tags: ['5g', 'amoled', 'ფლაგმანი'], created: '2026-07-14',
  },
  {
    id: 'ph-002', slug: 'apple-iphone-15-128gb', name: 'Apple iPhone 15 128GB',
    brand: 'Apple', category: 'phones',
    shortDescription: '6.1" Super Retina XDR, USB-C, 5G',
    description: 'iPhone 15 გთავაზობთ Dynamic Island-ს, 48 MP ძირითად კამერას და USB-C პორტს. A16 Bionic ჩიპი უზრუნველყოფს მაღალ წარმადობას ენერგოეფექტურობის შენარჩუნებით.',
    price: 2899, rating: 4.8, reviewsCount: 214, stock: 8, isFeatured: true,
    specs: { ram: '6 GB', storage: '128 GB', screen: '6.1"', network: '5G', color: 'თეთრი', camera: '48 MP', battery: '3349 mAh', os: 'iOS 17', warranty: '12 თვე' },
    tags: ['5g', 'usb-c', 'ios'], created: '2026-03-02',
  },
  {
    id: 'ph-003', slug: 'apple-iphone-15-pro-256gb', name: 'Apple iPhone 15 Pro 256GB',
    brand: 'Apple', category: 'phones',
    shortDescription: '6.1" ProMotion, ტიტანი, A17 Pro',
    description: 'iPhone 15 Pro ტიტანის კორპუსით, A17 Pro ჩიპითა და 120Hz ProMotion ეკრანით. Action ღილაკი და პროფესიონალური სამმაგი კამერის სისტემა 3x ოპტიკური zoom-ით.',
    price: 3799, oldPrice: 3999, rating: 4.9, reviewsCount: 96, stock: 5, isNew: true,
    specs: { ram: '8 GB', storage: '256 GB', screen: '6.1"', network: '5G', color: 'ვერცხლისფერი', camera: '48 MP', battery: '3274 mAh', os: 'iOS 17', warranty: '12 თვე' },
    tags: ['5g', 'promotion', 'ტიტანი'], created: '2026-06-21',
  },
  {
    id: 'ph-004', slug: 'xiaomi-redmi-note-13-pro-256gb', name: 'Xiaomi Redmi Note 13 Pro 256GB',
    brand: 'Xiaomi', category: 'phones',
    shortDescription: '6.7" AMOLED 120Hz, 200 MP კამერა',
    description: 'Redmi Note 13 Pro გამოირჩევა 200 MP კამერით და 6.7 დიუიმიანი 120Hz AMOLED ეკრანით. 67W სწრაფი დატენვა ბატარეას 45 წუთში ავსებს.',
    price: 949, oldPrice: 1099, rating: 4.4, reviewsCount: 341, stock: 24,
    specs: { ram: '8 GB', storage: '256 GB', screen: '6.7"', network: '5G', color: 'შავი', camera: '200 MP', battery: '5100 mAh', os: 'Android 13', warranty: '24 თვე' },
    tags: ['5g', 'amoled', '120hz'], created: '2026-01-18',
  },
  {
    id: 'ph-005', slug: 'samsung-galaxy-a55-128gb', name: 'Samsung Galaxy A55 128GB',
    brand: 'Samsung', category: 'phones',
    shortDescription: '6.5" Super AMOLED, 5G, IP67',
    description: 'Galaxy A55 აერთიანებს ლითონის კორპუსს, Super AMOLED ეკრანსა და IP67 დაცვას. ოპტიკური სტაბილიზაციის მქონე 50 MP კამერა ღამის ფოტოებისთვისაც გამოდგება.',
    price: 1199, rating: 4.5, reviewsCount: 187, stock: 19,
    specs: { ram: '8 GB', storage: '128 GB', screen: '6.5"', network: '5G', color: 'ლურჯი', camera: '50 MP', battery: '5000 mAh', os: 'Android 14', warranty: '24 თვე' },
    tags: ['5g', 'ip67', 'amoled'], created: '2026-02-11',
  },
  {
    id: 'ph-006', slug: 'xiaomi-14-512gb', name: 'Xiaomi 14 512GB',
    brand: 'Xiaomi', category: 'phones',
    shortDescription: '6.2" LTPO, Leica ოპტიკა, Snapdragon 8 Gen 3',
    description: 'Xiaomi 14 შექმნილია Leica-ს თანაავტორობით და აღჭურვილია Snapdragon 8 Gen 3 პროცესორით. კომპაქტური კორპუსი, LTPO ეკრანი და 90W სწრაფი დატენვა.',
    price: 2699, rating: 4.7, reviewsCount: 74, stock: 7, isFeatured: true,
    specs: { ram: '12 GB', storage: '512 GB', screen: '6.2"', network: '5G', color: 'მწვანე', camera: '50 MP', battery: '4610 mAh', os: 'Android 14', warranty: '24 თვე' },
    tags: ['5g', 'leica', 'ფლაგმანი'], created: '2026-04-08',
  },
  {
    id: 'ph-007', slug: 'apple-iphone-14-128gb', name: 'Apple iPhone 14 128GB',
    brand: 'Apple', category: 'phones',
    shortDescription: '6.1" Super Retina XDR, A15 Bionic',
    description: 'iPhone 14 A15 Bionic ჩიპით, გაუმჯობესებული ღამის რეჟიმითა და ავარიის აღმოჩენის ფუნქციით. საიმედო არჩევანი წლიური განახლებებით.',
    price: 2299, oldPrice: 2499, rating: 4.7, reviewsCount: 268, stock: 14,
    specs: { ram: '6 GB', storage: '128 GB', screen: '6.1"', network: '5G', color: 'ლურჯი', camera: '12 MP', battery: '3279 mAh', os: 'iOS 17', warranty: '12 თვე' },
    tags: ['5g', 'ios'], created: '2025-11-05',
  },
  {
    id: 'ph-008', slug: 'samsung-galaxy-s24-ultra-512gb', name: 'Samsung Galaxy S24 Ultra 512GB',
    brand: 'Samsung', category: 'phones',
    shortDescription: '6.8" QHD+ AMOLED, S Pen, 200 MP',
    description: 'Galaxy S24 Ultra ტიტანის კორპუსით, ჩაშენებული S Pen-ითა და 200 MP კამერით. QHD+ ეკრანი და 5x ოპტიკური zoom პროფესიონალური გადაღებისთვის.',
    price: 4299, rating: 4.9, reviewsCount: 152, stock: 6, isNew: true, isFeatured: true,
    specs: { ram: '12 GB', storage: '512 GB', screen: '6.8"', network: '5G', color: 'ნაცრისფერი', camera: '200 MP', battery: '5000 mAh', os: 'Android 14', warranty: '24 თვე' },
    tags: ['5g', 's-pen', 'ფლაგმანი', 'amoled'], created: '2026-08-02',
  },
  {
    id: 'ph-009', slug: 'xiaomi-redmi-13c-128gb', name: 'Xiaomi Redmi 13C 128GB',
    brand: 'Xiaomi', category: 'phones',
    shortDescription: '6.7" HD+, 5000 mAh, ბიუჯეტური',
    description: 'Redmi 13C ხელმისაწვდომი სმარტფონია დიდი ეკრანითა და 5000 mAh ბატარეით, რომელიც სრულ დღეს უძლებს აქტიური გამოყენებისას.',
    price: 449, rating: 4.1, reviewsCount: 412, stock: 40,
    specs: { ram: '6 GB', storage: '128 GB', screen: '6.7"', network: '4G', color: 'ლურჯი', camera: '50 MP', battery: '5000 mAh', os: 'Android 13', warranty: '24 თვე' },
    tags: ['ბიუჯეტური'], created: '2025-09-12',
  },
  {
    id: 'ph-010', slug: 'samsung-galaxy-a15-128gb', name: 'Samsung Galaxy A15 128GB',
    brand: 'Samsung', category: 'phones',
    shortDescription: '6.5" Super AMOLED, 5000 mAh',
    description: 'Galaxy A15 გთავაზობთ Super AMOLED ეკრანს ამ ფასის სეგმენტში და 25W სწრაფ დატენვას. სამმაგი კამერა და დიდი ბატარეა ყოველდღიური გამოყენებისთვის.',
    price: 649, oldPrice: 749, rating: 4.3, reviewsCount: 296, stock: 31,
    specs: { ram: '6 GB', storage: '128 GB', screen: '6.5"', network: '4G', color: 'შავი', camera: '50 MP', battery: '5000 mAh', os: 'Android 14', warranty: '24 თვე' },
    tags: ['ბიუჯეტური', 'amoled'], created: '2025-10-20',
  },
  {
    id: 'ph-011', slug: 'apple-iphone-13-128gb', name: 'Apple iPhone 13 128GB',
    brand: 'Apple', category: 'phones',
    shortDescription: '6.1" Super Retina XDR, A15 Bionic',
    description: 'iPhone 13 რჩება ერთ-ერთ ყველაზე დაბალანსებულ არჩევანად — მძლავრი A15 ჩიპი, ხარისხიანი ეკრანი და საიმედო ბატარეა.',
    price: 1899, rating: 4.6, reviewsCount: 388, stock: 0,
    specs: { ram: '6 GB', storage: '128 GB', screen: '6.1"', network: '5G', color: 'ვარდისფერი', camera: '12 MP', battery: '3240 mAh', os: 'iOS 17', warranty: '12 თვე' },
    tags: ['5g', 'ios'], created: '2025-07-15',
  },
  {
    id: 'ph-012', slug: 'xiaomi-poco-x6-pro-256gb', name: 'Xiaomi Poco X6 Pro 256GB',
    brand: 'Xiaomi', category: 'phones',
    shortDescription: '6.7" AMOLED 120Hz, Dimensity 8300',
    description: 'Poco X6 Pro Dimensity 8300-Ultra პროცესორით ერთ-ერთი ყველაზე მძლავრი შუა სეგმენტის სმარტფონია. 67W დატენვა და 120Hz AMOLED ეკრანი გეიმინგისთვის.',
    price: 1149, rating: 4.5, reviewsCount: 163, stock: 15, isNew: true,
    specs: { ram: '12 GB', storage: '256 GB', screen: '6.7"', network: '5G', color: 'ყვითელი', camera: '64 MP', battery: '5000 mAh', os: 'Android 14', warranty: '24 თვე' },
    tags: ['5g', 'გეიმინგი', '120hz'], created: '2026-06-30',
  },
  {
    id: 'ph-013', slug: 'samsung-galaxy-s23-fe-256gb', name: 'Samsung Galaxy S23 FE 256GB',
    brand: 'Samsung', category: 'phones',
    shortDescription: '6.5" Dynamic AMOLED, 3x zoom',
    description: 'Galaxy S23 FE ფლაგმანური ფუნქციების ხელმისაწვდომი ვერსიაა — 3x ოპტიკური zoom, IP68 დაცვა და უსადენო დატენვა.',
    price: 1799, oldPrice: 1999, rating: 4.5, reviewsCount: 121, stock: 11,
    specs: { ram: '8 GB', storage: '256 GB', screen: '6.5"', network: '5G', color: 'იისფერი', camera: '50 MP', battery: '4500 mAh', os: 'Android 14', warranty: '24 თვე' },
    tags: ['5g', 'ip68', 'amoled'], created: '2025-12-09',
  },
  {
    id: 'ph-014', slug: 'apple-iphone-15-plus-256gb', name: 'Apple iPhone 15 Plus 256GB',
    brand: 'Apple', category: 'phones',
    shortDescription: '6.7" Super Retina XDR, დიდი ბატარეა',
    description: 'iPhone 15 Plus დიდი ეკრანითა და ყველაზე გამძლე ბატარეით iPhone 15-ის ხაზში. 48 MP კამერა და USB-C პორტი.',
    price: 3399, rating: 4.8, reviewsCount: 87, stock: 9,
    specs: { ram: '6 GB', storage: '256 GB', screen: '6.7"', network: '5G', color: 'მწვანე', camera: '48 MP', battery: '4383 mAh', os: 'iOS 17', warranty: '12 თვე' },
    tags: ['5g', 'usb-c', 'ios'], created: '2026-03-02',
  },
  {
    id: 'ph-015', slug: 'xiaomi-redmi-note-13-128gb', name: 'Xiaomi Redmi Note 13 128GB',
    brand: 'Xiaomi', category: 'phones',
    shortDescription: '6.7" AMOLED, 108 MP კამერა',
    description: 'Redmi Note 13 გთავაზობთ 108 MP კამერას და AMOLED ეკრანს ხელმისაწვდომ ფასად. თხელი კორპუსი და 33W სწრაფი დატენვა.',
    price: 699, rating: 4.3, reviewsCount: 254, stock: 0,
    specs: { ram: '6 GB', storage: '128 GB', screen: '6.7"', network: '4G', color: 'თეთრი', camera: '108 MP', battery: '5000 mAh', os: 'Android 13', warranty: '24 თვე' },
    tags: ['amoled', 'ბიუჯეტური'], created: '2025-08-28',
  },
];

/* ========================================================================== */
/*  კაბელები (12)                                                             */
/* ========================================================================== */

const cables = [
  {
    id: 'cb-001', slug: 'anker-powerline-iii-usb-c-usb-c-2m', name: 'Anker PowerLine III USB-C — USB-C კაბელი 2მ',
    brand: 'Anker', category: 'cables',
    shortDescription: '100W, ნეილონის წნული, 2 მეტრი',
    description: 'Anker PowerLine III გამძლე ნეილონის წნულით და 100W სიმძლავრის მხარდაჭერით. გამოცდილია 25 000-ჯერ მოხრაზე, შესაფერისია ლეპტოპისა და ტელეფონისთვის.',
    price: 45, oldPrice: 59, rating: 4.8, reviewsCount: 512, stock: 60,
    specs: { connector: 'USB-C — USB-C', length: '2 მ', fastCharge: true, material: 'ნეილონი', color: 'შავი', power: '100 W', warranty: '18 თვე' },
    tags: ['usb-c', 'pd', '100w'], created: '2025-10-02',
  },
  {
    id: 'cb-002', slug: 'baseus-cafule-usb-c-lightning-1m', name: 'Baseus Cafule USB-C — Lightning კაბელი 1მ',
    brand: 'Baseus', category: 'cables',
    shortDescription: '20W PD, ნეილონი, 1 მეტრი',
    description: 'Baseus Cafule კაბელი iPhone-ის სწრაფი დატენვისთვის. 20W Power Delivery ბატარეას 30 წუთში 50%-მდე ავსებს.',
    price: 39, rating: 4.5, reviewsCount: 287, stock: 45,
    specs: { connector: 'USB-C — Lightning', length: '1 მ', fastCharge: true, material: 'ნეილონი', color: 'შავი', power: '20 W', warranty: '12 თვე' },
    tags: ['lightning', 'pd', 'iphone'], created: '2025-11-18',
  },
  {
    id: 'cb-003', slug: 'ugreen-usb-a-usb-c-2m', name: 'Ugreen USB-A — USB-C კაბელი 2მ',
    brand: 'Ugreen', category: 'cables',
    shortDescription: '18W QC, TPE, 2 მეტრი',
    description: 'Ugreen-ის საბაზისო USB-A — USB-C კაბელი Quick Charge 3.0 მხარდაჭერით. რბილი TPE გარსი და გამაგრებული კონექტორები.',
    price: 29, rating: 4.4, reviewsCount: 198, stock: 80,
    specs: { connector: 'USB-A — USB-C', length: '2 მ', fastCharge: true, material: 'TPE', color: 'შავი', power: '18 W', warranty: '12 თვე' },
    tags: ['usb-c', 'quick-charge'], created: '2025-09-25',
  },
  {
    id: 'cb-004', slug: 'apple-usb-c-lightning-1m', name: 'Apple USB-C — Lightning კაბელი 1მ',
    brand: 'Apple', category: 'cables',
    shortDescription: 'ორიგინალი MFi, 1 მეტრი',
    description: 'Apple-ის ორიგინალი კაბელი iPhone-ისა და iPad-ის სწრაფი დატენვისთვის. სრული თავსებადობა iOS-ის ყველა ვერსიასთან.',
    price: 79, oldPrice: 89, rating: 4.7, reviewsCount: 342, stock: 22,
    specs: { connector: 'USB-C — Lightning', length: '1 მ', fastCharge: true, material: 'სილიკონი', color: 'თეთრი', power: '20 W', warranty: '12 თვე' },
    tags: ['lightning', 'mfi', 'iphone'], created: '2025-08-14',
  },
  {
    id: 'cb-005', slug: 'hoco-x20-usb-a-micro-usb-1m', name: 'Hoco X20 USB-A — Micro USB კაბელი 1მ',
    brand: 'Hoco', category: 'cables',
    shortDescription: '10W, სილიკონი, 1 მეტრი',
    description: 'ხელმისაწვდომი Micro USB კაბელი ძველი მოდელის ტელეფონებისა და აქსესუარებისთვის. რბილი სილიკონის გარსი არ იხლართება.',
    price: 12, rating: 4.0, reviewsCount: 156, stock: 120,
    specs: { connector: 'USB-A — Micro USB', length: '1 მ', fastCharge: false, material: 'სილიკონი', color: 'თეთრი', power: '10 W', warranty: '6 თვე' },
    tags: ['micro-usb', 'ბიუჯეტური'], created: '2025-06-10',
  },
  {
    id: 'cb-006', slug: 'baseus-usb-c-usb-c-100w-2m', name: 'Baseus Flash Series USB-C — USB-C 100W კაბელი 2მ',
    brand: 'Baseus', category: 'cables',
    shortDescription: '100W, ჩაშენებული დისპლეი, 2 მეტრი',
    description: 'Baseus Flash Series კაბელი ჩაშენებული LED დისპლეით, რომელიც რეალურ დროში აჩვენებს დატენვის სიმძლავრეს. 100W მხარდაჭერა ლეპტოპისთვისაც.',
    price: 55, rating: 4.6, reviewsCount: 134, stock: 38, isNew: true,
    specs: { connector: 'USB-C — USB-C', length: '2 მ', fastCharge: true, material: 'ნეილონი', color: 'ნაცრისფერი', power: '100 W', warranty: '12 თვე' },
    tags: ['usb-c', 'pd', '100w', 'დისპლეი'], created: '2026-07-05',
  },
  {
    id: 'cb-007', slug: 'ugreen-usb-c-usb-c-3m', name: 'Ugreen USB-C — USB-C კაბელი 3მ',
    brand: 'Ugreen', category: 'cables',
    shortDescription: '60W PD, ნეილონი, 3 მეტრი',
    description: 'გრძელი 3-მეტრიანი კაბელი, როცა როზეტი შორსაა. 60W Power Delivery და გამძლე ნეილონის წნული.',
    price: 49, rating: 4.5, reviewsCount: 92, stock: 27,
    specs: { connector: 'USB-C — USB-C', length: '3 მ', fastCharge: true, material: 'ნეილონი', color: 'შავი', power: '60 W', warranty: '18 თვე' },
    tags: ['usb-c', 'pd', 'გრძელი'], created: '2026-01-30',
  },
  {
    id: 'cb-008', slug: 'anker-usb-a-lightning-1m', name: 'Anker PowerLine USB-A — Lightning კაბელი 1მ',
    brand: 'Anker', category: 'cables',
    shortDescription: 'MFi სერტიფიცირებული, 1 მეტრი',
    description: 'MFi სერტიფიცირებული Lightning კაბელი Anker-ისგან. გამაგრებული ბოლოები და უწყვეტი კავშირი iOS-ის განახლებების შემდეგაც.',
    price: 35, rating: 4.6, reviewsCount: 221, stock: 54,
    specs: { connector: 'USB-A — Lightning', length: '1 მ', fastCharge: false, material: 'TPE', color: 'თეთრი', power: '12 W', warranty: '18 თვე' },
    tags: ['lightning', 'mfi', 'iphone'], created: '2025-07-22',
  },
  {
    id: 'cb-009', slug: 'belkin-boostcharge-usb-c-usb-c-1-5m', name: 'Belkin BoostCharge USB-C — USB-C კაბელი 1.5მ',
    brand: 'Belkin', category: 'cables',
    shortDescription: '240W EPR, წნული, 1.5 მეტრი',
    description: 'Belkin BoostCharge Pro უახლესი USB-C EPR სტანდარტით — 240W-მდე სიმძლავრე და 480 Mb/s მონაცემთა გადაცემა. მოწოდებულია სამაგრი ღვედით.',
    price: 65, rating: 4.7, reviewsCount: 78, stock: 31, isNew: true, isFeatured: true,
    specs: { connector: 'USB-C — USB-C', length: '1.5 მ', fastCharge: true, material: 'ნეილონი', color: 'შავი', power: '240 W', warranty: '24 თვე' },
    tags: ['usb-c', 'pd', 'epr'], created: '2026-08-12',
  },
  {
    id: 'cb-010', slug: 'baseus-usb-c-usb-c-0-5m', name: 'Baseus Superior USB-C — USB-C კაბელი 0.5მ',
    brand: 'Baseus', category: 'cables',
    shortDescription: '100W, კომპაქტური, 0.5 მეტრი',
    description: 'მოკლე კაბელი Power Bank-თან ან მაგიდის დამტენთან გამოსაყენებლად. 100W სიმძლავრე კომპაქტურ ზომაში.',
    price: 25, rating: 4.4, reviewsCount: 143, stock: 66,
    specs: { connector: 'USB-C — USB-C', length: '0.5 მ', fastCharge: true, material: 'სილიკონი', color: 'თეთრი', power: '100 W', warranty: '12 თვე' },
    tags: ['usb-c', 'მოკლე', 'pd'], created: '2025-12-16',
  },
  {
    id: 'cb-011', slug: 'ugreen-usb-a-usb-c-0-5m', name: 'Ugreen USB-A — USB-C კაბელი 0.5მ',
    brand: 'Ugreen', category: 'cables',
    shortDescription: '18W, კომპაქტური, 0.5 მეტრი',
    description: 'მოკლე USB-A — USB-C კაბელი ავტომობილის ან Power Bank-ის დამტენისთვის. მაგარი კონექტორები და გამაგრებული ბოლოები.',
    price: 19, rating: 4.3, reviewsCount: 111, stock: 0,
    specs: { connector: 'USB-A — USB-C', length: '0.5 მ', fastCharge: true, material: 'TPE', color: 'შავი', power: '18 W', warranty: '12 თვე' },
    tags: ['usb-c', 'მოკლე'], created: '2025-09-03',
  },
  {
    id: 'cb-012', slug: 'hoco-usb-c-lightning-2m', name: 'Hoco X88 USB-C — Lightning კაბელი 2მ',
    brand: 'Hoco', category: 'cables',
    shortDescription: '20W PD, სილიკონი, 2 მეტრი',
    description: 'გრძელი Lightning კაბელი საწოლთან ან დივანთან დასატენად. 20W Power Delivery და რბილი, მოქნილი გარსი.',
    price: 27, oldPrice: 35, rating: 4.2, reviewsCount: 167, stock: 73,
    specs: { connector: 'USB-C — Lightning', length: '2 მ', fastCharge: true, material: 'სილიკონი', color: 'თეთრი', power: '20 W', warranty: '6 თვე' },
    tags: ['lightning', 'iphone', 'pd'], created: '2026-02-27',
  },
];

/* ========================================================================== */
/*  Power Bank-ები (10)                                                       */
/* ========================================================================== */

const powerbanks = [
  {
    id: 'pb-001', slug: 'anker-powercore-10000', name: 'Anker PowerCore 10000mAh',
    brand: 'Anker', category: 'powerbanks',
    shortDescription: '10 000 mAh, 20W PD, კომპაქტური',
    description: 'Anker PowerCore 10000 ჯიბის ზომის Power Bank-ია, რომელიც iPhone-ს ორჯერ სრულად ტენავს. 20W Power Delivery გამოსავალი და MultiProtect დაცვის სისტემა.',
    price: 129, oldPrice: 149, rating: 4.8, reviewsCount: 634, stock: 42, isFeatured: true,
    specs: { capacity: '10 000 mAh', output: '20 W', wireless: false, ports: 'USB-C + USB-A', color: 'შავი', weight: '194 გ', warranty: '18 თვე' },
    tags: ['pd', 'კომპაქტური', 'usb-c'], created: '2025-10-11',
  },
  {
    id: 'pb-002', slug: 'anker-powercore-20000', name: 'Anker PowerCore 20000mAh',
    brand: 'Anker', category: 'powerbanks',
    shortDescription: '20 000 mAh, 30W PD, ორი პორტი',
    description: 'დიდი ტევადობის Power Bank შორ მოგზაურობებისთვის — 20 000 mAh საკმარისია ტელეფონის ოთხჯერ ან ლეპტოპის ერთხელ დასატენად. 30W USB-C გამოსავალი.',
    price: 199, rating: 4.7, reviewsCount: 418, stock: 28,
    specs: { capacity: '20 000 mAh', output: '30 W', wireless: false, ports: 'USB-C + USB-A', color: 'შავი', weight: '345 გ', warranty: '18 თვე' },
    tags: ['pd', 'დიდი-ტევადობა', 'usb-c'], created: '2025-11-29',
  },
  {
    id: 'pb-003', slug: 'baseus-bipow-20000', name: 'Baseus Bipow 20000mAh',
    brand: 'Baseus', category: 'powerbanks',
    shortDescription: '20 000 mAh, 20W, ციფრული დისპლეი',
    description: 'Baseus Bipow ციფრული დისპლეით, რომელიც ზუსტად აჩვენებს დარჩენილ მუხტს პროცენტებში. სამი გამომავალი პორტი ერთდროული დატენვისთვის.',
    price: 159, oldPrice: 189, rating: 4.5, reviewsCount: 302, stock: 35,
    specs: { capacity: '20 000 mAh', output: '20 W', wireless: false, ports: '2× USB-A + USB-C', color: 'ლურჯი', weight: '388 გ', warranty: '12 თვე' },
    tags: ['დისპლეი', 'დიდი-ტევადობა'], created: '2026-01-08',
  },
  {
    id: 'pb-004', slug: 'xiaomi-redmi-power-bank-20000', name: 'Xiaomi Redmi Power Bank 20000mAh',
    brand: 'Xiaomi', category: 'powerbanks',
    shortDescription: '20 000 mAh, 18W, ორმხრივი დატენვა',
    description: 'Xiaomi-ს საიმედო Power Bank ორმხრივი სწრაფი დატენვით. თავსებადია სმარტფონებთან, ტაბლეტებთან და უსადენო ყურსასმენებთან.',
    price: 149, rating: 4.4, reviewsCount: 521, stock: 47,
    specs: { capacity: '20 000 mAh', output: '18 W', wireless: false, ports: '2× USB-A + USB-C', color: 'თეთრი', weight: '440 გ', warranty: '12 თვე' },
    tags: ['დიდი-ტევადობა', 'ბიუჯეტური'], created: '2025-08-19',
  },
  {
    id: 'pb-005', slug: 'baseus-magnetic-10000', name: 'Baseus Magnetic 10000mAh MagSafe',
    brand: 'Baseus', category: 'powerbanks',
    shortDescription: '10 000 mAh, უსადენო მაგნიტური დატენვა',
    description: 'მაგნიტური Power Bank, რომელიც პირდაპირ ეკვრის iPhone-ის ზურგს და უსადენოდ ტენავს. კაბელის გარეშე გამოყენება ჩანთაშიც კი.',
    price: 179, rating: 4.5, reviewsCount: 156, stock: 24, isNew: true,
    specs: { capacity: '10 000 mAh', output: '20 W', wireless: true, ports: 'USB-C', color: 'თეთრი', weight: '215 გ', warranty: '12 თვე' },
    tags: ['magsafe', 'უსადენო', 'მაგნიტური'], created: '2026-06-14',
  },
  {
    id: 'pb-006', slug: 'ugreen-powerbank-20000-65w', name: 'Ugreen 20000mAh 65W Power Bank',
    brand: 'Ugreen', category: 'powerbanks',
    shortDescription: '20 000 mAh, 65W, ლეპტოპისთვისაც',
    description: '65W გამომავალი სიმძლავრე საკმარისია MacBook Air-ისა და უმეტესი ულტრაბუქის დასატენად. ციფრული დისპლეი და სამი პორტი.',
    price: 289, rating: 4.8, reviewsCount: 97, stock: 18, isNew: true, isFeatured: true,
    specs: { capacity: '20 000 mAh', output: '65 W', wireless: false, ports: '2× USB-C + USB-A', color: 'ნაცრისფერი', weight: '420 გ', warranty: '24 თვე' },
    tags: ['pd', 'ლეპტოპი', '65w', 'დისპლეი'], created: '2026-07-27',
  },
  {
    id: 'pb-007', slug: 'hoco-j72-10000', name: 'Hoco J72 10000mAh',
    brand: 'Hoco', category: 'powerbanks',
    shortDescription: '10 000 mAh, 18W, ხელმისაწვდომი',
    description: 'ხელმისაწვდომი Power Bank ყოველდღიური გამოყენებისთვის. LED ინდიკატორი მუხტის დონისთვის და ორი USB-A პორტი.',
    price: 79, rating: 4.1, reviewsCount: 243, stock: 88,
    specs: { capacity: '10 000 mAh', output: '18 W', wireless: false, ports: '2× USB-A', color: 'შავი', weight: '230 გ', warranty: '6 თვე' },
    tags: ['ბიუჯეტური', 'კომპაქტური'], created: '2025-06-25',
  },
  {
    id: 'pb-008', slug: 'anker-maggo-5000', name: 'Anker MagGo 5000mAh',
    brand: 'Anker', category: 'powerbanks',
    shortDescription: '5 000 mAh, მაგნიტური, ულტრა-თხელი',
    description: 'ულტრა-თხელი მაგნიტური Power Bank, რომელიც ტელეფონის სისქეს თითქმის არ ზრდის. იდეალურია ერთდღიანი გასვლისთვის.',
    price: 149, rating: 4.4, reviewsCount: 128, stock: 33,
    specs: { capacity: '5 000 mAh', output: '20 W', wireless: true, ports: 'USB-C', color: 'თეთრი', weight: '128 გ', warranty: '18 თვე' },
    tags: ['magsafe', 'უსადენო', 'თხელი'], created: '2026-03-19',
  },
  {
    id: 'pb-009', slug: 'xiaomi-power-bank-30000', name: 'Xiaomi Power Bank 30000mAh',
    brand: 'Xiaomi', category: 'powerbanks',
    shortDescription: '30 000 mAh, 22.5W, მაქსიმალური ტევადობა',
    description: 'ყველაზე დიდი ტევადობის მოდელი ჩვენს ასორტიმენტში — 30 000 mAh საკმარისია მთელი კვირის მოგზაურობისთვის. სამი მოწყობილობის ერთდროული დატენვა.',
    price: 249, oldPrice: 279, rating: 4.6, reviewsCount: 184, stock: 21,
    specs: { capacity: '30 000 mAh', output: '22.5 W', wireless: false, ports: '2× USB-A + USB-C', color: 'შავი', weight: '635 გ', warranty: '12 თვე' },
    tags: ['დიდი-ტევადობა', 'მოგზაურობა'], created: '2026-02-05',
  },
  {
    id: 'pb-010', slug: 'baseus-adaman-26800', name: 'Baseus Adaman 26800mAh',
    brand: 'Baseus', category: 'powerbanks',
    shortDescription: '26 800 mAh, 30W, მეტალის კორპუსი',
    description: 'ლითონის კორპუსში ჩასმული 26 800 mAh Power Bank ციფრული დისპლეითა და 30W სწრაფი დატენვით. ოთხი პორტი ერთდროული გამოყენებისთვის.',
    price: 219, rating: 4.5, reviewsCount: 139, stock: 0,
    specs: { capacity: '26 800 mAh', output: '30 W', wireless: false, ports: '2× USB-A + 2× USB-C', color: 'შავი', weight: '580 გ', warranty: '12 თვე' },
    tags: ['დიდი-ტევადობა', 'დისპლეი', 'pd'], created: '2025-12-22',
  },
];

/* ========================================================================== */
/*  დამტენები (8)                                                             */
/* ========================================================================== */

const chargers = [
  {
    id: 'ch-001', slug: 'anker-511-nano-30w', name: 'Anker 511 Nano 30W დამტენი',
    brand: 'Anker', category: 'chargers',
    shortDescription: '30W GaN, ულტრა-კომპაქტური',
    description: 'GaN ტექნოლოგიაზე აგებული 30W დამტენი, რომელიც ჩვეულებრივ 20W ადაპტერზე პატარაა. ტენავს iPhone-ს, iPad-ს და MacBook Air-საც.',
    price: 69, oldPrice: 79, rating: 4.8, reviewsCount: 376, stock: 52,
    specs: { power: '30 W', ports: '1 პორტი', wireless: false, fastCharge: true, color: 'თეთრი', compatibility: 'უნივერსალური', warranty: '18 თვე' },
    tags: ['gan', 'pd', 'კომპაქტური'], created: '2025-11-12',
  },
  {
    id: 'ch-002', slug: 'apple-20w-usb-c-adapter', name: 'Apple 20W USB-C დამტენი',
    brand: 'Apple', category: 'chargers',
    shortDescription: '20W PD, ორიგინალი',
    description: 'Apple-ის ორიგინალი 20W ადაპტერი iPhone-ისა და iPad-ის სწრაფი დატენვისთვის. 30 წუთში 50%-მდე მუხტი.',
    price: 65, rating: 4.6, reviewsCount: 289, stock: 40,
    specs: { power: '20 W', ports: '1 პორტი', wireless: false, fastCharge: true, color: 'თეთრი', compatibility: 'iPhone', warranty: '12 თვე' },
    tags: ['pd', 'iphone', 'ორიგინალი'], created: '2025-07-08',
  },
  {
    id: 'ch-003', slug: 'ugreen-nexode-65w', name: 'Ugreen Nexode 65W GaN დამტენი',
    brand: 'Ugreen', category: 'chargers',
    shortDescription: '65W GaN, 3 პორტი',
    description: 'სამპორტიანი GaN დამტენი, რომელიც ერთდროულად ტენავს ლეპტოპს, ტელეფონსა და ყურსასმენებს. ინტელექტუალური სიმძლავრის განაწილება.',
    price: 129, rating: 4.8, reviewsCount: 212, stock: 36, isFeatured: true,
    specs: { power: '65 W', ports: '3 პორტი', wireless: false, fastCharge: true, color: 'შავი', compatibility: 'უნივერსალური', warranty: '24 თვე' },
    tags: ['gan', 'pd', 'ლეპტოპი'], created: '2026-01-24',
  },
  {
    id: 'ch-004', slug: 'baseus-gan5-100w', name: 'Baseus GaN5 Pro 100W დამტენი',
    brand: 'Baseus', category: 'chargers',
    shortDescription: '100W GaN, 4 პორტი, დისპლეი',
    description: 'ოთხპორტიანი 100W სადგური ციფრული დისპლეით — საკმარისია MacBook Pro-სთვის და კიდევ სამი მოწყობილობისთვის ერთდროულად.',
    price: 179, oldPrice: 199, rating: 4.7, reviewsCount: 118, stock: 19, isNew: true,
    specs: { power: '100 W', ports: '4 პორტი', wireless: false, fastCharge: true, color: 'შავი', compatibility: 'უნივერსალური', warranty: '24 თვე' },
    tags: ['gan', 'pd', '100w', 'დისპლეი'], created: '2026-07-19',
  },
  {
    id: 'ch-005', slug: 'samsung-45w-charger', name: 'Samsung 45W სწრაფი დამტენი',
    brand: 'Samsung', category: 'chargers',
    shortDescription: '45W Super Fast Charging 2.0',
    description: 'Samsung-ის ორიგინალი 45W დამტენი Galaxy S და Note სერიისთვის. Super Fast Charging 2.0 მხარდაჭერა კაბელთან ერთად.',
    price: 89, rating: 4.5, reviewsCount: 167, stock: 44,
    specs: { power: '45 W', ports: '1 პორტი', wireless: false, fastCharge: true, color: 'შავი', compatibility: 'Samsung', warranty: '12 თვე' },
    tags: ['pd', 'samsung', 'ორიგინალი'], created: '2025-09-30',
  },
  {
    id: 'ch-006', slug: 'belkin-boostcharge-wireless-15w', name: 'Belkin BoostCharge უსადენო დამტენი 15W',
    brand: 'Belkin', category: 'chargers',
    shortDescription: '15W უსადენო, Qi2 სტანდარტი',
    description: 'უსადენო დამტენი Qi2 სერტიფიკატით და 15W სიმძლავრით. სილიკონის ზედაპირი იცავს ტელეფონის ზურგს ნაკაწრებისგან.',
    price: 99, rating: 4.4, reviewsCount: 94, stock: 29,
    specs: { power: '15 W', ports: '1 პორტი', wireless: true, fastCharge: true, color: 'თეთრი', compatibility: 'უნივერსალური', warranty: '24 თვე' },
    tags: ['უსადენო', 'qi2', 'magsafe'], created: '2026-04-16',
  },
  {
    id: 'ch-007', slug: 'baseus-magsafe-wireless-15w', name: 'Baseus MagSafe უსადენო დამტენი 15W',
    brand: 'Baseus', category: 'chargers',
    shortDescription: '15W მაგნიტური, სამაგიდო სადგამი',
    description: 'მაგნიტური უსადენო დამტენი რეგულირებადი კუთხით — ტელეფონი დატენვისას ეკრანით თქვენკენ რჩება. იდეალურია სამუშაო მაგიდისთვის.',
    price: 79, oldPrice: 95, rating: 4.3, reviewsCount: 137, stock: 41,
    specs: { power: '15 W', ports: '1 პორტი', wireless: true, fastCharge: true, color: 'შავი', compatibility: 'iPhone', warranty: '12 თვე' },
    tags: ['უსადენო', 'magsafe', 'სადგამი'], created: '2026-05-11',
  },
  {
    id: 'ch-008', slug: 'hoco-20w-dual-charger', name: 'Hoco C80 20W ორპორტიანი დამტენი',
    brand: 'Hoco', category: 'chargers',
    shortDescription: '20W, USB-C + USB-A',
    description: 'კომპაქტური ორპორტიანი დამტენი, რომელიც ერთდროულად ტენავს ორ მოწყობილობას. USB-C პორტი მხარს უჭერს Power Delivery-ს.',
    price: 35, rating: 4.1, reviewsCount: 203, stock: 96,
    specs: { power: '20 W', ports: '2 პორტი', wireless: false, fastCharge: true, color: 'თეთრი', compatibility: 'უნივერსალური', warranty: '6 თვე' },
    tags: ['pd', 'ბიუჯეტური'], created: '2025-08-06',
  },
];

/* ========================================================================== */
/*  ყურსასმენები (10)                                                         */
/* ========================================================================== */

const headphones = [
  {
    id: 'hp-001', slug: 'apple-airpods-pro-2', name: 'Apple AirPods Pro 2 (USB-C)',
    brand: 'Apple', category: 'headphones',
    shortDescription: 'უსადენო TWS ყურსასმენი აქტიური ANC-ით',
    description: 'AirPods Pro 2 H2 ჩიპით — ორჯერ უკეთესი აქტიური ხმაურის შთანთქმა და ადაპტური აუდიო. უსადენო ყურსასმენი, რომელიც ავტომატურად ერთვება Apple-ის მოწყობილობებთან.',
    price: 649, oldPrice: 699, rating: 4.8, reviewsCount: 421, stock: 26, isFeatured: true,
    specs: { type: 'TWS', wireless: true, anc: true, playtime: '6 სთ', color: 'თეთრი', connector: 'USB-C', warranty: '12 თვე' },
    tags: ['უსადენო', 'wireless', 'anc', 'bluetooth', 'tws'], created: '2026-02-20',
  },
  {
    id: 'hp-002', slug: 'samsung-galaxy-buds2-pro', name: 'Samsung Galaxy Buds2 Pro',
    brand: 'Samsung', category: 'headphones',
    shortDescription: 'უსადენო TWS ყურსასმენი, 24bit Hi-Fi',
    description: 'Galaxy Buds2 Pro უსადენო ყურსასმენი 24bit Hi-Fi აუდიოთი და ინტელექტუალური ANC-ით. 360° აუდიო თავის მოძრაობის აღქმით.',
    price: 429, rating: 4.6, reviewsCount: 238, stock: 31,
    specs: { type: 'TWS', wireless: true, anc: true, playtime: '8 სთ', color: 'იისფერი', connector: 'USB-C', warranty: '12 თვე' },
    tags: ['უსადენო', 'wireless', 'anc', 'bluetooth', 'tws'], created: '2025-10-28',
  },
  {
    id: 'hp-003', slug: 'jbl-tune-520bt', name: 'JBL Tune 520BT',
    brand: 'JBL', category: 'headphones',
    shortDescription: 'უსადენო on-ear ყურსასმენი, 57 სთ',
    description: 'JBL Pure Bass ხმა და განსაცვიფრებელი 57 საათი მუშაობის დრო. დასაკეცი კონსტრუქცია და უსადენო Bluetooth 5.3 კავშირი.',
    price: 149, oldPrice: 179, rating: 4.4, reviewsCount: 356, stock: 48,
    specs: { type: 'On-ear', wireless: true, anc: false, playtime: '40 სთ', color: 'შავი', connector: 'USB-C', warranty: '12 თვე' },
    tags: ['უსადენო', 'wireless', 'bluetooth', 'on-ear'], created: '2025-12-03',
  },
  {
    id: 'hp-004', slug: 'sony-wh-1000xm5', name: 'Sony WH-1000XM5',
    brand: 'Sony', category: 'headphones',
    shortDescription: 'უსადენო over-ear ყურსასმენი, საუკეთესო ANC',
    description: 'Sony-ს ფლაგმანური უსადენო ყურსასმენი ინდუსტრიაში წამყვანი ხმაურის შთანთქმით. რვა მიკროფონი და ორი პროცესორი უზრუნველყოფს სრულ სიჩუმეს.',
    price: 899, rating: 4.9, reviewsCount: 187, stock: 14, isFeatured: true,
    specs: { type: 'Over-ear', wireless: true, anc: true, playtime: '30 სთ', color: 'შავი', connector: 'USB-C', warranty: '24 თვე' },
    tags: ['უსადენო', 'wireless', 'anc', 'bluetooth', 'over-ear', 'hi-res'], created: '2026-01-11',
  },
  {
    id: 'hp-005', slug: 'jbl-tune-flex', name: 'JBL Tune Flex',
    brand: 'JBL', category: 'headphones',
    shortDescription: 'უსადენო TWS ყურსასმენი, Smart ANC',
    description: 'JBL Tune Flex უსადენო ყურსასმენი ორი ტიპის ამბუშურით — ღია და დახურული. Smart Ambient რეჟიმი გარემოს ხმების მოსასმენად.',
    price: 199, rating: 4.3, reviewsCount: 174, stock: 39,
    specs: { type: 'TWS', wireless: true, anc: true, playtime: '8 სთ', color: 'თეთრი', connector: 'USB-C', warranty: '12 თვე' },
    tags: ['უსადენო', 'wireless', 'anc', 'bluetooth', 'tws'], created: '2025-11-21',
  },
  {
    id: 'hp-006', slug: 'xiaomi-redmi-buds-5', name: 'Xiaomi Redmi Buds 5',
    brand: 'Xiaomi', category: 'headphones',
    shortDescription: 'უსადენო TWS ყურსასმენი, 46 დბ ANC',
    description: 'Redmi Buds 5 გთავაზობთ 46 დბ აქტიურ ხმაურის შთანთქმას ხელმისაწვდომ ფასად. 12.4 მმ დინამიკები და 40 საათამდე მუშაობა ქეისთან ერთად.',
    price: 129, rating: 4.4, reviewsCount: 289, stock: 62, isNew: true,
    specs: { type: 'TWS', wireless: true, anc: true, playtime: '10 სთ', color: 'ლურჯი', connector: 'USB-C', warranty: '12 თვე' },
    tags: ['უსადენო', 'wireless', 'anc', 'bluetooth', 'tws', 'ბიუჯეტური'], created: '2026-06-08',
  },
  {
    id: 'hp-007', slug: 'sony-wf-c700n', name: 'Sony WF-C700N',
    brand: 'Sony', category: 'headphones',
    shortDescription: 'უსადენო TWS ყურსასმენი ANC-ით',
    description: 'კომპაქტური და მსუბუქი უსადენო ყურსასმენი Sony-ს ხმის ხარისხითა და აქტიური ხმაურის შთანთქმით. IPX4 დაცვა ვარჯიშისთვის.',
    price: 349, oldPrice: 399, rating: 4.5, reviewsCount: 143, stock: 22,
    specs: { type: 'TWS', wireless: true, anc: true, playtime: '8 სთ', color: 'ნაცრისფერი', connector: 'USB-C', warranty: '24 თვე' },
    tags: ['უსადენო', 'wireless', 'anc', 'bluetooth', 'tws'], created: '2026-03-27',
  },
  {
    id: 'hp-008', slug: 'anker-soundcore-life-q30', name: 'Anker Soundcore Life Q30',
    brand: 'Anker', category: 'headphones',
    shortDescription: 'უსადენო over-ear ყურსასმენი, 40 სთ',
    description: 'ჰიბრიდული აქტიური ხმაურის შთანთქმა სამი რეჟიმით და 40 საათი მუშაობა ერთი დატენვით. რბილი ამბუშურები ხანგრძლივი გამოყენებისთვის.',
    price: 259, rating: 4.6, reviewsCount: 312, stock: 27,
    specs: { type: 'Over-ear', wireless: true, anc: true, playtime: '40 სთ', color: 'ლურჯი', connector: 'USB-C', warranty: '18 თვე' },
    tags: ['უსადენო', 'wireless', 'anc', 'bluetooth', 'over-ear'], created: '2025-09-17',
  },
  {
    id: 'hp-009', slug: 'baseus-encok-h17', name: 'Baseus Encok H17 სადენიანი ყურსასმენი',
    brand: 'Baseus', category: 'headphones',
    shortDescription: 'სადენიანი in-ear ყურსასმენი, 3.5 მმ',
    description: 'მარტივი და საიმედო სადენიანი ყურსასმენი 3.5 მმ შტეკერით, ჩაშენებული მიკროფონითა და მართვის ღილაკით.',
    price: 25, rating: 4.0, reviewsCount: 198, stock: 140,
    specs: { type: 'In-ear', wireless: false, anc: false, color: 'შავი', connector: '3.5 მმ', warranty: '6 თვე' },
    tags: ['სადენიანი', 'in-ear', 'ბიუჯეტური'], created: '2025-06-18',
  },
  {
    id: 'hp-010', slug: 'jbl-tune-720bt', name: 'JBL Tune 720BT',
    brand: 'JBL', category: 'headphones',
    shortDescription: 'უსადენო over-ear ყურსასმენი, 76 სთ',
    description: 'JBL Pure Bass ხმა და 76 საათამდე მუშაობის დრო. უსადენო over-ear ყურსასმენი დასაკეცი კონსტრუქციითა და მრავალწერტილოვანი კავშირით.',
    price: 229, rating: 4.5, reviewsCount: 156, stock: 34, isNew: true,
    specs: { type: 'Over-ear', wireless: true, anc: false, playtime: '40 სთ', color: 'ლურჯი', connector: 'USB-C', warranty: '12 თვე' },
    tags: ['უსადენო', 'wireless', 'bluetooth', 'over-ear'], created: '2026-05-25',
  },
];

/* ========================================================================== */
/*  აქსესუარები (6)                                                           */
/* ========================================================================== */

const accessories = [
  {
    id: 'ac-001', slug: 'baseus-silicone-case-iphone-15', name: 'Baseus სილიკონის ქეისი iPhone 15',
    brand: 'Baseus', category: 'accessories',
    shortDescription: 'რბილი სილიკონი, MagSafe თავსებადი',
    description: 'რბილი სილიკონის ქეისი მიკროფიბრის შიდა საფარით. MagSafe მაგნიტების მხარდაჭერა და აწეული კიდეები კამერის დასაცავად.',
    price: 39, oldPrice: 49, rating: 4.4, reviewsCount: 187, stock: 74,
    specs: { type: 'ქეისი', material: 'სილიკონი', compatibility: 'iPhone', color: 'შავი', protection: 'დარტყმისგან', warranty: '6 თვე' },
    tags: ['ქეისი', 'magsafe', 'iphone'], created: '2026-01-16',
  },
  {
    id: 'ac-002', slug: 'baseus-tempered-glass-iphone-15', name: 'Baseus დამცავი მინა iPhone 15',
    brand: 'Baseus', category: 'accessories',
    shortDescription: '9H სიმაგრე, 2 ცალი კომპლექტში',
    description: 'დამცავი მინა 9H სიმაგრით და ოლეოფობური საფარით. კომპლექტში ორი ცალი და დასაწებებელი ჩარჩო ბუშტების გარეშე მოსარგებად.',
    price: 19, rating: 4.5, reviewsCount: 264, stock: 152,
    specs: { type: 'დამცავი მინა', material: 'მინა', compatibility: 'iPhone', color: 'გამჭვირვალე', protection: 'ნაკაწრებისგან', warranty: '3 თვე' },
    tags: ['მინა', 'iphone', 'დაცვა'], created: '2025-10-05',
  },
  {
    id: 'ac-003', slug: 'ugreen-car-mount', name: 'Ugreen ავტომობილის დამჭერი',
    brand: 'Ugreen', category: 'accessories',
    shortDescription: 'გრავიტაციული დამჭერი ვენტილაციაზე',
    description: 'გრავიტაციული მექანიზმი ტელეფონს ავტომატურად იჭერს ერთი ხელით მოთავსებისას. მყარი კლიპსა ვენტილაციის ცხაურზე და სილიკონის ბალიშები.',
    price: 45, rating: 4.3, reviewsCount: 156, stock: 63,
    specs: { type: 'დამჭერი', material: 'ლითონი', compatibility: 'უნივერსალური', color: 'შავი', protection: 'ანტისრიალი', warranty: '12 თვე' },
    tags: ['დამჭერი', 'ავტომობილი'], created: '2025-11-08',
  },
  {
    id: 'ac-004', slug: 'ugreen-usb-c-3-5mm-adapter', name: 'Ugreen USB-C — 3.5მმ ადაპტერი',
    brand: 'Ugreen', category: 'accessories',
    shortDescription: 'DAC ჩიპით, Hi-Fi ხარისხი',
    description: 'ადაპტერი ჩაშენებული DAC ჩიპით, რომელიც სადენიან ყურსასმენებს აერთებს USB-C პორტიან ტელეფონთან ხმის დანაკარგის გარეშე.',
    price: 25, rating: 4.4, reviewsCount: 211, stock: 108,
    specs: { type: 'ადაპტერი', material: 'პლასტიკი', compatibility: 'უნივერსალური', color: 'თეთრი', protection: 'არა', warranty: '12 თვე' },
    tags: ['ადაპტერი', 'usb-c', 'dac'], created: '2025-08-23',
  },
  {
    id: 'ac-005', slug: 'belkin-magsafe-stand', name: 'Belkin MagSafe სამაგიდო დამჭერი',
    brand: 'Belkin', category: 'accessories',
    shortDescription: 'მაგნიტური სადგამი, რეგულირებადი კუთხე',
    description: 'ალუმინის მაგნიტური სადგამი, რომელიც ტელეფონს მყარად იჭერს და კუთხის რეგულირების საშუალებას იძლევა. იდეალურია ვიდეო-ზარებისთვის.',
    price: 89, rating: 4.6, reviewsCount: 74, stock: 37, isNew: true,
    specs: { type: 'დამჭერი', material: 'ლითონი', compatibility: 'iPhone', color: 'თეთრი', protection: 'ანტისრიალი', warranty: '24 თვე' },
    tags: ['დამჭერი', 'magsafe', 'სადგამი'], created: '2026-08-19',
  },
  {
    id: 'ac-006', slug: 'baseus-laptop-sleeve-15', name: 'Baseus ლეპტოპის ჩანთა 15"',
    brand: 'Baseus', category: 'accessories',
    shortDescription: 'წყალგაუმტარი ნეილონი, 15 დიუიმი',
    description: 'წყალგაუმტარი ნეილონის ჩანთა რბილი შიდა საფარით. დამატებითი ჯიბე დამტენისა და კაბელებისთვის, გამაგრებული კიდეები.',
    price: 119, oldPrice: 139, rating: 4.5, reviewsCount: 98, stock: 41,
    specs: { type: 'ჩანთა', material: 'ნეილონი', compatibility: 'უნივერსალური', color: 'ნაცრისფერი', protection: 'წყლისგან', warranty: '12 თვე' },
    tags: ['ჩანთა', 'ლეპტოპი'], created: '2026-04-02',
  },
];

/* ========================================================================== */
/*  ექსპორტი                                                                  */
/* ========================================================================== */

/** @type {import('../types.js').Product[]} */
export const products = [
  ...phones,
  ...cables,
  ...powerbanks,
  ...chargers,
  ...headphones,
  ...accessories,
].map(make);

export default products;
