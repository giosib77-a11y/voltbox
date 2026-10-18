# Audit — VoltBox

- **თარიღი:** 2026-10-18
- **commit:** `10d933d` (branch `agent-system`)
- **სფერო:** მთელი პროექტი (backend, frontend, CI, კონფიგურაცია)
- **რეჟიმი:** trusted (code-reviewer, security-auditor, tester)
- **baseline (ყველა მწვანე):**
  - backend: `ruff check` ✅ · `ruff format --check` ✅ (161 ფაილი) · `mypy app scripts tests` ✅ (143 ფაილი) ·
    `pytest -q` ✅ **1017 passed** · `alembic upgrade head` + `alembic check` ლოკალურ ბაზაზე ✅ ·
    `pip-audit -r requirements.txt` ✅ (0)
  - frontend: `npm run lint` ✅ · `npm test` ✅ **580 tests / 46 files** · build `http` ✅ · build `mock` ✅ ·
    `npm audit --omit=dev --audit-level=high` ✅ (0)
  - არ გაშვებულა: e2e workflow, Docker image build და API surface შემოწმება, frontend-ის mock-data export job.
- **შედეგი:** 0 critical · 7 should-fix · 9 nit

PROJECT.md-ის Accepted Risks-ში და PROGRESS.md-ის Backlog-ში უკვე ჩაწერილი საკითხები აქ აღარ მეორდება.
Stage 1-ის გამოსწორებებში (T0–T17) რეგრესია ვერ ვიპოვეთ.

---

## Should-fix

### A-001 · should-fix · პაროლის შეცვლა და email-ის შეცვლა auth-ის ლიმიტის და lockout-ის გარეშეა
- **ფაილი:** `backend/app/api/v1/routes/auth.py:170-188`, `backend/app/services/auth.py:432-446`, `:574-583`
- **სცენარი:** `POST /auth/change-password`-სა და `PATCH /auth/me`-ს (email-ის შეცვლა) `@limiter.limit(AUTH_RATE_LIMIT)`
  არ აქვთ, ამიტომ მოქმედებს მხოლოდ ნაგულისხმევი 60/წთ. ორივე Argon2-ით ამოწმებს მიმდინარე პაროლს, მაგრამ
  `_record_failure`-ს არ იძახებს და `locked_until`-ს არ ამოწმებს. თავდამსხმელს აქვს ნაპარავი access token
  (localStorage, 30 წთ). ის `/change-password`-ით პაროლს არჩევს 60/წთ თითო IP-დან. login-ის lockout
  (10 ცდა / 15 წთ) აქ არ მოქმედებს. პაროლის გამოცნობისას ახალს აყენებს, `revoke_all` მსხვერპლის ყველა
  სესიას თიშავს და ანგარიში თავდამსხმელისაა.
  - ასევე: ნებისმიერი დარეგისტრირებული ანგარიში ერთი IP-დან 60 Argon2 hash-ს/წთ იწვევს. ისინი worker-ის
    `Semaphore(1)`-ის რიგში დგება (`core/security.py:71`), რაც ნამდვილ login-ს ანელებს.
- **შედეგი:** T6-ის დაცვა სუსტდება („token-ი მარტო არ კმარა ანგარიშის წასაღებად“). PROJECT.md-ის წესი
  „auth 5/min“ ირღვევა `/auth`-ის ორ route-ზე.
- **გამოსწორება:** ორივე route-ზე `@limiter.limit(AUTH_RATE_LIMIT)` + `request: Request`. მიმდინარე პაროლის
  შეცდომა ითვლება `_record_failure`-ით, დაბლოკილ ანგარიშზე პასუხი `TOO_MANY_LOGIN_ATTEMPTS`-ია (როგორც login-ში).
  ტესტები: მე-6 ცდა → 429; არასწორი მიმდინარე პაროლი N-ჯერ → lock.
- **owner:** backend-dev
- **status:** open

