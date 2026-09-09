/**
 * პროდუქტების placeholder-სურათების გენერატორი.
 *
 * ქმნის `public/images/products/<id>-<n>.svg` ფაილებს — თითოეული პროდუქტისთვის
 * უნიკალური ფერითა და კატეგორიის შესაბამისი გრაფიკით. გარე სერვისზე
 * დამოკიდებულება არ არსებობს.
 *
 * გაშვება:  npm run gen:images
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { products } from '../src/data/products.js';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(here, '../public/images/products');

/* ---------------------------------------------------------------- ფერები -- */

function hashCode(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  return hash;
}

function palette(product, variant) {
  const hash = hashCode(product.id);
  const hue = (hash % 360 + variant * 12) % 360;
  return {
    bgFrom: `hsl(${hue} 34% 96%)`,
    bgTo: `hsl(${(hue + 28) % 360} 42% 88%)`,
    blob: `hsl(${(hue + 18) % 360} 60% 82%)`,
    body: `hsl(${hue} 22% 26%)`,
    bodyLight: `hsl(${hue} 20% 38%)`,
    screen: `hsl(${(hue + 200) % 360} 45% 62%)`,
    accent: `hsl(${(hue + 165) % 360} 72% 55%)`,
    line: `hsl(${hue} 18% 20%)`,
  };
}

/* --------------------------------------------------------------- გრაფიკა -- */

const glyphs = {
  phones: (c) => `
    <rect x="-105" y="-185" width="210" height="370" rx="30" fill="${c.body}"/>
    <rect x="-92" y="-172" width="184" height="344" rx="22" fill="${c.screen}"/>
    <rect x="-30" y="-166" width="60" height="14" rx="7" fill="${c.body}"/>
    <circle cx="-58" cy="-128" r="20" fill="${c.body}" opacity="0.55"/>
    <circle cx="-58" cy="-80" r="20" fill="${c.body}" opacity="0.4"/>
    <rect x="-60" y="118" width="120" height="10" rx="5" fill="${c.body}" opacity="0.5"/>`,
  cables: (c) => `
    <path d="M-190 -120 C -40 -120, -40 120, 110 120" fill="none" stroke="${c.body}" stroke-width="26" stroke-linecap="round"/>
    <rect x="-236" y="-152" width="66" height="64" rx="16" fill="${c.bodyLight}"/>
    <rect x="-222" y="-138" width="38" height="36" rx="10" fill="${c.accent}"/>
    <rect x="104" y="88" width="66" height="64" rx="16" fill="${c.bodyLight}"/>
    <rect x="118" y="102" width="38" height="36" rx="10" fill="${c.accent}"/>`,
  powerbanks: (c) => `
    <rect x="-150" y="-210" width="300" height="420" rx="34" fill="${c.body}"/>
    <rect x="-118" y="-176" width="236" height="150" rx="18" fill="${c.screen}" opacity="0.85"/>
    <g fill="${c.accent}">
      <rect x="-100" y="40" width="46" height="18" rx="9"/>
      <rect x="-38" y="40" width="46" height="18" rx="9"/>
      <rect x="24" y="40" width="46" height="18" rx="9"/>
    </g>
    <rect x="-60" y="120" width="120" height="40" rx="12" fill="${c.bodyLight}"/>`,
  chargers: (c) => `
    <rect x="-140" y="-140" width="280" height="280" rx="56" fill="${c.body}"/>
    <rect x="-70" y="-236" width="30" height="106" rx="12" fill="${c.bodyLight}"/>
    <rect x="40" y="-236" width="30" height="106" rx="12" fill="${c.bodyLight}"/>
    <rect x="-58" y="60" width="116" height="26" rx="13" fill="${c.accent}"/>
    <path d="M14 -74 L-42 6 h44 l-14 66 58 -84 h-46 z" fill="${c.accent}"/>`,
  headphones: (c) => `
    <path d="M-176 40 A176 176 0 0 1 176 40" fill="none" stroke="${c.body}" stroke-width="40" stroke-linecap="round"/>
    <rect x="-224" y="30" width="96" height="164" rx="42" fill="${c.body}"/>
    <rect x="128" y="30" width="96" height="164" rx="42" fill="${c.body}"/>
    <rect x="-206" y="52" width="60" height="120" rx="30" fill="${c.accent}" opacity="0.85"/>
    <rect x="146" y="52" width="60" height="120" rx="30" fill="${c.accent}" opacity="0.85"/>`,
  accessories: (c) => `
    <rect x="-160" y="-190" width="320" height="380" rx="46" fill="${c.body}"/>
    <rect x="-128" y="-158" width="256" height="316" rx="32" fill="${c.screen}" opacity="0.7"/>
    <circle cx="-58" cy="-96" r="30" fill="${c.body}"/>
    <circle cx="24" cy="-96" r="30" fill="${c.body}" opacity="0.7"/>
    <rect x="-70" y="66" width="140" height="16" rx="8" fill="${c.accent}"/>`,
};

/* ------------------------------------------------------------- ვარიანტები -- */

const variants = [
  { rotate: 0, scale: 1, blobX: 250, blobY: 200, blobR: 250 },
  { rotate: -14, scale: 0.92, blobX: 560, blobY: 600, blobR: 290 },
  { rotate: 9, scale: 1.08, blobX: 620, blobY: 180, blobR: 220 },
];

function buildSvg(product, variantIndex) {
  const c = palette(product, variantIndex);
  const v = variants[variantIndex % variants.length];
  const glyph = (glyphs[product.category] || glyphs.accessories)(c);
  const gradId = `g-${product.id}-${variantIndex}`;
  const label = `${product.brand} · ${product.name}`;

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800" role="img" aria-label="${escapeXml(label)}">
  <title>${escapeXml(label)}</title>
  <defs>
    <linearGradient id="${gradId}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${c.bgFrom}"/>
      <stop offset="1" stop-color="${c.bgTo}"/>
    </linearGradient>
  </defs>
  <rect width="800" height="800" fill="url(#${gradId})"/>
  <circle cx="${v.blobX}" cy="${v.blobY}" r="${v.blobR}" fill="${c.blob}" opacity="0.55"/>
  <g transform="translate(400 396) rotate(${v.rotate}) scale(${v.scale})">${glyph}
  </g>
  <g opacity="0.5">
    <rect x="286" y="700" width="228" height="34" rx="17" fill="${c.body}" opacity="0.08"/>
    <text x="400" y="723" text-anchor="middle" font-family="system-ui, sans-serif" font-size="20" font-weight="600" fill="${c.line}">${escapeXml(product.brand)}</text>
  </g>
</svg>
`;
}

function escapeXml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ------------------------------------------------------------------ გაშვება */

mkdirSync(outDir, { recursive: true });

let written = 0;
products.forEach((product) => {
  product.images.forEach((imagePath, index) => {
    const fileName = imagePath.split('/').pop();
    writeFileSync(resolve(outDir, fileName), buildSvg(product, index), 'utf8');
    written += 1;
  });
});

console.log(`✔ დაგენერირდა ${written} სურათი ${products.length} პროდუქტისთვის → public/images/products/`);
