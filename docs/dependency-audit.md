# Dependency audit

გაშვებულია **2026-09-12**: `npm audit` (frontend) და `pip-audit` (backend).

⚠️ `npm audit fix --force` ამ პროექტში **აკრძალულია** — ის major ვერსიებს ჩუმად
ცვლის. ქვემოთ თითოეული გაფრთხილება ცალკეა შეფასებული.

---

## Frontend — 8 გაფრთხილება

### 7 მათგანი მხოლოდ dev-ია

| პაკეტი | სიმძიმე | რა |
|---|---|---|
| `vitest`, `@vitest/coverage-v8`, `@vitest/mocker` | critical / moderate | ტესტის ხელსაწყო |
| `vite`, `vite-node`, `esbuild` | high / moderate | dev-სერვერი და ბილდი |

**production-ში არცერთი არ ხვდება** — `dependencies`-ში მხოლოდ react,
react-dom, react-router-dom და lucide-react-ია.

ამათგან ყველაზე რეალური `esbuild`-ისა და `vite`-ის **dev-სერვერის** ხარვეზებია:
გაშვებულ `npm run dev`-ს მავნე საიტს შეუძლია მოთხოვნა გაუგზავნოს და პასუხი
წაიკითხოს. ეს ლოკალურ მანქანას ეხება, არა მომხმარებლებს.

**გადაწყვეტილება:** არ ვასწორებთ ახლა. გასწორება `vite 5→7` და `vitest 2→4`
major-ებს ნიშნავს — ცალკე სამუშაოა, ცალკე ტესტირებით (იხ. ROADMAP §18).

### 1 ეხება production-ს — `react-router-dom` 6.30.x

ორი პრობლემა, `6.0.0 – 7.17.0`. გასწორება მხოლოდ **7.x major**-შია.

**ა) `deserializeErrors()` SSR hydration-ში** — ჩვენ SSR არ გვაქვს. არ გვეხება.

**ბ) Open redirect backslash-ით (CVE-2025-68470 bypass)** — `<Link>`-სა და
`useNavigate`-ში backslash-ის ზოგი ფორმა protocol-relative URL-ად იკითხება.

გვეხება? სამი ადგილი კითხულობს მომხმარებლის შეყვანას:

```
src/pages/Login.jsx          ?redirect=
src/pages/Register.jsx       ?redirect=
src/admin/pages/AdminLogin.jsx  ?next=
```

**სამივე `getSafeRedirect`-ზე გადის**, რომელიც აბრუნებს **უკვე გახსნილ**
`pathname + search + hash`-ს იმავე origin-იდან. ანუ `navigate()`-მდე backslash
ან ორმაგი სლეში ვერ აღწევს.

**გადაწყვეტილება:** major განახლება გადადებულია. ეს ვარაუდი არ არის —
`src/utils/redirect.test.js`-ში ცალკე ბლოკია ამ advisory-ზე, ათი payload-ით.
დაცვის დასუსტებაზე ისინი ჩავარდებიან.

⚠️ **თუ ოდესმე `navigate()`-ს ან `<Link to={...}>`-ს გარედან მოსული მნიშვნელობა
`getSafeRedirect`-ის გარეშე მისცემ — ეს შეფასება ძალას კარგავს.**

---

## Backend — სუფთაა ✅

```
pip-audit  →  No known vulnerabilities found
```

(`voltbox-backend` თვითონ გამოტოვებულია — ის PyPI-ზე არ დევს, რაც სწორია.)

დამოკიდებულებები შედარებით ცოტაა და ყველა ფართოდ გამოყენებადი:
fastapi, uvicorn, gunicorn, sqlalchemy, asyncpg, alembic, pydantic, pyjwt,
argon2-cffi, slowapi, redis, orjson, pillow, python-multipart, httpx, tzdata.

`pillow` ცალკე აღსანიშნავია — ატვირთული სურათები **ნამდვილად იხსნება**
ვალიდაციისთვის, ანუ მისი ხარვეზები პირდაპირ გვეხება. `MAX_IMAGE_BYTES` და
`MAX_IMAGE_DECODE_BYTES` სწორედ ამიტომ არსებობს.

⚠️ `pillow`-ის ვერსიის აწევისას: `storage.py`-ის `DECODE_COST` გაზომილი
რიცხვებია, და დეკოდერის ცვლილება მათ ჩუმად გააძვირებს. ამას
`TestDecodeMemoryIsBounded` იჭერს — ის ყოველ ფორმატის ყველაზე დიდ მიღებულ
სურათს ცალკე პროცესში შლის და პიკს ბიუჯეტს ადარებს.

---

## როდის გავიმეოროთ

- ყოველი `npm install`-ის ან `pip install`-ის შემდეგ
- გაშვებამდე აუცილებლად, ხელახლა
- მერე — თვეში ერთხელ

```bash
cd frontend && npm audit
cd backend && .venv/Scripts/python.exe -m pip_audit
```