### A-002 · should-fix · ფასის ფილტრი კატეგორიის ყველაზე ძვირ პროდუქტს მალავს, როცა ფასი მთელი არ არის
- **ფაილი:** `backend/app/services/catalog.py:363-366`; `frontend/src/components/catalog/PriceRangeSlider.jsx:9-12,34-37`
- **სცენარი:** კატეგორიაში ყველაზე ძვირი 129.99 ₾-ია. facet აბრუნებს `max = int(129.99) = 129`, slider-ის
  ზედა ზღვარი 129 ხდება. მყიდველი მხოლოდ ქვედა ბიძგს ამოძრავებს 50-მდე. `commit()` აგზავნის `price=50-129`-ს,
  სერვერი ფილტრავს `price <= 129`-ით და 129.99-იანი პროდუქტი სიიდან ქრება. `current_max`-ზეც იგივე ხდება.
  mock (`utils/filter.js:215-218`) `Math.ceil`-ს იყენებს, ამიტომ mock-რეჟიმში და ტესტებში (მხოლოდ მთელი ფასები)
  ეს არ ჩანს.
- **შედეგი:** ჩვეულებრივი ფილტრი ჩუმად მალავს პროდუქტს.
- **გამოსწორება:** `min`/`current_min` → `math.floor`, `max`/`current_max` → `math.ceil` (Decimal-ზე).
  ტესტი: 129.99-იან პროდუქტზე `max == 130` და `price=50-130` მას აბრუნებს.
- **owner:** backend-dev
- **status:** open

### A-003 · should-fix · შესული მომხმარებლის კალათა ყოველ გვერდის ჩატვირთვაზე ერწყმის, ამიტომ ნაყიდი და წაშლილი ხაზები სხვა მოწყობილობიდან ბრუნდება
- **ფაილი:** `frontend/src/context/CartAccountSync.jsx:31-46`, `frontend/src/context/CartContext.jsx:233-241`,
  `backend/app/services/cart.py:177-178`
- **სცენარი:** `lastUserId` ref ყოველ ჩატვირთვაზე `null`-ით იწყება, ამიტომ `mergeWithAccount()` ყოველ reload-ზე
  ეშვება (არა მხოლოდ შესვლისას, როგორც კომპონენტის docstring ამბობს), და merge-ში „უფრო დიდი რაოდენობა იგებს“.
  ერთი ანგარიში, ტელეფონი და ლეპტოპი. ტელეფონზე შეკვეთა ფორმდება და `clear()` სერვერის კალათას ასუფთავებს.
  ლეპტოპის localStorage-ში ძველი ხაზები რჩება. ლეპტოპის შემდეგ ჩატვირთვაზე merge(ლოკალური, ცარიელი) მათ აბრუნებს
  და ინახავს, მერე ისინი ტელეფონზეც ჩნდება. ხელით წაშლილ ხაზებსა და შემცირებულ რაოდენობასაც იგივე ემართება
  (`max(1, 3) = 3`).
- **შედეგი:** უკვე ნაყიდი პროდუქტები კალათაში ბრუნდება. იმეორებს ზუსტად იმას, რისი თავიდან აცილებაც სურს
  `clear()`-ის კომენტარს; შესაძლებელია განმეორებითი შეკვეთა.
- **გამოსწორება:** merge მხოლოდ ნამდვილ შესვლაზე (login/register action). უკვე შესულის გვერდის ჩატვირთვაზე
  ანგარიშის კალათა იკითხება `GET /cart`-ით. ტესტი: ორი „მოწყობილობა“, წაშლა ან შეკვეთა ერთზე, მეორის reload.
- **owner:** frontend-dev
- **status:** open

### A-004 · should-fix · სტუმრის კალათის ფასი და მარაგი არასდროს ახლდება — checkout აჩვენებს ჯამს, რომელსაც სერვერი არ ჩამოჭრის
- **ფაილი:** `frontend/src/context/CartContext.jsx:118-130` (ADD არსებულ ხაზზე მხოლოდ `qty`), `frontend/src/pages/Checkout.jsx:385-413`,
  `frontend/src/pages/Cart.jsx`
