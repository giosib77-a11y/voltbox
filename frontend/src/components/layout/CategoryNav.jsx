import { useId, useRef, useState } from 'react';
import { NavLink } from 'react-router';
import { ChevronDown } from 'lucide-react';
import { categoryTree } from '../../utils/categoryTree.js';

/**
 * კატეგორიების ნავიგაცია (desktop, md+) — ფესვები, ქვეკატეგორიები ჩამოსაშლელში.
 *
 * იხსნება მაუსის hover-ზე და კლავიატურის focus-ზე, იხურება გასვლაზე და Escape-ზე.
 * მშობლის ბმული ყოველთვის მშობლის გვერდზე გადადის; ჩამოსაშლელს ცალკე ღილაკიც
 * აქვს, რადგან md+ ეკრანი ტაბლეტიც შეიძლება იყოს, სადაც hover არ არსებობს.
 * თითით შეხება ბმულზე მხოლოდ გადადის — focus-ზე გახსნა მას არ ეხება, თორემ
 * ერთი შეხება ერთდროულად გახსნიდა და გადავიდოდა.
 */
export default function CategoryNav({ categories }) {
  return (
    <nav aria-label="კატეგორიები" className="hidden border-t border-ink-100 md:block">
      {/* flex-wrap და არა overflow-x-auto: გადახვევადი კონტეინერი ჩამოსაშლელს მოჭრიდა */}
      <ul className="flex flex-wrap items-center gap-1 py-1.5">
        {categoryTree(categories).map((category) => (
          <CategoryNavItem key={category.id} category={category} />
        ))}
      </ul>
    </nav>
  );
}

function linkClass({ isActive }) {
  return `block whitespace-nowrap rounded-control px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? 'bg-primary-50 text-primary-700' : 'text-ink-700 hover:bg-ink-100 hover:text-primary-700'
  }`;
}

function CategoryNavItem({ category }) {
  const [open, setOpen] = useState(false);
  const pointerPressed = useRef(false);
  const toggleRef = useRef(null);
  const panelRef = useRef(null);
  const panelId = useId();

  if (category.children.length === 0) {
    return (
      <li>
        <NavLink to={`/category/${category.slug}`} className={linkClass}>
          {category.name}
        </NavLink>
      </li>
    );
  }

  // ჩამოსაშლელი ქრება — თუ focus მასში იყო, ღილაკზე გადადის და არა body-ზე
  function close() {
    if (panelRef.current?.contains(document.activeElement)) toggleRef.current?.focus();
    setOpen(false);
  }

  const isHover = (event) => event.pointerType !== 'touch';

  return (
    <li
      className="relative flex items-center"
      onPointerEnter={(event) => isHover(event) && setOpen(true)}
      onPointerLeave={(event) => isHover(event) && close()}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) close();
      }}
    >
      <NavLink
        to={`/category/${category.slug}`}
        className={(state) => `${linkClass(state)} pr-1`}
        onPointerDown={() => {
          pointerPressed.current = true;
        }}
        onFocus={() => {
          if (!pointerPressed.current) setOpen(true);
          pointerPressed.current = false;
        }}
        onBlur={() => {
          pointerPressed.current = false;
        }}
        onClick={() => setOpen(false)}
      >
        {category.name}
      </NavLink>
      <button
        ref={toggleRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`${category.name} — ქვეკატეგორიები`}
        className="flex h-9 w-7 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100 hover:text-primary-700"
      >
        <ChevronDown
          className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {/* disclosure და არა ARIA menu: ისრებით ნავიგაცია არ გვაქვს, ამიტომ aria-haspopup
          არ ადევს. პანელი ყოველთვის DOM-შია, `hidden`-ით — aria-controls-ის სამიზნე
          დახურულზეც არსებობს, დამალული ბმულები კი Tab-ით მიუწვდომელია.
          pt-1 და არა mt-1: ღრიჭოზე გადასვლისას pointer <li>-ში რჩება და მენიუ არ იხურება */}
      <div
        ref={panelRef}
        id={panelId}
        hidden={!open}
        className="absolute left-0 top-full z-drawer pt-1"
      >
        <ul className="w-56 overflow-hidden rounded-card border border-ink-200 bg-white py-1.5 shadow-popover">
          {category.children.map((child) => (
            <li key={child.id}>
              <NavLink
                to={`/category/${child.slug}`}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `block px-3 py-2 text-sm transition-colors ${
                    isActive ? 'bg-primary-50 text-primary-700' : 'text-ink-700 hover:bg-ink-50'
                  }`
                }
              >
                {child.name}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </li>
  );
}
