import { useEffect, useId, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router';
import { ChevronDown, ChevronRight, LayoutGrid } from 'lucide-react';
import CategoryIcon from '../common/CategoryIcon.jsx';
import { useMediaQuery } from '../../hooks/useMediaQuery.js';
import { categoryTree } from '../../utils/categoryTree.js';

/**
 * კატეგორიების ვერტიკალური მენიუ (desktop, md+) — თითო ხაზი თითო ფესვზე, მისი
 * ქვეკატეგორიები სიის მარჯვნივ გამოსულ პანელში (flyout).
 *
 * იხსნება მაუსის hover-ზე და კლავიატურის focus-ზე, იხურება გასვლაზე და Escape-ზე.
 * მშობლის ბმული ყოველთვის მშობლის გვერდზე გადადის. ისრის ღილაკი მხოლოდ იქ ჩანს,
 * სადაც hover არ არის: ეკრანის სიგანე ამას ვერ გვეტყვის — md+ ტაბლეტზე ისრის
 * გარეშე პანელის გახსნა შეუძლებელი იქნებოდა, რადგან სახელზე შეხება გადადის.
 * თითით შეხება ბმულზე მხოლოდ გადადის — focus-ზე გახსნა მას არ ეხება, თორემ
 * ერთი შეხება ერთდროულად გახსნიდა და გადავიდოდა.
 *
 * მთავარ გვერდზე სია hero-ს გვერდითაა, სხვაგან — header-ის ღილაკის ქვეშ
 * (CategoryMenuButton). ორივე ერთი და იგივე კომპონენტია.
 */
export const CAN_HOVER = '(hover: hover) and (pointer: fine)';

/**
 * რამდენ ხანს უძლებს ღია პანელი მაუსს, რომელიც მისკენ მიდის. მარჯვნივ
 * დიაგონალით სვლისას მაუსი მეზობელ ხაზს კვეთს — ეს დრო საკმარისია, რომ პანელამდე
 * მიაღწიოს და გადართვა გაუქმდეს.
 */
export const AIM_MS = 300;

export default function CategoryNav({ categories, className = '' }) {
  // media query და არა CSS კლასი: ისრის არყოფნაზე aria და Escape-ის focus-იც
  // იცვლება, ამიტომ ერთი წყარო JS-ში უნდა იყოს
  const canHover = useMediaQuery(CAN_HOVER);
  // ერთ დროს ერთი პანელი: ღიაობა სიის დონეზეა და არა ხაზისა
  const [activeId, setActiveId] = useState(null);
  const navRef = useRef(null);
  const timer = useRef(null);
  const lastX = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  // პანელი ქრება — თუ focus მასში იყო, ბრუნდება იმ კონტროლზე, რომელიც პანელს
  // ფლობს (aria-controls): ისარზე, ისრის გარეშე კი ბმულზე, და არა body-ზე. რიგი
  // მნიშვნელოვანია: ბმულის onFocus პანელს ხსნის, და იმავე batch-ში ბოლო
  // setActiveId(null) იგებს
  function close() {
    clearTimeout(timer.current);
    const panel = document.activeElement?.closest('[data-flyout]');
    if (panel && navRef.current?.contains(panel)) {
      [...navRef.current.querySelectorAll('[aria-controls]')]
        .find((control) => control.getAttribute('aria-controls') === panel.id)
        ?.focus();
    }
    setActiveId(null);
  }

  // მაუსი ხაზზე შევიდა. პანელი თუ არ არის ღია, ან მაუსი მარჯვნივ არ მიდის,
  // გადართვა მყისიერია. მარჯვნივ მიმავალი მაუსი კი, სავარაუდოდ, ღია პანელისკენ
  // მიდის და ამ ხაზს გზად კვეთს — გადართვა AIM_MS-ით გადაიდება, და პანელში შესვლა
  // (ის DOM-ში თავისი ხაზის შვილია) მას გააუქმებს
  function enter(event, id) {
    if (event.pointerType === 'touch') return;
    clearTimeout(timer.current);
    if (activeId === id) return;
    const aiming = lastX.current !== null && event.clientX > lastX.current;
    if (activeId === null || !aiming) setActiveId(id);
    else timer.current = setTimeout(() => setActiveId(id), AIM_MS);
  }

  // გასვლა იგივე დროს ელოდება: მაუსი, რომელიც კიდეს ცოტათი გასცდა, პანელს არ ხურავს
  function leave(event) {
    if (event.pointerType === 'touch') return;
    clearTimeout(timer.current);
    timer.current = setTimeout(close, AIM_MS);
  }

  const aim = { enter, leave };

  return (
    <nav
      ref={navRef}
      aria-label="კატეგორიები"
      className={`relative ${className}`}
      onPointerMove={(event) => {
        lastX.current = event.clientX;
      }}
    >
      <ul className="py-1.5">
        {categoryTree(categories).map((category) => (
          <CategoryNavItem
            key={category.id}
            category={category}
            canHover={canHover}
            open={activeId === category.id}
            setActiveId={setActiveId}
            close={close}
            aim={aim}
          />
        ))}
      </ul>
    </nav>
  );
}

function rowClass({ isActive }, open) {
  return `flex min-w-0 flex-1 items-center gap-3 px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-primary-50 text-primary-800'
      : open
        ? 'bg-ink-100 text-fg'
        : 'text-ink-700 hover:bg-ink-100 hover:text-fg'
  }`;
}

function RowLabel({ category }) {
  return (
    <>
      <CategoryIcon name={category.icon} className="h-5 w-5 shrink-0 text-primary-700" />
      <span className="truncate">{category.name}</span>
    </>
  );
}

function CategoryNavItem({ category, canHover, open, setActiveId, close, aim }) {
  const pointerPressed = useRef(false);
  const panelId = useId();

  const id = category.id;
  const setOpen = (value) =>
    setActiveId((active) => (value ? id : active === id ? null : active));

  if (category.children.length === 0) {
    // ფოთოლს პანელი არ აქვს — მასზე გადასვლა სხვის პანელს ხურავს
    return (
      <li onPointerEnter={(event) => aim.enter(event, null)}>
        <NavLink to={`/category/${category.slug}`} className={(state) => rowClass(state, false)}>
          <RowLabel category={category} />
        </NavLink>
      </li>
    );
  }

  // ისრის გარეშე მდგომარეობას ბმული აცხადებს — ეკრანის წამკითხველმა უნდა იცოდეს
  const disclosure = { 'aria-expanded': open, 'aria-controls': panelId };

  return (
    <li
      className="flex items-center"
      onPointerEnter={(event) => aim.enter(event, id)}
      onPointerLeave={(event) => aim.leave(event)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          // header-ის ჩამოსაშლელი მეორე Escape-ზე იხურება, არა ამავეზე
          event.stopPropagation();
          close();
        }
      }}
    >
      <NavLink
        to={`/category/${category.slug}`}
        className={(state) => rowClass(state, open)}
        {...(canHover ? disclosure : {})}
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
        <RowLabel category={category} />
      </NavLink>
      {!canHover && (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          {...disclosure}
          aria-label={`${category.name} — ქვეკატეგორიები`}
          className={`flex w-9 items-center justify-center self-stretch transition-colors hover:bg-ink-100 hover:text-fg ${
            open ? 'bg-ink-100 text-fg' : 'text-fg-muted'
          }`}
        >
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      )}

      {/* disclosure და არა ARIA menu: ისრებით ნავიგაცია არ გვაქვს, ამიტომ aria-haspopup
          არ ადევს. პანელი ყოველთვის DOM-შია, `hidden`-ით — aria-controls-ის სამიზნე
          დახურულზეც არსებობს, დამალული ბმულები კი Tab-ით მიუწვდომელია.
          პოზიცია nav-ის მიმართ (li არ არის relative): სიის მარჯვნივ, მთელ სიმაღლეზე,
          ასე რომ სიის მარჯვნივ მიმავალი მაუსი აუცილებლად პანელს ხვდება.
          pl-2 და არა ml-2: ღრიჭო პანელის ნაწილია, pointer ხაზს არ ტოვებს.
          `flex` მხოლოდ ღიაზე — display-ის კლასი `hidden` ატრიბუტს გადაფარავდა */}
      <div
        id={panelId}
        data-flyout
        hidden={!open}
        className={`absolute left-full top-0 z-drawer min-h-full pl-2 ${open ? 'flex' : ''}`}
      >
        <div className="w-64 rounded-card border border-line bg-surface py-2 shadow-popover">
          <p className="px-4 pb-1.5 pt-1 text-sm font-semibold text-fg">{category.name}</p>
          <ul>
            {category.children.map((child) => (
              <li key={child.id}>
                <NavLink
                  to={`/category/${child.slug}`}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    `block px-4 py-2 text-sm transition-colors ${
                      isActive ? 'bg-primary-50 text-primary-800' : 'text-ink-700 hover:bg-ink-100 hover:text-fg'
                    }`
                  }
                >
                  {child.name}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </li>
  );
}

/**
 * „კატეგორიები“ ღილაკი header-ში (ყველა გვერდზე, მთავრის გარდა) — იმავე
 * ვერტიკალურ მენიუს ჩამოსაშლელად ხსნის.
 *
 * მხოლოდ დაწკაპუნებით და არა hover-ზე: ღილაკი ლოგოსა და ძებნას შორისაა, და
 * მაუსი ძებნისკენ გზაში ყოველ ჯერზე გვერდს პანელით დაფარავდა. იხურება Escape-ზე
 * (focus ღილაკზე ბრუნდება), გარეთ დაწკაპუნებაზე, focus-ის გასვლაზე და გადასვლაზე.
 */
export function CategoryMenuButton({ categories }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const panelId = useId();
  const { pathname } = useLocation();

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return undefined;
    function onPointerDown(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  return (
    <div
      ref={rootRef}
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          buttonRef.current?.focus();
          setOpen(false);
        }
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={panelId}
        className={`flex h-10 items-center gap-2 rounded-control border px-3 text-sm font-semibold transition-colors ${
          open
            ? 'border-primary-600 bg-primary-600 text-white'
            : 'border-line bg-surface text-ink-800 hover:bg-ink-100'
        }`}
      >
        <LayoutGrid className="h-4 w-4" aria-hidden="true" />
        კატეგორიები
        <ChevronDown
          className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {/* ბმულზე დაწკაპუნება იმავე გვერდზეც ხურავს — pathname მაშინ არ იცვლება */}
      <div
        id={panelId}
        hidden={!open}
        className="absolute left-0 top-full z-drawer pt-2"
        onClick={(event) => {
          if (event.target.closest('a')) setOpen(false);
        }}
      >
        <CategoryNav
          categories={categories}
          className="w-64 rounded-card border border-line bg-surface shadow-popover"
        />
      </div>
    </div>
  );
}