- **სცენარი:** სტუმარი ორშაბათს კალათაში დებს 999 ₾-იან ტელეფონს (snapshot localStorage-შია). ადმინი ფასს
  1099-მდე ზრდის. ოთხშაბათს checkout ისევ 999-ს აჩვენებს. სერვერი (სწორად) 1099-იან შეკვეთას ქმნის და ახალ ჯამს
  მყიდველი მხოლოდ success გვერდზე ხედავს. მიწოდებაზეც იგივეა: 55 ₾ იყო („უფასო მიწოდება“), ფასი 45-მდე დაეცა
  და სერვერი 45 + 8-ს ითხოვს. reducer-ში snapshot-ის განახლების გზა არ არსებობს. დაარქივებული პროდუქტის შეცდომისას
  ხაზი არ მოინიშნება (`details.productId` არ გამოიყენება). შესულ მომხმარებელს merge-ის პასუხი snapshot-ს ახლებს.
- **შედეგი:** დადასტურების ეკრანზე ნაჩვენები ჯამი არ ემთხვევა ჩამოჭრილს. `delivery.py`-ის docstring პირობას დებს,
  რომ ესენი არ უნდა განსხვავდებოდეს. სტუმრის checkout მთავარი გზაა.
- **გამოსწორება:** Cart/Checkout-ის mount-ზე სტუმრის ხაზების ფასი და მარაგი განახლდეს სერვერიდან. შეიძლება
  საჯარო, rate limit-იანი `POST /cart/quote` იმავე `services/cart._resolve`-ით, ≤20 ხაზით, ან არსებული product
  endpoint-ები, თუ ერთი მოთხოვნით შეიძლება. გამქრალი ხაზი ამოიღება შეტყობინებით. ADD არსებულ ხაზზე snapshot-საც აახლებს.
- **owner:** frontend-dev (+ backend-dev, თუ ახალი endpoint)
- **status:** open

### A-005 · should-fix · პროფილის ცვლილება სესიაში არ იწერება — reload-ის შემდეგ ძველი მონაცემი ბრუნდება და შემდეგი შენახვა მას სერვერზე აბრუნებს
- **ფაილი:** `frontend/src/services/httpApi.js:221-223`, `frontend/src/context/AuthContext.jsx:19-23,58-62`,
  `frontend/src/pages/Account/Profile.jsx:34-47,82-88`
- **სცენარი:** http `updateProfile` `writeSession`-ს არ იძახებს (mock კი იძახებს, `mockApi.js:372`). reload-ზე
  user `auth:v1`-დან აღდგება.
  - (ა) სახელი „Gio“ → „Giorgi“ ინახება. reload (ან ენის გადართვა) და ფორმაში ისევ „Gio“-ა. მერე ტელეფონის
    შეცვლა ყველა ველს აგზავნის და სერვერზე სახელი ჩუმად „Gio“-ზე ბრუნდება.
  - (ბ) email A → B, reload, ფორმაში A-ა. `emailChanged` false-ია, ამიტომ პაროლის ველი დამალულია. ნებისმიერი
    შენახვა `email: A`-ს აგზავნის და სერვერი 400 `INVALID_CURRENT_PASSWORD`-ს პასუხობს, ანუ პროფილი არ ინახება
    ახალ შესვლამდე.
  - Checkout-ის ავტოშევსებაც ძველ ტელეფონს სვამს.
- **შედეგი:** მომხმარებლის მონაცემი ჩუმად ბრუნდება ძველზე, ან პროფილის შენახვა შეუძლებელი ხდება.
- **გამოსწორება:** წარმატებისას `writeSession({ ...readSession(), user: updated })`. ტესტი `httpApi.test.js`-ში.
- **owner:** frontend-dev
- **status:** open

### A-006 · should-fix · პაროლის შეცვლის შემდეგ UI „შესულად“ რჩება, თუმცა სესია უკვე გაუქმებულია
- **ფაილი:** `frontend/src/pages/Account/ChangePassword.jsx:44-51`, `frontend/src/context/AuthContext.jsx:64`;
  backend `services/auth.py:446` (`revoke_all`, განზრახ — `tests/test_auth.py:667`)
- **სცენარი:** პაროლი იცვლება და ჩანს „პაროლი შეიცვალა“. `auth:v1` რჩება, მაგრამ token_version გაიზარდა და
  refresh გაუქმდა. შემდეგი მოთხოვნა (კალათის debounce save, „ჩემი შეკვეთები“) იღებს 401-ს, refresh იღებს 401-ს და
  `session.js:186-189` login-ზე გადაჰყავს „სესიის ვადა ამოიწურა“-თ, მიზეზის ახსნის გარეშე. mock არაფერს აუქმებს,
  ამიტომ ტესტებში არ ჩანს.
- **შედეგი:** მომხმარებელი შემთხვევით მომენტში და გაუგებარი შეტყობინებით გამოდის სისტემიდან. ჩაუწერელი ცვლილება
  შეიძლება დაიკარგოს.
- **გამოსწორება:** უმარტივესი: წარმატებისას `clearSession()` + `setUser(null)` და ნავიგაცია login-ზე ტექსტით
  „პაროლი შეიცვალა — შედით ახლით“ (i18n ორივე ფაილში). ტესტი.
- **owner:** frontend-dev
- **status:** open

### A-007 · should-fix · ფონური მოთხოვნის 401 საჯარო გვერდიდან (მთავრის ჩათვლით) login-ზე გადაჰყავს
- **ფაილი:** `frontend/src/services/session.js:108-112,186-189`, `frontend/src/services/httpClient.js:209-215`,
  `frontend/src/context/CartAccountSync.jsx:44-45`
- **სცენარი:** მომხმარებელი, რომელიც 30 წუთზე მეტი ხნის წინ შევიდა (onrender-ზე refresh cookie ვერ გადადის),
  ხსნის მთავარ გვერდს. ჩატვირთვაზე `mergeCart` იღებს 401-ს, refresh ვერ ხერხდება და `defaultOnSessionLost` აკეთებს
  `window.location.assign('/login?redirect=/')`-ს. `setSessionLostHandler` აპში არსად არის override-ებული. ანუ
  კატალოგის დათვალიერებაც login-ით იწყება. voltbox.ge-ზეც იგივე მოხდება refresh-ის ვადის (30 დღე) გასვლის შემდეგ,
  ან სხვა მოწყობილობაზე პაროლის შეცვლის შემდეგ.
- **შედეგი:** Accepted Risk ამბობს „თავიდან შესვლა 30 წუთის შემდეგ“, არა „საჯარო გვერდი login-ზე გადამისამართებით
  იხსნება“. სტუმრად დათვალიერება იბლოკება.
- **გამოსწორება:** ფონური გამოძახების (cart merge/save) 401-ზე მხოლოდ `clearSession()` + `setUser(null)`,
  გადამისამართების გარეშე. გადამისამართება მხოლოდ დაცულ გვერდებზე (`RequireAuth`, admin): flag `request()`-ში ან
  `setSessionLostHandler`-ით. ტესტი: საჯარო გვერდზე ვადაგასული სესია → სტუმარი, გადამისამართება არ ხდება.
- **owner:** frontend-dev
- **status:** open

---

## Nit

### A-008 · nit · შესულის კალათის ხაზების რიგი ბაზის ფიზიკურ რიგს მიჰყვება
- **ფაილი:** `backend/app/services/cart.py:84-92` (`_resolve`, `ORDER BY` არ არის)
- **სცენარი / შედეგი:** ხაზები ყოველ ჩატვირთვაზე შეიძლება სხვა რიგით გამოჩნდეს და არა დამატების რიგით.
- **გამოსწორება:** შედეგი დალაგდეს `wanted`-ის რიგით.
- **owner:** backend-dev · **status:** open

### A-009 · nit · Idempotency-Key-ის signature-ში მომხმარებელი არ შედის → 409 სტუმრის ცდის შემდეგ შესვლისას
- **ფაილი:** `frontend/src/pages/Checkout.jsx:67-82`, `frontend/src/hooks/useIdempotencyKey.js`
- **სცენარი:** სტუმრის მცდელობა timeout-ით მთავრდება, თუმცა შეკვეთა სერვერზე შეიქმნა. სტუმარი შედის და იგივეს
  აგზავნის: იგივე გასაღები, `owns_order` false, პასუხი 409 `IDEMPOTENCY_KEY_CONFLICT`. გასაღები sessionStorage-შია,
  ამიტომ „refresh the page“ არ შველის.
- **გამოსწორება:** `user?.id` signature-ში, ან 409 conflict-ზე `resetIdempotencyKey()`.
- **owner:** frontend-dev · **status:** open

### A-010 · nit · ადმინის ფორმაში SKU-ს წაშლა შეუძლებელია
- **ფაილი:** `frontend/src/admin/pages/ProductForm.jsx:225`
- **სცენარი:** ცარიელი SKU payload-იდან ამოიღება, ამიტომ PATCH ძველს ტოვებს. backend `null`-ს იღებს (`normalize_sku`).
- **გამოსწორება:** რედაქტირებისას ცარიელ SKU-ზე `sku: null`-ის გაგზავნა.
- **owner:** frontend-dev · **status:** open

### A-011 · nit · `StockAdjustRequest.change` საზღვრის გარეშეა → 500
- **ფაილი:** `backend/app/schemas/admin_product.py:257`
- **სცენარი:** ადმინი შეცდომით კრეფს 3000000000-ს, int4 გადაივსება და პასუხი 500-ია, გასაგები შეტყობინების გარეშე.
- **გამოსწორება:** `Field(ge=-100_000, le=100_000)` (400 `VALIDATION_ERROR`).
- **owner:** backend-dev · **status:** open

### A-012 · nit · `services/order.cancel()` production-ში არ გამოიყენება
- **ფაილი:** `backend/app/services/order.py:448`
- **სცენარი / შედეგი:** მას იძახებს მხოლოდ `tests/test_inventory.py:136,159`; გაუქმება `order_status.transition`-ით
  ხდება. ზედმეტი კოდია, რომელიც ტესტებს მეორე გზით ამოწმებინებს.
- **გამოსწორება:** წაიშალოს და ტესტებმა `order_status.transition` გამოიძახონ.
- **owner:** backend-dev · **status:** open

### A-013 · nit · სტუმრის lookup token-ები localStorage-ში ვადის გარეშე გროვდება
- **ფაილი:** `frontend/src/services/httpApi.js:123-128,160-169`
- **სცენარი:** საერთო კომპიუტერზე შემდეგი მომხმარებელი წინა სტუმრის შეკვეთას ხსნის (სახელი, ტელეფონი, მისამართი).
- **გამოსწორება:** ჩანაწერს დაემატოს თარიღი და, მაგალითად, 30 დღის შემდეგ წაიშალოს.
- **owner:** frontend-dev · **status:** open

### A-014 · nit · storefront-ს `Strict-Transport-Security` header არ აქვს
- **ფაილი:** `frontend/render.yaml:75-127` (API-ს აქვს: `backend/app/core/headers.py:64`)
- **გამოსწორება:** დაემატოს voltbox.ge-ზე გადასვლისას; ჩაიწეროს PROGRESS.md-ის „Before going live“ სიაში.
- **owner:** frontend-dev · **status:** open

### A-015 · nit · `DB_SSL_MODE=require` შიფრავს, მაგრამ Supabase-ის სერტიფიკატს არ ამოწმებს
- **ფაილი:** `backend/app/db/ssl.py:43-46`
- **შენიშვნა:** უკვე წერია `docs/pre-deployment-checklist.md:159`-ში, PROGRESS.md-ის Backlog-ში კი არა.
- **გამოსწორება:** გაშვებამდე `DB_SSL_ROOT_CERT` + `verify-full`; ჩაიწეროს „Before going live“ სიაში.
- **owner:** backend-dev · **status:** open

### A-016 · nit · CLAUDE.md-ის ლოკალური migration ბრძანება `backend/.env`-ს ტვირთავს
- **ფაილი:** `CLAUDE.md:46` (root), `backend/README.md:28`
- **სცენარი:** `DATABASE_URL=... alembic upgrade head` `backend/`-იდან, `VOLTBOX_NO_DOTENV=1`-ის გარეშე, `Settings`-ს
  ცოცხალი `.env`-დან ტვირთავს (`JWT_SECRET`, Supabase/Telegram/Resend key-ები). ეს ეწინააღმდეგება იმავე ფაილის
  წესს („`backend/.env` არც ერთმა პროცესმა არ უნდა წაიკითხოს“). flag-ით კი ბრძანება `jwt_secret Field required`-ით
  ვარდება (tester-მა ორივე გადაამოწმა; გაიარა `VOLTBOX_NO_DOTENV=1 JWT_SECRET=<dummy>`-ით).
- **გამოსწორება:** ბრძანებაში `VOLTBOX_NO_DOTENV=1 JWT_SECRET=<dummy ≥32>`, როგორც CI-ში (`backend.yml:83`).
- **owner:** backend-dev · **status:** open

---

## შესამოწმებელი (დაუდასტურებელი)

- **Supabase Storage-ის policy-ები `product-images`-ზე.** repo-დან არ ჩანს, აქვს თუ არა anon/authenticated როლს
  INSERT/UPDATE/DELETE უფლება `storage.objects`-ზე. თუ აქვს, საჯარო anon key-ით პროდუქტის სურათების შეცვლა
  შეიძლება. შესამოწმებელია Dashboard → Storage → Policies-ში (მფლობელი).
- **Email-ის Unicode lower-case.** აღდგენის წერილი იგზავნება `payload.email`-ზე (Python `.lower()`), ანგარიში
  კი citext-ით (Postgres `lower()`) მოიძებნება. ისეთი სიმბოლო, რომელზეც ეს ორი განსხვავდება, ვერ ვიპოვეთ.
  გამაგრება: `issue_password_reset`-მა `RETURNING users.email` გამოიყენოს.
- **`ORDER_RATE_LIMIT` (5/წთ; 30/დღე, IP-ზე)** ითვლის 401→refresh→retry წყვილს და `INSUFFICIENT_STOCK`-ით
  უარყოფილ ცდებსაც. Georgian mobile CGNAT-ზე ბევრ მყიდველს ერთი IP აქვს. ამ მასშტაბზე სავარაუდოდ OK-ია, მაგრამ
  არ გაზომილა.
- **CI-ის ნაწილები, რომლებიც ლოკალურად არ გაშვებულა:** e2e (Playwright), Docker image build და API surface,
  frontend mock-data export და shape check.

## reviewer-ის მიგნებები, რომლებიც არ დადასტურდა — და რატომ

- **ტესტების `client` fixture ყველა მოთხოვნას ერთ session-ს აძლევს, rollback-ის გარეშე**
  (`tests/conftest.py:99-101`). ეს რისკი რეალურია (T1/T5 სწორედ ასე დაიმალა), მაგრამ ახლანდელ კოდში კონკრეტული
  დამალული ბაგი ვერ ვიპოვეთ. ამიტომ მიგნებად არ ჩაიწერა. commit/rollback-ზე დამოკიდებული ახალი ტესტები
  `test_orders_concurrency.py`-ის ნიმუშით უნდა დაიწეროს.
- **security-auditor-მა A-001 „სადავო should-fix“ უწოდა.** ის should-fix-ად დარჩა, რადგან PROJECT.md-ის
  „auth 5/min“ წესს არღვევს და T6-ის მიზანს ასუსტებს. ექსპლუატაციას კი ნაპარავი token სჭირდება, ამიტომ
  critical არ არის.
- **tester-ის warning-ები** („`VITE_SITE_URL` is not set“ ლოკალურ http build-ზე; vitest-ში „jsdom created 46 times“).
  პირველი ლოკალურად მოსალოდნელია: Render-ის build-ს ცვლადი `frontend/render.yaml`-იდან აქვს. მეორე სიჩქარის
  მინიშნებაა და შეცდომა არ არის.
