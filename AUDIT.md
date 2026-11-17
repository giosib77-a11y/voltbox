# Audit — VoltBox

- **თარიღი:** 2026-10-22
- **commit:** `65dc3db` (branch `agent-system`)
- **სფერო:** მთელი პროექტი. აქცენტი იმაზეა, რაც წინა აუდიტის (`10d933d`, 2026-10-18) შემდეგ შეიცვალა (61 commit):
  - წინა აუდიტის გასწორებები (A-001–A-026);
  - Stage 2 — შეკვეთების სანაგვე (migration 0016, `services/order_trash.py`, admin routes და გვერდები);
  - Stage 3 — storefront-ის რედიზაინი (მხოლოდ frontend).
- **რეჟიმი:** trusted (code-reviewer, security-auditor, tester)
- **baseline:**
  - backend:
    - `ruff check` ✅; `ruff format --check` ✅ (167 ფაილი); `mypy app scripts tests` ✅ (148 ფაილი)
    - `pytest -q` ✅ **1097 passed**
    - `alembic upgrade head` (0001→0016) + `alembic check` ✅, ლოკალურ scratch ბაზაზე
    - **`pip-audit --strict --disable-pip`** სამივე lock-ზე (CI-ის ნაკრები) ❌ **25 სისუსტე, exit 1** → A-001
  - frontend:
    - `npm run lint` ✅; `npm test` ✅ **672 tests / 57 files**
    - build `http` ✅; build `mock` ✅
    - `npm audit --omit=dev --audit-level=high` ✅ (0)
  - არ გაშვებულა:
    - e2e workflow, Docker image build და API surface check, frontend mock-data export;
    - CI-ის `pip install --require-hashes` + `pip check`;
    - frontend Node 22 / npm 10-ზე (ლოკალურად Node 24 / npm 11-ია).
- **შედეგი:** 0 critical · 1 should-fix · 19 nit
  - nit-ებიდან 2 ახალია (A-002, A-003);
  - 17 წინა აუდიტის ღია nit-ია, რომლებიც ახლანდელ კოდში ისევ ძალაშია (A-004–A-020). მათ ახალი ID მიიღეს, ძველი ID ფრჩხილებშია.

**`/fix A-001` 2026-10-22** (ბრენჩი `fix/pillow-certifi`):
- A-001 — fixed (verified), `fc5b3e3`. ახალი ტესტები ძველ კოდზე ვარდებოდა; მიზნობრივმა re-review-მ (security-auditor) A-001 დახურულად ჩათვალა და ოთხი ახალი nit იპოვა (A-021–A-024). ღია: მხოლოდ nit-ები.
- საბოლოო შემოწმება (`fc5b3e3`, tester):
  - backend: ruff ✅ · format 167 ✅ · mypy 148 ✅ · **pytest 1106** (baseline 1097, +9) · alembic 0001→0016 + check ✅ · **pip-audit (CI-ის ფორმა) 0** (baseline 25, exit 1) · `docker build` ✅;
  - frontend (უცვლელი): lint ✅ · vitest 672 / 57 · build http ✅ · build mock ✅ · npm audit 0.

PROJECT.md-ის Accepted Risks-ში და PROGRESS.md-ის Backlog-ში ჩაწერილი საკითხები აქ აღარ მეორდება.
შეკვეთების სანაგვესა (Stage 2) და რედიზაინში (Stage 3) critical ან should-fix ვერ ვიპოვეთ. წინა აუდიტის გასწორებებში რეგრესია არ ჩანს. რა შემოწმდა, წერია ბოლოს.

---

## Should-fix

### A-001 · should-fix · backend-ის lock-ებში ცნობილი სისუსტეებია (Pillow 12.3.0, certifi 2026.7.22) — CI-ის `pip-audit` წითელია
- **ფაილი:** `backend/requirements.txt:590` (`pillow==12.3.0`), `:132` (`certifi==2026.7.22`); `backend/requirements-dev.txt:913`, `:204`;
  `backend/app/services/storage.py:186`, `:280`; `.github/workflows/backend.yml:142-149`
- **სცენარი:**
  - `pip-audit` lock-ებში 25 სისუსტეს პოულობს:
    - **certifi** — PYSEC-2026-4320 (ნაკრებშია CA, რომლის intermediate-ების key-ები კომპრომეტირებულია), fix 2026.10.19;
    - **Pillow** — 24 CVE (GIF, TIFF, EPS, MIC, XBM, PPM, MSP, IPTC, PDF და PNG-ის ნაწილის parser-ები), fix 13.0.0.
  - `backend.yml`-ის audit step-ი `--strict`-ით ეშვება და კომენტარის მიხედვით „any finding fails“. ამიტომ backend-ის შემდეგი push ან PR CI-ს გააწითლებს. ეს ჩვეულებრივ მუშაობაში ჩნდება: ლოკალურად გაშვებულმა იმავე ბრძანებამ exit 1 დააბრუნა.
  - Pillow-ის რისკს ამძაფრებს კოდიც. `storage.py:186` და `:280` იძახებენ `Image.open(io.BytesIO(data))`-ს `formats=`-ის გარეშე. ამიტომ ატვირთული ფაილის header-ს ყველა Pillow parser არჩევს `ALLOWED_FORMATS`-ის (`:27`) შემოწმებამდე. ადმინის (ან ადმინის მოპარული token-ის) ატვირთული ბოროტი GIF/TIFF ამ parser-ებამდე აღწევს.
- **შედეგი:**
  - CI წითელია;
  - production image-ი სურათის ატვირთვის გზაზე ცნობილ სისუსტეებს ატარებს;
  - გამავალი TLS (Supabase Storage service-role key-ით, Telegram, Resend) ენდობა CA-ს, რომელსაც ნდობა აღარ ეკუთვნის.
  - critical არ არის: Pillow-ის ექსპლუატაციას ადმინის ანგარიში სჭირდება, certifi-ისას — ქსელში პოზიცია და კომპრომეტირებული key.
- **გამოსწორება:**
  1. `certifi` → 2026.10.19 და `pillow` → 13.0.0 ორივე lock-ში (`requirements.txt`, `requirements-dev.txt`; `requirements-build.txt` მათ არ შეიცავს). განახლება Linux container-ში, `--upgrade-package`-ით (`backend/README.md`, „დამოკიდებულებების lock“). Pillow 13 major ვერსიაა: `DECODE_COST`-ის ცხრილი (`storage.py:89`) 12.3-ზეა გაზომილი, ამიტომ თავიდან უნდა გაიზომოს. შემდეგ უნდა გაიაროს `test_admin_images.py`-მ, image build-მა და `pip check`-მა.
  2. ვერსიისგან დამოუკიდებელი გამაგრება: ორივე `Image.open`-ში `formats=list(ALLOWED_FORMATS)`. ამის შემდეგ GIF/TIFF `UNSUPPORTED_IMAGE_FORMAT`-ის ნაცვლად შეიძლება `INVALID_IMAGE` გახდეს — უნდა გადაიხედოს ტესტები, რომლებიც ამ კოდს ამოწმებენ (`grep -rn UNSUPPORTED_IMAGE_FORMAT backend/tests`, 4 ადგილი). ადმინისთვის საჭირო შეტყობინება უნდა დარჩეს.
  3. თუ Pillow 13 მაშინვე ვერ ჯდება: certifi მაინც განახლდეს, Pillow-ის ID-ებს კი დაემატოს `--ignore-vuln` მიზეზითა და ვადით (როგორც `backend.yml:139` ითხოვს), (2)-ის გამაგრებასთან ერთად.
- **owner:** backend-dev
- **status:** fixed (verified) — `fc5b3e3`. რა გაკეთდა:
  - lock-ები Linux container-ში თავიდან დაგენერირდა `--upgrade-package`-ით. შეიცვალა მხოლოდ certifi (→ 2026.10.19) და pillow (→ 13.0.0); `requirements-build.txt` უცვლელია; `pyproject.toml`-ში `pillow>=13.0`.
  - ორივე `Image.open` იხსნება `formats=`-ით. სხვა ფორმატი (GIF, TIFF, ...) plugin-ის `accept()`-ით ცნობილდება, parser-ის გამოძახების გარეშე, და ისევ `UNSUPPORTED_IMAGE_FORMAT`-ს იღებს.

  მტკიცებულება:
  - **pip-audit (CI-ის ფორმა):** 0, exit 0 — orchestrator-მა და tester-მა ცალ-ცალკე გაუშვეს.
  - **ტესტები:** `test_a_format_we_do_not_accept_is_never_parsed[GIF|TIFF|BMP|PPM|EPS]` და `test_shrink_to_fit_opens_only_the_format_it_was_validated_as` ძველ `storage.py`-ზე ვარდებოდა (6 failed; orchestrator-მაც გაუშვა).
  - **Linux-ზე, ახალი lock-ით (CI-ის base image):** pytest 1106, `pip check` სუფთაა, `TestDecodeMemoryIsBounded` მწვანეა. Peak-ები 13.0.0-ზე 90.2–91.1 MiB-ია, 12.3-ზე 90.4–91.4. ამიტომ `DECODE_COST` უცვლელია.
  - **re-review (security-auditor):** დახურულია; იპოვა A-021–A-024.

---

## Nit

### A-002 · nit · deadlock-ის ტესტი ცვლილების მხარეს ნამდვილ სერვისს არ იძახებს
- **ფაილი:** `backend/tests/test_orders_concurrency.py:673-683`, `:686-713`; `backend/app/services/auth.py:702-719`
- **სცენარი / შედეგი:** `test_a_reset_and_a_change_in_the_same_instant_do_not_deadlock` ცვლილებას ხელით წერს: `update(User)`, შემდეგ `delete(PasswordResetToken)`. `change_password` და `update_profile` არ იძახება. თუ ვინმე `update_profile`-ში reset token-ის წაშლას `update(User)`-ზე ადრე გადაიტანს, lock-ების რიგი ისევ შემობრუნდება და deadlock დაბრუნდება. ტესტი მაინც გაივლის: ის მხოლოდ `reset_password`-ის მხარეს იცავს. (code-reviewer)
- **გამოსწორება:** ცვლილება ნამდვილი სერვისით გაკეთდეს და `_until_queued_behind`-ით გაჩერდეს. თუ ეს ვერ ხერხდება, ტესტმა სერვისის statement-ების რიგი ცალკე დაამტკიცოს.
- **owner:** backend-dev · **status:** open

### A-003 · nit · შესული მომხმარებლის კალათის აღდგენისას ლოდინის დროს დამატებული ხაზი ქრება
- **ფაილი:** `frontend/src/context/CartContext.jsx:317-327` (`mergeWithAccount`), `:342-354` (`restoreFromAccount`)
- **სცენარი / შედეგი:** სესია აღდგა, `GET /cart` (ან 401→refresh→retry) ჯერ პასუხს ელოდება. მომხმარებელი პროდუქტს ამატებს. `savingRef` ჯერ false-ია, ამიტომ დამატება არ იგზავნება. პასუხის `HYDRATE` ხაზებს მთლიანად ცვლის და დამატებულს ჩუმად შლის. ფანჯარა ვიწროა (გვერდის მონაცემებიც იმავე API-დან მოდის), მაგრამ onrender-ის გაღვიძებისას რამდენიმე წამი გრძელდება. ეს A-016-ის (ძველი A-027) ნათესავია შესულის გზაზე. merge-ის ნაწილი წინა აუდიტამდეც ასე იყო. (code-reviewer)
- **გამოსწორება:** პასუხის მოსვლისას, თუ `stateRef.current.items` გაგზავნილისგან განსხვავდება, გაგზავნის შემდეგ დამატებული ხაზები ანგარიშის ხაზებს შეერწყას (`reconcileWithQuote`-ის მსგავსად). ტესტი: `getCart` დაყოვნებით, ლოდინისას ADD → ხაზი რჩება.
- **owner:** frontend-dev · **status:** open

### წინა აუდიტის (`10d933d`) ღია nit-ები — 2026-10-22-ს ისევ ძალაშია
თითოეული ახლანდელ კოდში გადამოწმდა. სრული სცენარი (ძველი ID-ებით) წინა `AUDIT.md`-შია: `git show 65dc3db:AUDIT.md`.
აქ მოკლედაა.

| ID | ძველი | ფაილი | რა | owner |
|---|---|---|---|---|
| A-004 | A-008 | `backend/app/services/cart.py:84-89` | `_resolve`-ს `ORDER BY` არ აქვს — ხაზების რიგი ბაზის ფიზიკურ რიგს მიჰყვება; დალაგდეს `wanted`-ის რიგით | backend-dev |
| A-005 | A-009 | `frontend/src/pages/Checkout.jsx:69-84` | Idempotency-Key-ის signature-ში მომხმარებელი არ შედის → სტუმრის timeout-იანი ცდის შემდეგ შესვლა 409 `IDEMPOTENCY_KEY_CONFLICT`-ს იძლევა; `user?.id` signature-ში ან 409-ზე `resetIdempotencyKey()` | frontend-dev |
| A-006 | A-010 | `frontend/src/admin/pages/ProductForm.jsx:225` | ცარიელი SKU payload-იდან ამოიღება, ამიტომ SKU-ს წაშლა შეუძლებელია; რედაქტირებისას `sku: null` | frontend-dev |
| A-007 | A-011 | `backend/app/schemas/admin_product.py:257` | `StockAdjustRequest.change` საზღვრის გარეშეა → int4 overflow → 500; `Field(ge=-100_000, le=100_000)` | backend-dev |
| A-008 | A-012 | `backend/app/services/order.py:470` | `cancel()` production-ში არ გამოიყენება, მხოლოდ ტესტებში (`test_inventory.py`, `test_orders_concurrency.py`, `test_order_trash_hidden.py`); ტესტებმა გამოიძახონ `order_status.transition` | backend-dev |
| A-009 | A-013 | `frontend/src/services/httpApi.js:122-127` | სტუმრის lookup token-ები localStorage-ში ვადის გარეშე გროვდება (საერთო კომპიუტერი); თარიღი + 30 დღის შემდეგ წაშლა | frontend-dev |
| A-010 | A-014 | `frontend/render.yaml` | storefront-ს `Strict-Transport-Security` არ აქვს (API-ს აქვს); დაემატოს voltbox.ge-ზე გადასვლისას | frontend-dev |
| A-011 | A-015 | `backend/app/db/ssl.py:44-46` | `DB_SSL_MODE=require` შიფრავს, მაგრამ სერტიფიკატს არ ამოწმებს; გაშვებამდე `verify-full` + `DB_SSL_ROOT_CERT` | backend-dev |
| A-012 | A-016 | `CLAUDE.md:49`, `backend/README.md:28` | ლოკალური migration-ის ბრძანება `VOLTBOX_NO_DOTENV=1`-ის გარეშეა, ამიტომ `backend/.env`-ს ტვირთავს; დაემატოს `VOLTBOX_NO_DOTENV=1 JWT_SECRET=<dummy ≥32>`, როგორც CI-ში | task-executor |
| A-013 | A-020 | `backend/app/api/v1/routes/auth.py:182-184` | 5/წთ ლიმიტი სახელის/ტელეფონის ჩვეულებრივ შენახვაზეც მოქმედებს | backend-dev |
| A-014 | A-021 | `backend/app/services/auth.py` (`change_password`, `update_profile`) | წარმატებული შეცვლა `failed_login_count`-ს არ ანულებს (ანულებს მხოლოდ login და reset, `:663`) | backend-dev |
| A-015 | A-023 | `frontend/src/context/CartContext.jsx:294-296` | მეორე tab-ის storage `HYDRATE` `fromAccount`-ის გარეშეა → marker + ზედმეტი `PUT` | frontend-dev |
| A-016 | A-027 | `frontend/src/context/CartContext.jsx` (`reconcileWithQuote`, `REFRESH`) | quote-ის ლოდინისას სხვა tab-ში დამატებული ხაზი „აღარ არის ხელმისაწვდომი“-თ იშლება | frontend-dev |
| A-017 | A-024 | `frontend/src/context/CartAccountSync.test.jsx:309` | ტესტი „a later manual sign-out …“ flag-ის განულებას არ ამოწმებს | frontend-dev |
| A-018 | A-025 | `frontend/src/context/CartAccountSync.test.jsx:446`, `:458` | `saveCart.mock.calls`-ის ციკლი ცარიელ სიაზე გადის; `expect(api.saveCart).not.toHaveBeenCalled()` | frontend-dev |
| A-019 | A-028 | `frontend/src/pages/GuestCartQuote.test.jsx` | ორი ტესტი toast-ის არყოფნას პასუხის დამუშავებამდე ამოწმებს | frontend-dev |
| A-020 | A-029 | `backend/tests/` | ერთი reset-link-ის ორჯერ ერთდროულ გამოყენებაზე ტესტი არ არის | backend-dev |

ყველას status: open, გარდა: **A-007 — fixed (verified), `35e6fb0`** (2026-11-15, re-review: code-reviewer).
`change` ±100 000-ის ფარგლებშია (`MAX_STOCK_ADJUSTMENT`), გარეთ → 400 `VALIDATION_ERROR`. ნული ისევ 400-ია, არსებული
`EMPTY_ADJUSTMENT` კოდით (ka/en ტექსტი და ტესტი უკვე ჰქონდა). 4 ახალი ტესტი ძველ schema-ზე ვარდება: 3 000 000 000 → asyncpg
`value out of int32 range` (500), 100 001 → 200. ნარჩენი: A-072, A-073.

**A-010 — fixed (verified), `a13000d`** (2026-11-15): `frontend/render.yaml`-ში `Strict-Transport-Security: max-age=300`,
`includeSubDomains`/`preload`-ის გარეშე; კომენტარი — voltbox.ge-ის შემდეგ 31536000. `TEMP-ONRENDER` მარკერები უცვლელია (2).
`backend/tests/test_storefront_blueprint.py` ძველ ფაილზე ვარდება. Render-ზე header-ი deploy-მდე არ შემოწმდება.
re-review: code-reviewer — დახურულია; ნარჩენი A-085 (მარკერი HSTS-ზე — მფლობელის გადაწყვეტილება).

**A-011 — fixed (verified) კოდში, `3540f2f`; status: blocked (owner)** (2026-11-15): სამივე რეჟიმი ტესტითაა დაფიქსირებული
(`tests/test_db_ssl.py`, 19; 6 ძველ ssl.py-ზე ვარდება); დეპლოიზე `require` WARNING-ს წერს; ცუდი CA ფაილი →
`DB_SSL_ROOT_CERT`-ის მდებარეობის მითითებით RuntimeError; `require` + CA სრულად ამოწმებს. ეფექტური რეჟიმი production-ზე უცვლელია
(`require`). docs/deployment.md — „ბაზასთან TLS". CA-ს დაყენება და გადართვა მფლობელისაა (PROGRESS.md Blockers).
re-review: security-auditor — დახურულია; ნარჩენი A-081, A-086.

### A-001-ის re-review-ის nit-ები (security-auditor, 2026-10-22)

#### A-021 · nit · კომენტარი „მხოლოდ სამი parser ხედავს ბაიტებს“ ზედმეტს ამბობს — JPEG-ის გზა TIFF-ის IFD კოდს მაინც უშვებს
- **ფაილი:** `backend/app/services/storage.py:225-227`, docstring `:49-64`
- **სცენარი / შედეგი:** EXIF-იან JPEG-ზე, რომელსაც JFIF dpi არ აქვს (კამერის ჩვეულებრივი ფოტო), Pillow-ის JPEG plugin-ი თავად იძახებს `getexif()`-ს. ის `TiffImagePlugin.ImageFileDirectory_v2`-ს გადის (`JpegImagePlugin.py` `_read_dpi_from_exif`). იგივე ხდება APP2 MPF-ზეც (`_getmp`). libtiff-ის decoder-ი აქამდე არ აღწევს და Pillow 13-ზე ცნობილი CVE არ არის. თუმცა კომენტარის მიხედვით მომავალი TIFF-ის advisory JPEG ატვირთვას არ ეხება, რაც არასწორია.
- **გამოსწორება:** კომენტარში ჩაიწეროს, რომ JPEG-ის გზაზე TIFF-ის tag-directory-ის კოდი ეშვება, და `ImageFileDirectory`-ის advisory-ები JPEG ატვირთვებზეც გადამოწმდეს.
- **owner:** backend-dev · **status:** open

#### A-022 · nit · `_announced_format`-ის „დაშვებული ფორმატი → None“ branch-ის მიზეზი არასწორია და ტესტი მას არ ამოწმებს
- **ფაილი:** `backend/app/services/storage.py:62-64`; `backend/tests/test_admin_images.py:242-259`
- **სცენარი / შედეგი:**
  - docstring-ის მაგალითი არასწორია: MPO Pillow 13-ში open-ზე რეგისტრირებული არ არის (`MpoImagePlugin.py:204` დაკომენტარებულია), ამიტომ `Image.OPEN`-ში არ ჩანს.
  - ტესტი branch-ს ვერ ამოწმებს: დაზიანებული JPEG/PNG-ის prefix-ს სხვა plugin-ის `accept` არ ემთხვევა, WebP-ის ნიმუში (12 ბაიტი, `VP8` chunk-ის გარეშე) კი WebP-ის `_accept`-საც ვერ გადის. ამიტომ სამივე „damaged“ ტესტი ამ branch-ის გარეშეც გაივლიდა.
  - branch-ი უვნებელია და დაცვის დამატებითი ფენაა.
- **გამოსწორება:** docstring-ში სწორი მიზეზი; WebP-ის ნიმუშს დაემატოს `b"VP8 "`, რომ branch მართლა შემოწმდეს.
- **owner:** backend-dev · **status:** open

#### A-023 · nit · CI-ის pip-audit ხელსაწყოს lock-ში ისევ certifi 2026.7.22-ია
- **ფაილი:** `.github/pip-audit/requirements.txt:17`
- **სცენარი / შედეგი:** ეს audit ხელსაწყოს გარემოა და CI-ის ნაბიჯი მას არ ამოწმებს. ქსელში მყოფ თავდამსხმელს, რომელსაც კომპრომეტირებული intermediate აქვს, შეუძლია advisory-ების პასუხი გააყალბოს და audit სუფთა გამოიყვანოს. რისკი დაბალია.
- **გამოსწორება:** certifi → 2026.10.19 ამ lock-ში, `.github/pip-audit/requirements.in`-ში აღწერილი container-ის ბრძანებით (ან Dependabot-ის PR-ით).
- **owner:** task-executor
- **status:** fixed — 2026-10-27, `agent-system`. რა გაკეთდა:
  - lock-ში certifi 2026.7.22 → 2026.10.19 (PYSEC-2026-4320) და filelock 4.0.0 → 4.2.1 (CVE-2026-112940, -112913, -112907; Dependabot: high + 2 low). სხვა pin-ი არ შეცვლილა.
  - Docker გამორთული იყო, ამიტომ ორი ჩანაწერი ხელით შეიცვალა: ვერსია და PyPI-ის ორივე ფაილის (wheel, sdist) sha256, pip-compile-ის ფორმატით. არცერთ პაკეტს დამოკიდებულება არ აქვს, ამიტომ resolve-ი სხვა pin-ს ვერ შეცვლიდა.

  მტკიცებულება (Windows, Python 3.14):
  - ახალ venv-ში `pip install --require-hashes --only-binary=:all: -r .github/pip-audit/requirements.txt` გავიდა, pip-audit 2.10.1 დადგა.
  - ამ pip-audit-ით CI-ის ბრძანება (`--strict --disable-pip`, backend-ის სამი lock) — 0, exit 0; იგივე ამ lock-ზე — 0, exit 0.
  - Linux container-ში (`requirements.in`-ის ბრძანება) ხელახლა არ დაგენერირებულა.

#### A-024 · nit · `config.py`-ის კომენტარი ისევ „measured on Pillow 12.3“-ს ამბობს
- **ფაილი:** `backend/app/core/config.py:208`
- **სცენარი / შედეგი:** A-001-მა გაზომვის აღწერა `storage.py`-ში განაახლა, ეს კომენტარი კი არა.
- **გამოსწორება:** დაემატოს „re-checked on 13.0.0 (A-001)“.
- **owner:** backend-dev · **status:** open

---

## შესამოწმებელი (დაუდასტურებელი)

- **Pillow 13 + Python 3.14 wheel და `pip check`** (A-001). lock-ის განახლება Linux container-ში არ გაშვებულა. უცნობია,
  ჯდება თუ არა 13.0.0 დანარჩენ pin-ებთან და იცვლება თუ არა decode-ის ხარჯი.
- **`place_order`-ის IntegrityError-ის (clash) გზა სანაგვეში მყოფ შეკვეთაზე** (`backend/app/services/order.py:283-291`).
  კოდის მიხედვით სწორია (`deleted_at`-ით განზრახ არ იფილტრება, როგორც პირველი lookup), მაგრამ ცალკე ტესტი არ აქვს.
  შემთხვევისთვის trash და პარალელური replay ერთსა და იმავე მომენტში უნდა მოხდეს.
- **წინა აუდიტის „შესამოწმებელი“ სიიდან ღიაა:**
  - Supabase Storage-ის policy-ები `product-images`-ზე (Dashboard, მფლობელი);
  - email-ის Unicode lower-case;
  - `ORDER_RATE_LIMIT` CGNAT-ზე;
  - multi-tab sign-out.

  ამ აუდიტში არცერთი არ გადამოწმებულა და არცერთი არ შეცვლილა.
- **CI-ის ნაწილები, რომლებიც ლოკალურად არ გაშვებულა:** e2e (nightly), Docker image build და API surface,
  frontend mock-data export, `pip install --require-hashes` + `pip check`, frontend Node 22-ზე.

## reviewer-ის მიგნებები, რომლებიც არ დადასტურდა — და რატომ

- **security-auditor: Pillow და certifi „სამივე lock-შია“.** `requirements-build.txt` არცერთს არ შეიცავს (grep). ორივე
  მხოლოდ `requirements.txt`-სა და `requirements-dev.txt`-შია. A-001-ის არსი არ იცვლება.
- **security-auditor: `frontend/scripts/e2e/screens.mjs:351`, `startsWith(MOCKUP_DIR)` separator-ის გარეშე.** ეს მხოლოდ
  localhost-ზე მიბმული ლოკალური სკრიპტია, მსგავსი სახელის მეზობელი საქაღალდე არ არსებობს და ზიანის სცენარი არ ჩანს.
  მიგნებად არ ჩაიწერა.
- **tester: `pip-audit` 10 წუთში გაიჭედა.** ხელახლა გაეშვა `--disable-pip`-ით (როგორც CI-ში) და 25 სისუსტე აჩვენა
  (A-001). გაჭედვის სავარაუდო მიზეზი ისაა, რომ `--disable-pip`-ის გარეშე pip-audit dependency-ებს თავიდან resolve-ს
  უკეთებს. ეს არ გადამოწმებულა; კოდის ხარვეზად არ ჩაიწერა.
- **security-auditor (A-001-ის re-review): TGA, IM, SPIDER და PCD ფაილები ახლა `INVALID_IMAGE`-ს იღებს
  `UNSUPPORTED_IMAGE_FORMAT`-ის ნაცვლად** (მათ plugin-ებს `accept` არ აქვს), ხოლო ზოგი არა-გამოსახულება, რომლის prefix
  ფართო `accept`-ს ემთხვევა (XBM, WMF, DIB), „format“-ის შეტყობინებას იღებს. იცვლება მხოლოდ შეტყობინების ტექსტი
  ადმინისთვის, ფაილი ორივე შემთხვევაში უარყოფილია. reviewer-მაც თქვა, რომ გამოსწორება არ სჭირდება; მიგნებად არ ჩაიწერა.
- **backend-dev (A-001): MPO-header-იანი JPEG `UNSUPPORTED_IMAGE_FORMAT`-ით უარყოფილია.** ჰიპოთეზაა და არ შემოწმებულა. თუ
  სწორია, ასე იყო A-001-მდეც და ცვლილება მას არ ეხება. შესამოწმებელია, წერს თუ არა ამას რეალური ტელეფონი.
- **tester-ის warning-ი** „jsdom created 57 times“ სიჩქარის მინიშნებაა და შეცდომა არ არის.

## რა შემოწმდა და რიგზეა (მოკლედ)

- **სანაგვე, backend:**
  - ყველა მკითხველი `deleted_at IS NULL`-ით ფილტრავს: admin-ის სია, `counts_by_status`, dashboard, admin customers, მომხმარებლის სია და `GET /orders/{n}`. guest lookup-ის ფილტრი იმავე statement-შია, ამიტომ იგივე 404 ბრუნდება.
  - idempotency-ის lookup-ები განზრახ არ ფილტრავს.
  - trash/restore/delete/purge-ში `adjust_stock` არ არის. FK-ები: CASCADE / SET NULL.
  - `ORDER_IN_TRASH` lock-ის შემდეგ მოწმდება.
  - purge-ის audit row-ში PII არ არის.
  - 0016 და `docs/migrations/0016...sql` ერთმანეთს ემთხვევა, ყველაფერი `public.`-ით.
  - `test_admin_auth.py` admin route-ებს (DELETE-ის ჩათვლით) OpenAPI-დან ჩამოთვლის.
- **სანაგვე, admin UI:** დიალოგები, მარაგის გაფრთხილება, 404/409-ის დამუშავება, toast-ები.
- **წინა გასწორებები:**
  - A-001/A-017: ლიმიტი, lockout, პირობითი UPDATE;
  - A-002: floor/ceil;
  - A-003–A-007, A-018, A-019: სესია/კალათა;
  - A-004/A-026: `POST /cart/quote` — stateless, 30/წთ, ფასი მხოლოდ ბაზიდან;
  - A-022: lock-ების რიგი.
- **Stage 3:**
  - `frontend/src/admin/` `db9a242`-ის შემდეგ არ შეცვლილა, backend-ის კოდიც არ შეცვლილა;
  - საერთო კომპონენტები იცვლება მხოლოდ token-ებით და opt-in prop-ებით;
  - handler-ები, aria-label-ები, role-ები და heading-ები დაკარგული არ არის;
  - CSP უცვლელია, ფონტები self-hosted;
  - `dangerouslySetInnerHTML`/`innerHTML`/`eval` არ არის, JSON-LD `textContent`-ით იწერება.
- **Secrets:** 61 commit-ის ისტორიაში key ან `.env` არ ჩანს.


---

## გარე აუდიტი — 2026-11-12

- **თარიღი:** 2026-11-12
- **commit:** `7bcca3c`
- **წყარო:** დამოუკიდებელი აუდიტი (Claude, claude.ai). კოდი წაკითხულია სრულად; ტესტები და სერვერი გაშვებულია
  ლოკალურად (Python 3.14.6, Node 22, PostgreSQL 16, Redis; uvicorn და gunicorn 2 worker-ით). production-ს არ შევხებივართ.
- **baseline:**
  - backend: ruff ✅ · format ✅ · mypy ✅ · **pytest 1106 passed** · branch coverage 94% · alembic 0001→0016 + check ✅ ·
    **pip-audit --strict ❌ 1 სისუსტე** (A-035)
  - frontend: lint ✅ · **vitest 672 / 57** (22 `act()` გაფრთხილება) · line coverage 67.5% · build ✅ · npm audit 0
- **შედეგი:** 0 critical · 8 should-fix (A-030–A-037) · 14 nit (A-038–A-051)
- ყველა მიგნება გაშვებით ან კოდის წაკითხვით დადასტურდა; რომელი როგორ — თითოეულის „სცენარში“ წერია.
- ამ სექციის მიგნებები A-001–A-029-ს არ იმეორებს. A-007, A-010 და A-011 ისევ ღიაა და ზემოთ ცხრილშია.

**`/fix A-035 A-030 A-031` 2026-11-12** (ბრენჩი `fix/external-2026-11-12`):
- A-035 — fixed (verified), `5d62944`. pip-audit (CI-ის ფორმა, Dockerfile-ის base image-ში): ძველ lock-ზე exit 1,
  ახალზე exit 0. re-review: code-reviewer — დახურულია.
- A-030 — fixed (verified), `1880bcc`. 5 ახალი ტესტი ძველ `session.js`/`httpClient.js`-ზე ვარდება, ახალზე გადის
  (ორკესტრატორმაც გაუშვა ორივე მიმართულებით). re-review: code-reviewer — დახურულია.
- A-031 — fixed (verified), `6ed1119`. refresh-ის ტესტი ძველ decorator-ზე ვარდება (მე-6 → 429), ახალზე გადის
  (ორკესტრატორმაც გაუშვა). re-review: security-auditor — დახურულია.
- re-review-მ 3 ახალი nit იპოვა: A-052–A-054 (სექციის ბოლოს).
- gate-ები (`6ed1119`): ruff ✅ · format 167 ✅ · mypy 148 ✅ · **pytest 1108 passed** (baseline 1106 + 2) ·
  eslint ✅ · **vitest 677 / 57** (baseline 672 + 5).
- საბოლოო შემოწმება (`92a8647`, tester): ruff ✅ · format 167 ✅ · mypy 148 ✅ · pytest 1108 passed ·
  alembic 0001→0016 + check ✅ (scratch ბაზაზე) · `docker build` ✅ · eslint ✅ · vitest 677 / 57 · build `http` ✅ ·
  build `mock` ✅. არ გაშვებულა: e2e, ნამდვილი ბრაუზერი, frontend Node 22-ზე.

**`/fix A-032 A-033` 2026-11-12** (ბრენჩი `fix/external-a032-a033`, `agent-system`-იდან, `85a2781`):
- A-032 — fixed (verified), `e903dcd`. 4 ახალი ტესტი ძველ კოდზე ვარდება (`optimize: True`; validate/shrink loop-ის thread-ზე;
  loop-ის 0 tick), ახალზე გადის. re-review: code-reviewer — დახურულია, 2 nit (A-055, A-056).
- A-033 — fixed (verified), `6469e57`. 46 ახალი ტესტი; 35 ძველ კოდზე ვარდება. ორკესტრატორმა აუდიტის ორივე სცენარი ორივე
  კოდზე გაუშვა: HEAD — 1600×1200 და ბაიტ-ბაიტ უცვლელი ფაილი GPS-ით და `Make`-ით; ახალი — 1200×1600, GPS/`Make` აღარ არის.
  მეხსიერების ორივე კლასი (`TestDecodeMemoryIsBounded` და ახალი `…WhenOnlyTurning`) Linux-ზე, production image-ში
  (python:3.14.7-slim, Pillow 13) — 8/8 budget-ში. re-review: security-auditor — დახურულია ახალი ატვირთვებისთვის, 4 nit
  (A-057–A-060) და დაუდასტურებელი A-062.
- **ინციდენტი (A-061):** A-033-ის დეველოპერის scratchpad pytest-plugin-მა `app` conftest-მდე დააიმპორტა და session fixture-ის
  `alembic downgrade base` ორჯერ გაეშვა `backend/.env`-ის ბაზაზე (სავარაუდოდ ლაივ Supabase). ორივეჯერ 0010-ის downgrade-ზე
  ჩავარდა, 0016→0011 იმავე ტრანზაქციაში უკვე შესრულებული იყო. კოდის მიხედვით ყველაფერი rollback-ით გაუქმდა (ერთი
  ტრანზაქცია, autocommit არსად) — **ლაივ ბაზაზე გადამოწმებული არ არის**, მფლობელისაა.
  განახლება 2026-11-14: მფლობელმა გადაამოწმა (0016, დაზიანება არ არის); A-061 — fixed (verified), `6ca1bdc`.
- gate-ები (`6469e57`, ორკესტრატორი, მარტო გაშვებული): ruff ✅ · format 167 ✅ · mypy 148 ✅ · **pytest 1159 passed**
  (baseline 1108 + 51) · `docker build` ✅.

**`/fix A-039 A-040 A-034` 2026-11-14** (ბრენჩი `fix/a039-a040-a034`, `agent-system`-იდან, `4a358a2`):
- A-039 — fixed (verified), `227ad5d`. 2 race-ტესტი ძველ კოდზე ვარდება, ახალზე გადის. re-review: code-reviewer — დახურულია.
- A-040 — fixed (verified), `a18e3ff`. 7 race-ტესტი ძველ კოდზე 7/7 ვარდება. re-review: code-reviewer — დახურულია, deadlock-ის
  გზა არ არის; ფიქსამდელი შესამოწმებელი A-071.
- A-034 — fixed (verified), `b530418`, აუდიტში აღწერილი გზისთვის (`uvicorn.error`/`gunicorn.error`). 12 ტესტი ძველ კოდზე
  ვარდება. re-review: security-auditor — დახურულია; ნარჩენი should-fix A-067 (`Failing row contains`), nit-ები A-068–A-070.
- ორკესტრატორის baseline (`4a358a2`): pytest 1199 → 1220 (+21). gate-ები (`b530418`, მარტო გაშვებული): ruff ✅ ·
  format 170 ✅ · mypy 151 ✅ · **pytest 1220 passed**.
- **სატესტო ბაზის შეჯახება:** subagent-ის დასრულებისას Stop hook-ის (`verify.sh`) `pytest` ორკესტრატორის `pytest`-თან ერთად
  გაეშვა ერთ `voltbox_test`-ზე. შედეგი იყო ცალკეული შეცდომები: teardown-ის `alembic downgrade`-ის deadlock,
  `relation "users" does not exist`. პარალელურ pytest-ს პირველი ორი პირდაპირ დაუკავშირდა (`tasklist`-ში უცხო `pytest.exe`
  ჩანდა). ერთი `test_search`-ის assertion-იც, სავარაუდოდ, იგივე მიზეზით იყო, მაგრამ ეს დამტკიცებული არ არის. მარტო გაშვებისას
  ყველა გაშვება მწვანეა.
- საბოლოო შემოწმება (`1c05975`, tester, პარალელური pytest არ ყოფილა): ruff ✅ · format 170 ✅ · mypy 151 ✅ ·
  pytest 1220 passed · alembic 0001→0016 + check ✅ (scratch ბაზაზე; სჭირდება `JWT_SECRET`) · eslint ✅ ·
  vitest 677 / 57 · build `http` ✅ · build `mock` ✅. არ გაშვებულა: რეალური gunicorn (Linux), e2e, frontend Node 22-ზე,
  `docker build` (Dockerfile და დამოკიდებულებები არ შეცვლილა).

**`/fix A-067 A-038 A-007 A-041 A-071 A-045 A-060` 2026-11-15** (ბრენჩი `fix/a067-a038-a007-a041-a071-a045-a060`,
`agent-system`-იდან, `b74e108`). ყოველ commit-ზე ორკესტრატორმა თავად გაუშვა ruff/format/mypy/სრული pytest მარტო და ძველ
კოდზე ჩავარდნა `git stash`-ით (გამონაკლისები თითო finding-შია).
- A-067 (+A-068) — fixed (verified), `0452669`; re-review: security-auditor — დახურულია.
- A-038 — fixed (verified), `069f8b1`; re-review: code-reviewer — დახურულია.
- A-007 — fixed (verified), `35e6fb0`; re-review: code-reviewer — დახურულია, ახალი nit A-073 (+ backend-dev-ის A-072).
- A-041 — fixed (verified), `91420c3`; re-review: code-reviewer — დახურულია. frontend gate: eslint ✅ · vitest 677 / 57 · build ✅ ×2.
- A-071 — **დადასტურდა** და fixed (verified), `50905ba`; re-review: code-reviewer — დახურულია.
- A-045 — fixed (verified), `c4d2217`; re-review: code-reviewer — დახურულია, ახალი nit A-074.
- A-060 — fixed (verified), `cc6abee`; re-review: security-auditor — დახურულია, დაუდასტურებელი A-075 (WEBP).
- pytest: 1220 (baseline `b74e108`) → 1226 → 1251 → 1258 → 1268 → 1271 → 1285 → **1289**.
- საბოლოო შემოწმება (`264e199`, ორკესტრატორი, foreground-ში, პარალელური pytest არ ყოფილა — `tester` აგენტი არ გამოიყენებოდა,
  რომ Stop hook-ს არ შეჯახებოდა): ruff ✅ · format 172 ✅ · mypy 153 ✅ · **pytest 1289 passed** · alembic 0001→0016 + check ✅
  (ახალ ცარიელ ლოკალურ `voltbox_check`-ზე) · eslint ✅ · vitest 677 / 57 · build `http` ✅ · build `mock` ✅. არ გაშვებულა:
  `docker build` (Dockerfile/დამოკიდებულებები არ შეცვლილა), e2e, ნამდვილი ბრაუზერი, frontend Node 22-ზე, HTTP-ის დონის race.
- **სატესტო ბაზის შეჯახება ისევ:** ორკესტრატორის Stop hook-ის `pytest` ყოველ სვლის ბოლოს ეშვება და 6-ჯერ დაემთხვა
  subagent-ის ან ორკესტრატორის `pytest`-ს (`relation "users"/"categories" does not exist`, ასობით error). ეს შედეგები
  არ ჩაითვალა. ყველა ჩათვლილი გაშვება `tasklist`-ის guard-ით, მარტო იყო. ორჯერ hook-მა subagent-ის „ძველ კოდზე“ შემოწმების
  მომენტი დაიჭირა (ახალი ტესტები მოსალოდნელად ჩავარდა).

**`/fix A-042 A-043 A-044 A-069 A-070 A-072 A-073 A-074` 2026-11-15** (ბრენჩი `fix/a042-a074`, `agent-system`-იდან, `c193db4`).
ყოველ finding-ზე ორკესტრატორმა თავად გაუშვა ruff/format/mypy/სრული pytest მარტო (`tasklist`-ის guard-ით) და ძველ კოდზე
ჩავარდნა `git stash`-ით (A-070-ზე — ძველი გამოძახების დროებით ჩასმით, A-072-ზე — ძველი ფაილი + მხოლოდ კონსტანტა).
- A-042 — fixed (verified), `ec0c98f`; migration 0017; re-review: security-auditor — დახურულია. **ლაივ SQL deploy-მდე** (Blockers).
- A-043 — fixed (verified), `0765bb8`; re-review: code-reviewer — დახურულია.
- A-044 — fixed (verified), `12b2723`; `demote-user` შეგნებულად არ ამოწმებს; re-review: code-reviewer — დახურულია.
- A-069 — **not reproduced (measured)**, კოდი არ შეცვლილა; დეველოპერის ცვლილება უარყოფილია (დეტალები finding-ში).
- A-070 — fixed (verified), `ccb494d`; re-review: code-reviewer — დახურულია.
- A-072 — fixed (verified), `23566e9`; DB CHECK-ის გარეშე; re-review: code-reviewer — დახურულია.
- A-073 — fixed (verified), `4a15441`; re-review: code-reviewer — დახურულია.
- A-074 — fixed (verified), `0927590`; re-review: code-reviewer — დახურულია.
- re-review-ის ახალი nit-ები: A-076 (გასწორდა A-072-ში), A-077, A-078, A-079 — ღია.
- pytest: 1289 (baseline `c193db4`) → 1308 → 1312 → 1334 → 1335 → 1348 → 1363 → **1364**.
- საბოლოო შემოწმება (`0927590`, ორკესტრატორი, foreground-ში, პარალელური pytest არ ყოფილა): ruff ✅ · format 178 ✅ · mypy 158 ✅ ·
  **pytest 1364 passed** · alembic 0001→0017 + check ✅ (ახალ ცარიელ ლოკალურ `voltbox_final_check`-ზე, შემდეგ წაიშალა) ·
  eslint ✅ · vitest 677 / 57 · build `http` ✅ · build `mock` ✅. არ გაშვებულა: `docker build` (Dockerfile/დამოკიდებულებები
  არ შეცვლილა), e2e, ნამდვილი ბრაუზერი, frontend Node 22-ზე, ლაივ ბაზა.
- **სატესტო ბაზის შეჯახება:** Stop hook-ს ახლა საკუთარი `voltbox_hook_test` აქვს, მაგრამ ორკესტრატორის და subagent-ის hook-ები
  ერთმანეთს ამ ბაზაზე 5-ჯერ დაემთხვა (`relation "users"/"categories" does not exist`, ერთხელ deadlock). ეს შედეგები არ ჩაითვალა.

**`/fix A-063 A-036 A-046 A-010 A-011 A-048 A-065 A-066` 2026-11-15** (ბრენჩი `fix/a063-a036-a046-a010-a011-a048-a065-a066`,
`agent-system`-იდან, `b5aeeec`). ყველა ID ღია იყო. ძველ კოდზე ჩავარდნა subagent-ებმა `git show HEAD:<file>`-ით შეამოწმეს
(`git stash` მათთვის დაბლოკილია). pytest ერთდროულად ერთზე მეტი არასდროს გაშვებულა. Stop hook-ს pytest აღარ აქვს.
- A-063 — fixed (verified), `ca58669`; re-review: security-auditor — დახურულია.
- A-036 — fixed (reviewed), owner check pending, `31c2427` + `e2d60a6`. re-review-მ (security-auditor) slowapi-ის WARNING-ში
  ნედლი IP იპოვა (should-fix, image-ზე გაზომილი). გასწორება — რაუნდი 1/2, `e2d60a6`; მეორე re-review — დახურულია.
- A-046 — fixed (verified), `65a241f`; image-ზე გაზომილი; re-review: security-auditor — დახურულია.
- A-010 — fixed (verified), `a13000d`; re-review: code-reviewer — დახურულია.
- A-011 — fixed (verified) კოდში, `3540f2f`; **blocked (owner)**: CA და env ცვლადები Render-ზე. re-review: security-auditor — დახურულია.
- A-048 — fixed (verified), `87db0fd`; re-review: code-reviewer — დახურულია.
- A-065 — fixed (verified), `13eb2b0`; re-review: security-auditor — დახურულია.
- A-066 — fixed (reviewed), `e2a2a81`; re-review: code-reviewer — დახურულია.
- re-review-ის docs-ის მიგნებები (A-010/A-011/A-036/A-066-ის ტექსტში დაშვებული უზუსტობები) — `f5b0cd3`; მეორე re-review: დახურულია.
- ახალი: A-080 (should-fix, ჩვენამდეც ასე იყო), A-081–A-087 (nit) — სექციის ბოლოს.
- pytest: 1364 (baseline `b5aeeec`) → 1368 → 1378 → 1407 (+1 skip) → 1409 → 1428 → 1432 → **1447 passed, 1 skipped**.
- საბოლოო შემოწმება (`f5b0cd3`, ორკესტრატორი, foreground-ში): ruff ✅ · format 182 ✅ · mypy 162 ✅ · **pytest 1447 passed,
  1 skipped** · alembic 0001→0017 + check ✅ (ახალ ცარიელ `voltbox_final_check`-ზე, შემდეგ წაიშალა) · eslint ✅ ·
  **vitest 681 / 58** (baseline 677 / 57) · build `http` ✅ · build `mock` ✅ · `docker build` ✅. image გაეშვა მხოლოდ
  ლოკალური env-ით (`.env`-ის გარეშე, 1 worker, ლოკალური ბაზა), გაჩერდა. ერთი vitest-ის გაშვება 1 ჩავარდნით დასრულდა,
  როცა პარალელურად pytest მიდიოდა; მომდევნო 3 გაშვება მწვანეა. ტესტის სახელი ვერ დავაფიქსირე, ამიტომ flaky-ს მიზეზი დაუდგენელია.
  არ გაშვებულა: e2e, ნამდვილი ბრაუზერი, frontend Node 22-ზე, Render, ლაივ ბაზა.

**`/fix A-080 A-037 A-081 A-083 A-084 A-085 A-086 A-087` 2026-11-16** (ბრენჩი `fix/a080-a037-a081-a083-a087`, `agent-system`-იდან,
`0a9522c`). რვავე ID ღია იყო, არცერთი მხოლოდ frontend-ის არ არის. მფლობელმა წინასწარ დაამტკიცა A-080 (300/წთ, health-ის
გამონაკლისი), A-037 (TOTP-ის გარეშე) და A-085 (მესამე მარკერი). ძველ კოდზე ჩავარდნა ორკესტრატორმა `git stash`-ით ხელახლა
გაუშვა ყველა კოდის ID-ზე. pytest ერთდროულად ერთზე მეტი არასდროს გაშვებულა.
- A-080 — fixed (verified), `1d9e314`; re-review: security-auditor — დახურულია.
- A-037 — fixed (verified), `e09ce2e` + `85bb546` (re-review-ის should-fix, რაუნდი 1/2); security-auditor ×2 — დახურულია.
- A-081 — fixed (verified), `77f1e58`; security-auditor — დახურულია.
- A-083 — fixed (verified), `a36741f`; code-reviewer — დახურულია.
- A-084 — fixed (reviewed), `45c8326`; code-reviewer — დახურულია.
- A-085 — fixed (verified), `f5f948b`; code-reviewer — დახურულია.
- A-086 — fixed (verified), `3c72ab5`; code-reviewer — დახურულია.
- A-087 — fixed (verified), `95c98b5` (აუდიტის მექანიზმი არ დადასტურდა, გაჟონვა — კი); code-reviewer — დახურულია.
- ახალი nit-ები: A-088–A-095 (A-094 — მფლობელის გადაწყვეტილება) — სექციის ბოლოს.
- pytest: 1447 (baseline `0a9522c`) → 1455 → 1616 → 1638 → 1648 → 1656 → **1658 passed, 1 skipped**.
- საბოლოო შემოწმება (`95c98b5`, tester): ruff ✅ · format 185 ✅ · mypy 165 ✅ · **pytest 1658 passed, 1 skipped** ·
  alembic 0001→0017 + check ✅ (ცარიელ `voltbox_final_check`-ზე, შემდეგ წაიშალა) · `docker build` ✅ (პაროლების სიის sha256
  image-ში ემთხვევა) · eslint ✅ · **vitest 682 / 58** (baseline 681 / 58) · build `http` ✅ · build `mock` ✅. Node 22.23.2 /
  npm 10.9.8 container-ში (ორკესტრატორი; მხოლოდ `frontend` + ორი backend ფაილი, რომელსაც ტესტები კითხულობს): `npm ci`,
  eslint, vitest 682 / 58, ორივე build ✅.
  არ გაშვებულა: e2e, ნამდვილი ბრაუზერი, Telegram-ის ნამდვილი გაგზავნა, Render (ლიმიტი რეალური IP-ით), ლაივ ბაზა.

**`/fix A-055 A-056 A-057 A-058 A-059 A-075 A-077 A-078 A-079` 2026-11-16** (ბრენჩი `fix/a055-a059-a075-a077-a079`,
`agent-system`-იდან, `069410b`). ცხრავე ID ღია იყო. მფლობელმა წინასწარ დაამტკიცა ყველა (A-077 — ზონა Settings-იდან, A-078 —
წინასწარი შემოწმება ჩაწერამდე); `DECODE_COST`, ბიუჯეტი და `Semaphore(1)` უცვლელია. storage.py-ის ხუთი ID რიგრიგობით გავიდა
(ერთ ფაილზე ერთი აგენტი). ძველ კოდზე ჩავარდნა ორკესტრატორმა `git stash`-ით ხელახლა გაუშვა ყველა კოდის ID-ზე; A-079-ზე
(მხოლოდ ტესტი) — დროებითი bypass-ით. pytest ერთდროულად ერთზე მეტი არასდროს გაშვებულა.
- A-055 — fixed (verified), `84d1b1f`; code-reviewer — დახურულია.
- A-056 — fixed (verified), `6b2d585` + `aa98335` (გაზომილია: `method=6` → `5`); code-reviewer — დახურულია.
- A-057 — fixed (verified), `93e8fd1`; code-reviewer — დახურულია.
- A-058 — fixed (verified), `a837692`; security-auditor — დახურულია.
- A-059 — fixed (verified), `d446b70` (აუდიტის მაგალითი სხვა დეფექტი აღმოჩნდა → A-097); code-reviewer — დახურულია.
- A-075 — fixed (verified), `bb7ae36` (დადასტურდა: 285 → 33 ms); security-auditor — დახურულია.
- A-077 — fixed (verified), `9d2f96a` (+ `STORE_TIMEZONE`-ის startup-ვალიდაცია); code-reviewer — დახურულია.
- A-078 — fixed (verified), `33c3cfe`; code-reviewer — დახურულია.
- A-079 — fixed (verified), `172a3ba`; code-reviewer — დახურულია.
- PROJECT.md: Decision Log-ის ახალი ჩანაწერი და მოძველებული „What still holds" ხაზები — `aa98335`.
- ახალი: A-096, A-097 (should-fix, ჩვენამდეც ასე იყო, scope-ის გარეთ — ღია), A-098–A-100 (nit), A-101 (needs decision) —
  სექციის ბოლოს.
- pytest: 1658 (baseline `069410b`) → **1757 passed, 1 skipped**.
- საბოლოო შემოწმება (`aa98335`, tester): ruff ✅ · format 186 ✅ · mypy 166 ✅ · **pytest 1757 passed, 1 skipped** · alembic
  0001→0017 + check ✅ (ცარიელ `voltbox_final_check`-ზე, შემდეგ წაიშალა) · eslint ✅ · **vitest 682 / 58** (უცვლელი) · build
  `http` ✅ · build `mock` ✅. frontend და დამოკიდებულებები არ შეცვლილა, ამიტომ `docker build` და Node 22 არ გაშვებულა.
  არ გაშვებულა: Linux-ზე სურათების დრო და მეხსიერება (გაზომვები Windows-ისაა), ნამდვილი ტელეფონის/კამერის ფაილები, ბრაუზერში
  stripped ფაილის რენდერი, e2e, Render, ლაივ ბაზა.

**`/fix A-096 A-097 A-101 A-098 A-099 A-100` 2026-11-16** (ბრენჩი `fix/a096-a101`, `agent-system`-იდან, `07466ed`). ექვსივე ID
ღია იყო; ამ რიგით გავიდა, ერთ ფაილზე ერთი აგენტი, pytest ერთდროულად მხოლოდ ერთი. მფლობელმა წინასწარ დაამტკიცა ყველა
(A-101 — ანიმაცია იკრძალება, `IMAGE_ANIMATED`); `MAX_IMAGE_DECODE_BYTES`, `DECODE_COST` და `Semaphore(1)` უცვლელია. ძველ კოდზე
ჩავარდნა ორკესტრატორმა `git stash`-ით ხელახლა გაუშვა ყველა კოდის ID-ზე.
- A-096 — fixed (verified), `e7487a4`; security-auditor — დახურულია.
- A-097 — fixed (verified), `d503a1e`; security-auditor — დახურულია.
- A-101 — fixed (verified), `da165ea` (+ Decision Log); security-auditor — დახურულია (გვერდის ავლა → A-104, nit).
- A-098 — fixed (verified), `5a31a38`; code-reviewer — დახურულია.
- A-099 — fixed (verified), `3a5aef4`; code-reviewer — დახურულია.
- A-100 — fixed (verified), `ddde89e` (Linux-ზე გაზომილი, მნიშვნელობა უცვლელი); code-reviewer — დახურულია.
- re-review-ის should-fix-ები, გასწორების რაუნდი 1: A-102 — fixed (verified), `fbb132a`; A-103-ის მცდარი კომენტარები — `72361f8`
  (მნიშვნელობა — მფლობელის); ორივე ხელახლა შემოწმდა და დახურულია.
- ღია: **A-103 (should-fix, needs decision)**, A-104–A-106 (nit) — სექციის ბოლოს. (შემდეგ გაშვებაში, `fix/a103-a106-a088-a095`:
  A-103 — accepted, A-104–A-106 — fixed; იხ. ქვემოთ.)
- პროცესის დარღვევები (არაფერს შეხებია, შედეგები ჩვეულებრივი გაშვებით გადამოწმდა): ერთ დეველოპერს ერთხელ `-p no:logging`
  ჰქონდა (ჩაშენებული plugin-ის გამორთვა), მეორემ `-p no:cacheprovider` სცადა (classifier-მა უარყო) და ერთი read-only
  `python -I -c` გაუშვა (Pillow-ის ვერსია).
- pytest: 1757 (baseline `aa98335`) → **1866 passed, 1 skipped**.
- საბოლოო შემოწმება (`72361f8`, tester): ruff ✅ · format 186 ✅ · mypy 166 ✅ · **pytest 1866 passed, 1 skipped** · alembic
  0001→0017 + check ✅ (ცარიელ `voltbox_final_check`-ზე, შემდეგ წაიშალა) · eslint ✅ · **vitest 683 / 58** (baseline 682 / 58) ·
  build `http` ✅ · build `mock` ✅ · Node 22.23.2 / npm 10.9.8 container-ში: `npm ci`, eslint, vitest 683 / 58, ორივე build ✅.
  დამოკიდებულებები და Dockerfile არ შეცვლილა (`docker build` მხოლოდ A-100-ის გაზომვისთვის აეწყო, `voltbox-api:a100`).
  არ გაშვებულა: ნამდვილი ბრაუზერი (`IMAGE_ANIMATED`-ის ტექსტი ადმინ პანელში, A-104-ის APNG), ნამდვილი ტელეფონის/კამერის
  ფაილები, Render (გაზომვა Docker Desktop-ის WSL2-ზეა), e2e, ლაივ ბაზა.

**`/auto` → `/fix A-103 A-104 A-105 A-106 A-088 A-089 A-090 A-091 A-092 A-093 A-094 A-095` 2026-11-16** (ბრენჩი
`fix/a103-a106-a088-a095`, `agent-system`-იდან, `4213a95`). ახალი აუდიტი არ გაშვებულა; მფლობელმა ყველა წინასწარ დაამტკიცა
(A-103 — ვარიანტი ბ; A-094 — `/health` 30/წთ, `/health/live` ლიმიტის გარეშე; A-088 — keyboard-ის წესიც). ამ რიგით გავიდა,
pytest ერთდროულად მხოლოდ ერთი; ძველ კოდზე ჩავარდნა ორკესტრატორმა `git stash`-ით გაიმეორა ყველა კოდის ID-ზე.
- A-103 — accepted, `f4be0ad` (PROJECT.md Accepted Risks; კოდი უცვლელი); code-reviewer — დახურულია.
- A-104 — fixed (verified), `05490ef`; security-auditor — დახურულია.
- A-105 — fixed (verified), `f9698f1` (წესი წაიშალა — AUDIT-ის პირობა არასდროს შესრულდებოდა); code-reviewer — დახურულია.
- A-106 — fixed (reviewed), `113c2e1`; code-reviewer — დახურულია.
- A-088 — fixed (verified), `218847b` (+ Decision Log); security-auditor — დახურულია.
- **A-089 — გამოტოვებულია:** მხოლოდ frontend-ს ეხება (backend `details`-ს უკვე აბრუნებს), მფლობელის პირობით. ღიაა.
- A-090 — fixed (verified), `9c5db85` (mutation-ით); code-reviewer — დახურულია.
- A-091 — fixed (reviewed), `12b97dc`; A-092 — fixed (reviewed), `c189273`; A-093 — fixed (reviewed), `5a508a9` (backend-ის
  ტესტის კომენტარია, backend-dev-მა გაასწორა); code-reviewer — სამივე დახურულია.
- A-094 — fixed (verified), `dc98253` (+ Decision Log); security-auditor — დახურულია.
- A-095 — fixed (verified), `b9795e0`; code-reviewer — დახურულია.
- re-review: 0 critical / 0 should-fix. nit-ები ამ ბრენჩის საკუთარ ტექსტში (Pillow-ის `acTL` მექანიზმის აღწერა, A-103-ის
  კომენტარი, ტესტის სახელი, §10-ის 2 → 4–5 მოთხოვნა და `curl -4`) — გასწორდა, `2920c30`.
- ღიად დარჩა: A-089 (nit, frontend); A-094-ის „შესამოწმებელი" (slowapi-ის Redis hit-ს ჩვენი socket timeout არ აქვს;
  `/health`-იც ახლა Redis-ს ეხება, `/health/live` — არა).
- pytest: 1866 (baseline `72361f8`) → **1970 passed, 1 skipped**.
- საბოლოო შემოწმება (`2920c30`, tester): ruff ✅ · format 186 ✅ · mypy 166 ✅ · **pytest 1970 passed, 1 skipped** · alembic
  0001→0017 + check ✅ (ცარიელ `voltbox_final_check`-ზე, შემდეგ წაიშალა) · eslint ✅ · **vitest 683 / 58** (baseline-ის
  ტოლი; frontend არ შეცვლილა) · build `http` ✅ · build `mock` ✅. დამოკიდებულებები და Dockerfile არ შეცვლილა, image არ აწყობილა.
  არ გაშვებულა: ნამდვილი ბრაუზერი (APNG-ის ჩვენება), §10-ის პროცედურა ცოცხალზე, Render, e2e, ლაივ ბაზა.

**`/auto` → `/fix A-089 A-049 A-047 A-050 A-052 A-053 A-054 A-064 A-082` 2026-11-17** (ბრენჩი
`fix/a089-a049-a047-a050-a082`, `agent-system`-იდან, `58211a5`). ახალი აუდიტი არ გაშვებულა; მფლობელმა ყველა წინასწარ
დაამტკიცა. ცხრავე ღია იყო; A-050-ის ოთხივე შეუსაბამობა ჯერ კიდევ არსებობდა. ძველ კოდზე ჩავარდნა ორკესტრატორმა
`git stash`-ით გაიმეორა კოდის ყველა ID-ზე; pytest ერთდროულად მხოლოდ ერთი.
- A-089 — fixed (verified), `a4763f3`; security-auditor + code-reviewer — დახურულია.
- A-049 — fixed (verified), `3b0e283`; code-reviewer — დახურულია.
- A-047 — fixed (verified), `e63ac33` (+ Decision Log, CLAUDE.md); code-reviewer — დახურულია. gzip, ცვლილებამდე → შემდეგ:
  | chunk | http | mock |
  |---|---|---|
  | constants (entry, ყველა გვერდზე) | 22.92 → 12.97 | 22.89 → 12.94 |
  | en (ახალი, მხოლოდ `/en`) | — → 9.01 | — → 9.01 |
  | index | 20.61 → 20.04 | 35.24 → 34.63 |
  | adminApi (lazy) | 0.70 → 2.38 | — |
  | vendor / icons | 89.04 / 5.88 (უცვლელი) | 88.85 / 4.60 (უცვლელი) |
  `/`-ის საწყისი JS ≈ −10.5 kB gzip ორივე რეჟიმში; `/en` ≈ −1.5 kB (ინგლისური ცალკე მოთხოვნაა, A-109).
- A-050 — fixed (reviewed), `43dffb4`; A-052 — fixed (reviewed), `efd3525`; A-053 — fixed (verified), `bfc457d`;
  A-054 — fixed (verified), `bca370f`; A-064 — fixed (verified), `0c42877`; A-082 — fixed (verified), `737c83c`;
  code-reviewer — ყველა დახურულია.
- re-review-ის nit-ები ამ ბრენჩის საკუთარ ტექსტში/ტესტებში — გასწორდა იმავე commit-ებში. ახალი: A-107, A-108 (დაუდასტურებელი),
  A-109 (nit-ები) და **A-110 (should-fix, ჩვენამდეც ასე იყო, ამ ბრენჩის ფარგლებს სცდება — ღიაა)**.
- **vitest-ის ჩავარდნა პარალელური pytest-ისას** (მფლობელის დამატებითი პუნქტი) — `482d353` (+ Decision Log). ჩუმ მანქანაზე
  5/5 ზედიზედ მწვანე; დატვირთვაზე (სამი ნაკრები ერთად) გამეორდა: HomeHero 6-დან 2-ში, Register / catalogNames / BrandList
  თითოჯერ — ყველა `testTimeout` 5 s-ის ან `findBy*`-ის 1 s-ის ამოწურვა. გასწორდა ზედმეტი ხარჯი (HomeHero-ს per-test
  `resetModules`, userEvent-ის keystroke delay, ერთი რეალური debounce, lazy გვერდების preload) და ლოდინი დატვირთვაზე
  გაიზომა (`testTimeout` 15 s, `asyncUtilTimeout` 3 s). შემდეგ: 6/6 ნაკრები მწვანე backend-ის სრულ pytest-თან ერთად.
- პროცესის დარღვევები (არაფერს შეხებია): ერთმა backend-dev-მა ერთხელ ცარიელი heredoc გაუშვა (`cat >/dev/null`); ორი
  frontend-dev ერთ ფაილზე (`httpClient.js`) ერთდროულად მუშაობდა — ორკესტრატორის შეცდომა, შედეგი ხელახლა გადამოწმდა.
- pytest: 1970 (baseline `58211a5`) → **1976 passed, 1 skipped**; vitest 683 / 58 → **775 / 69**, `act()` 25 → 0.
- საბოლოო შემოწმება (`482d353`, tester + ორკესტრატორი): ruff ✅ · format 188 ✅ · mypy 168 ✅ · **pytest 1976 passed,
  1 skipped** · alembic 0001→0017 + check ✅ (ცარიელ `voltbox_final_check`-ზე, შემდეგ წაიშალა) · eslint ✅ · **vitest 775 / 69**,
  0 `act()` · build `http` ✅ · build `mock` ✅ · Node 22.23.2 / npm 10.9.8 container-ში (`git archive HEAD frontend backend`):
  `npm ci`, eslint, vitest 775 / 69, ორივე build ✅. დამოკიდებულებები და Dockerfile არ შეცვლილა.
  არ გაშვებულა: ნამდვილი ბრაუზერი (`/en`-ის ჩატვირთვა, ველის შეცდომების ჩვენება, ადმინის შეცდომის ტექსტები), e2e, Render,
  ლაივ ბაზა.

### Should-fix

#### A-030 · should-fix · refresh-ის 429 ან 5xx პასუხი მომხმარებელს სისტემიდან აგდებს
- **ფაილი:** `frontend/src/services/session.js:224-227`
- **სცენარი:** `POST /auth/refresh`-ის ნებისმიერ არა-2xx პასუხზე კოდი იძახებს `endSession()`-ს. ქსელის შეცდომაზე კი
  (`:218-222`) სესია განზრახ რჩება. დროებითი vitest ტესტით: 429, 500, 502 და 503 — ოთხივეზე შენახული სესია `null` გახდა
  და `sessionLost` handler გამოიძახა (login-ზე გადამისამართება). სერვერი ერთი IP-დან წუთში მეექვსე refresh-ს 429-ით
  პასუხობს (გაზომილია, იხ. A-031). საერთო NAT-ის უკან მყოფ მომხმარებლებზე ან deploy-ის / ბაზის ხანმოკლე გათიშვისას
  ეს ჩვეულებრივ გამოყენებაში ჩნდება.
- **შედეგი:** სესია უმიზეზოდ იკარგება, კალათის სინქრონიზაცია ნახევრად სრულდება.
- **გამოსწორება:** სესია დასრულდეს მხოლოდ 401-ზე (და 403-ზე, თუ `routes/auth.py`-ის refresh მას აბრუნებს). 429 და 5xx →
  `return null` სესიის წაშლისა და გადამისამართების გარეშე, როგორც ქსელის შეცდომისას. ტესტები: 401 → სესია იშლება;
  429/500/502/503 → სესია რჩება, `sessionLost` არ იძახება (სტილი: `src/services/sessionLost.test.js`).
- **owner:** frontend-dev
- **status:** fixed (verified) — `1880bcc` (re-review: code-reviewer)

#### A-031 · should-fix · `/auth/refresh` იზიარებს login-ის 5/წთ ლიმიტს
- **ფაილი:** `backend/app/core/rate_limit.py:47` (`AUTH_RATE_LIMIT = "5/minute"`), `backend/app/api/v1/routes/auth.py`
  (refresh-ის `@limiter.limit(AUTH_RATE_LIMIT)`)
- **სცენარი:** ერთი IP-დან 7 ზედიზედ refresh: 1–5 → 401, 6–7 → 429 (გაზომილია). login-ისთვის 5/წთ გამართლებულია
  (brute force), refresh-ისთვის კი არა: მას `HttpOnly; SameSite=strict; Path=/api/v1/auth` cookie სჭირდება.
  ერთი ოფისიდან ან მობილური ოპერატორის CGNAT-იდან რამდენიმე მომხმარებელი, რომელთა access token ერთდროულად იწურება,
  ამ ზღვარს აღწევს. A-030-თან ერთად ეს logout-ია.
- **შედეგი:** ლეგიტიმური მომხმარებლები 429-ს იღებენ.
- **გამოსწორება:** ცალკე `REFRESH_RATE_LIMIT = "30/minute"` refresh-ის route-ზე; მიზეზი კომენტარში და Decision Log-ში
  (რა რჩება ძალაში: login/register/reset 5/წთ). ტესტი: 30 refresh გადის, 31-ე → 429.
- **owner:** backend-dev
- **status:** fixed (verified) — `6ed1119` (re-review: security-auditor)

#### A-032 · should-fix · PNG-ის ატვირთვა event loop-ს 6.5–8.2 წამით ბლოკავს
- **ფაილი:** `backend/app/services/storage.py:335` (`image.save(buffer, format="PNG", optimize=True)`);
  `backend/app/services/admin_image.py:63`, `:76` (`validate_image`, `shrink_to_fit` სინქრონულად, event loop-ზე)
- **სცენარი:** გაზომილია სრულ CPU ბირთვზე, `shrink_to_fit` პირდაპირ:
  - JPEG 4000×3000 — 0.2 წმ;
  - PNG 2000×1500 (1.4 MB) — 7.5 წმ;
  - PNG 2800×2100 (2.2 MB) — 6.5 წმ;
  - PNG 2800×2100 RGBA (2.5 MB) — 8.2 წმ.
  იგივე PNG `optimize=True`-ის გარეშე 0.52 წმ-ში ინახება (980 KB-ის ნაცვლად 1080 KB). Render-ის 0.5 CPU-ზე დრო დაახლ.
  ორმაგდება და ამ ხნის განმავლობაში worker სხვა მოთხოვნებს ვერ ემსახურება. gunicorn-ზე `timeout=5`-ით ატვირთვამ
  worker-ი მოკლა (`WORKER TIMEOUT` + `SIGABRT`, კლიენტმა კავშირის გაწყვეტა მიიღო). production-ის `timeout=60`-ს
  უფასო გეგმის 0.1 CPU-ზე, გათვლით, სცდება (გაზომილი არ არის).
- **შედეგი:** ადმინის ჩვეულებრივი მოქმედება (პროდუქტის PNG ფოტო) მაღაზიას ანელებს ან worker-ს კლავს.
- **გამოსწორება:**
  1. PNG-ის შენახვიდან `optimize=True` მოიხსნას (ნაგულისხმევი `compress_level`).
  2. CPU-ის სამუშაო (`validate_image`, `shrink_to_fit`, A-033-ის ცვლილებები) გადავიდეს `asyncio.to_thread`-ში
     `asyncio.Semaphore(1)`-ის უკან — იგივე ნიმუშით, რაც `backend/app/core/security.py:71`, `:81` (Argon2).
     მეხსიერების ზღვარი და `DECODE_COST`-ის ლოგიკა არ იცვლება; `TestDecodeMemoryIsBounded` უნდა გადიოდეს.
  3. ტესტები: PNG-ის შენახვის გზა `optimize`-ს აღარ იყენებს; დამუშავება event loop-ის გარეთ ხდება.
- **owner:** backend-dev
- **status:** fixed (verified) — `e903dcd` (re-review: code-reviewer)

#### A-033 · should-fix · ტელეფონის ფოტო გადაბრუნებული ინახება; პატარა ფოტოს GPS საჯარო bucket-ში ხვდება
- **ფაილი:** `backend/app/services/storage.py:313-342` (`shrink_to_fit`)
- **სცენარი (გაშვებით):**
  - JPEG 4000×3000, `Orientation=6` (ტელეფონზე ვერტიკალური 3000×4000) → შეინახა 1600×1200, ორიენტაციის ნიშნის გარეშე.
    `ImageOps.exif_transpose` არსად გამოიძახება, `thumbnail` კი EXIF-ს აგდებს. ფოტო საიტზე გვერდზე გადაბრუნებული ჩანს.
  - JPEG 1200×900 GPS-ით და `Make`-ით → დაბრუნდა ბაიტ-ბაიტ უცვლელი (`:328-329` — „fits → return data“).
    GPS კოორდინატები და მოწყობილობის მონაცემი საჯარო `product-images` bucket-ში ხვდება.
- **შედეგი:** არასწორი შედეგი ჩვეულებრივ გამოყენებაში; ადმინის / მომწოდებლის ლოკაციის გაჟონვა.
- **გამოსწორება:**
  1. ორიენტაცია: `thumbnail`-მდე `ImageOps.exif_transpose`. თუ ფოტო ზომაში ეტევა, მაგრამ `Orientation ≠ 1`, ხელახლა
     შენახვა საჭიროა.
  2. მეტამონაცემები (EXIF, GPS, XMP, IPTC) მოშორდეს **ყველა** ფაილს, პატარასაც. ეს ცვლის `:315-318`-ის docstring-ის
     გადაწყვეტილებას („small image left untouched“) — ახალი მიზეზი Decision Log-ში. სადაც შესაძლებელია,
     ხარისხის დაკარგვის გარეშე (JPEG-ის APP1/APP13 სეგმენტები, PNG-ის `eXIf`/`tEXt`/`iTXt`/`zTXt` chunk-ები, WEBP-ის
     EXIF/XMP chunk-ები); ICC profile რჩება.
  3. ტესტები: `Orientation=6` → შენახული სურათი ვერტიკალურია და `Orientation` აღარ აქვს; GPS-იანი 1200×900 JPEG →
     შენახულში არც GPS IFD არის, არც `Make`; არსებული სურათების ტესტები გადის.
- **owner:** backend-dev
- **status:** fixed (verified) — `6469e57` (re-review: security-auditor). bucket-ში უკვე შენახული ფოტოები — A-062.

#### A-034 · should-fix · დაუმუშავებელი შეცდომისას მომხმარებლის ელფოსტა ლოგში scrub-ის გარეშე იწერება
- **ფაილი:** `backend/app/core/logging.py:24-35` (`scrub`, `PG_DETAIL_VALUE`), `backend/gunicorn.conf.py:30-31`
- **სცენარი (გაშვებით, gunicorn, 2 worker, Redis):** ერთი ელფოსტით ორი ერთდროული `POST /auth/register` → `[201, 500]`
  (A-039). JSON ხაზში მნიშვნელობა გაწმენდილია (`Key (email)=(…)`). მაგრამ Starlette 500-ის შემდეგ გამონაკლისს
  ხელახლა ისვრის და uvicorn მას `Exception in ASGI application`-ით `uvicorn.error` logger-ში წერს, scrub-ის გარეშე.
  ლოგში ელფოსტა სამჯერ ჩაიწერა: `DETAIL: Key (email)=(pii-leak-probe-94bef7@example.com) already exists.`
  იგივე ხდება `addresses`-ის `user_id`-ზე (A-040): 6 ერთდროული მოთხოვნის 3 რაუნდში 11 გაუწმენდავი traceback.
- **შედეგი:** PII ჰოსტინგის ლოგში ხვდება — `logging.py`-ის დოკუმენტირებული წესის საწინააღმდეგოდ.
- **გამოსწორება:** scrub-ის ფილტრი მიება `uvicorn.error`-ისა და `gunicorn.error`-ის handler-ებს (ან ორივე
  გადავიდეს იმავე JSON handler-ზე), ისე რომ Postgres-ის `DETAIL` მნიშვნელობა ლოგის არცერთ ხაზში არ მოხვდეს.
  ტესტი: `uvicorn.error`-ში დაწერილი ჩანაწერი, რომელიც `Key (email)=(x@y.com)`-ს შეიცავს, გამოსავალში `x@y.com`-ის
  გარეშე ჩნდება. A-039 და A-040 ამ 500-ებს აქრობს, ეს კი იცავს ყველა მომავალ შემთხვევას.
- **owner:** backend-dev
- **status:** fixed (verified) — `b530418` (re-review: security-auditor). `configure_logging()` `uvicorn`, `uvicorn.error`
  და `gunicorn.error`-ს root JSON handler-ზე გადაიყვანს; `JsonFormatter` message-ს და `exc_text`-საც ასუფთავებს. 12 ახალი
  ტესტი (`tests/test_server_log_secrecy.py`, UvicornWorker-ის და uvicorn dev-ის wiring `configure_logging()`-მდე) ძველ
  `logging.py`-ზე ვარდება — გამოსავალში ელფოსტაა, ახალზე გადის. რეალური gunicorn-ით გაშვებული არ არის (Windows).
  **ნარჩენი:** `scrub` მხოლოდ `Key (…)=(…)`-ს იცნობს — `Failing row contains (…)` (NOT NULL/CHECK) ისევ გაუწმენდავია → A-067.

#### A-035 · should-fix · lock-ებში ცნობილი სისუსტეა (dnspython 2.8.0) — CI-ის `pip-audit` ისევ წითელია
- **ფაილი:** `backend/requirements.txt:248`, `backend/requirements-dev.txt:327` (`dnspython==2.8.0`, via `email-validator`)
- **სცენარი:** `pip-audit --strict --disable-pip -r requirements.txt -r requirements-dev.txt -r requirements-build.txt`
  → exit 1: **CVE-2026-114605** (GHSA-45c3-73f7-pv4m), fix 2.9.0. სისუსტე DNS პასუხის დეკომპრესიაშია (CPU DoS).
  აპლიკაცია DNS-ს არ იყენებს: pydantic `email_validator`-ს `check_deliverability=False`-ით იძახებს, `app/`-ში `dns`
  არსად ჩანს. ამიტომ რეალური რისკი დაბალია. მაგრამ `.github/workflows/backend.yml`-ის audit step `--strict`-ით
  ეშვება, ამიტომ backend-ის ყოველი შემდეგი push / PR წითელია (იგივე სიტუაცია, რაც A-001-ში).
- **შედეგი:** CI-ის უსაფრთხოების კარიბჭე წითელია.
- **გამოსწორება:** მხოლოდ `dnspython` → 2.9.0 ორივე lock-ში, Linux container-ში, `--upgrade-package dnspython`-ით
  (`backend/README.md`, „დამოკიდებულებების lock“). სხვა პაკეტი არ იცვლება; Dependabot-ის ჯგუფურ PR-ს
  (34 განახლება) არ ვეხებით. შემოწმება: `pip install --require-hashes` + `pip check`, pip-audit-ის CI-ის ფორმა = 0,
  `docker build`, pytest.
- **owner:** backend-dev
- **status:** fixed (verified) — `5d62944` (re-review: code-reviewer)

#### A-036 · should-fix · rate limit-ის IP წყარო (`FORWARDED_ALLOW_IPS`) production-ში გადაუმოწმებელია და ლოგით ვერ მოწმდება
- **ფაილი:** `backend/app/core/logging.py:71-113` (access log), `backend/gunicorn.conf.py`; `PROGRESS.md`-ის Backlog
  („`FORWARDED_ALLOW_IPS` value on Render — if wrong, all clients share one bucket“)
- **სცენარი:** ყველა ლიმიტი (`ORDER_RATE_LIMIT` 5/წთ;30/დღე, auth 5/წთ) კლიენტის IP-ზეა. `gunicorn.conf.py` მხოლოდ
  ცარიელ მნიშვნელობასა და `*`-ს უარყოფს. თუ მნიშვნელობა არასწორია, ყველა მყიდველი Render-ის proxy-ის IP-ით ჩანს და
  მთელ მაღაზიას ერთი bucket რჩება (30 შეკვეთა დღეში). access log კი კლიენტის არანაირ იდენტიფიკატორს არ წერს, ამიტომ
  ამის გადამოწმება ლოგიდან შეუძლებელია.
- **შედეგი:** შესაძლო გათიშვა პირველივე დატვირთვაზე, რომელიც ვერ დიაგნოსტირდება.
- **გამოსწორება:**
  1. access log-ს დაემატოს `client`: `sha256(salt + request.client.host)`-ის პირველი 12 სიმბოლო. salt
     `JWT_SECRET`-იდან HMAC-ით მიიღება, ნედლი IP არსად ინახება.
  2. `docs/deployment.md`-ს დაემატოს შემოწმების პროცედურა: deploy-ის შემდეგ ორი ქსელიდან (Wi-Fi და მობილური)
     `curl`-ით `GET /api/v1/health/live` → ლოგში ორი განსხვავებული `client` უნდა ჩანდეს.
  3. Render-ზე შემოწმება მფლობელისაა → `## Blockers`. ამ ჩანაწერის status: `fixed (reviewed)` + „owner check pending“.
- **owner:** backend-dev
- **status:** fixed (reviewed) — **owner check pending** (Render, PROGRESS.md Blockers). კოდი გაზომილია: `31c2427` + `e2d60a6`.
  `client` = HMAC(HMAC(JWT_SECRET, label), IP)[:12]; gunicorn-ის `accesslog = None` (UvicornWorker-ით ის ნედლ IP-ს ბეჭდავდა).
  re-review-მ (security-auditor) იპოვა, რომ slowapi-ის 429-ის WARNING ნედლ IP-ს წერდა — image-ზე გაზომილი
  `ratelimit 5 per 1 minute (172.17.0.1) …`; `e2d60a6`-ის შემდეგ `(edd9ef059bf8)`, იგივე, რაც access line-ის `client`, და
  container-ის ლოგში IP აღარ არის. 9 + 14 ახალი ტესტი ძველ კოდზე ვარდება. docs/deployment.md §10 — ორი ქსელის შემოწმება.

#### A-037 · should-fix · ადმინის ანგარიშს მხოლოდ სუსტი პაროლის წესი იცავს; დაბლოკვა შეუმჩნეველია
- **ფაილი:** `backend/app/core/security.py:29` (`COMMON_PASSWORDS`, 17 ჩანაწერი), `:50` (`MIN_PASSWORD_LENGTH = 8`);
  `backend/app/core/config.py:117` (`max_failed_logins = 10`); `backend/scripts/manage_admin.py:36-50`
- **სცენარი:** ადმინი შედის იმავე `/auth/login`-ით, მეორე ფაქტორის გარეშე; პანელი ყველა მყიდველის სახელს, ტელეფონს,
  მისამართსა და შეკვეთებს აჩვენებს. ახალი პაროლის ვალიდაციამ მიიღო `aaaaaaaa`, `12345678a`, `qwertyuiop`,
  `Password1!` (გაშვებით). 10 არასწორი ცდა ანგარიშს 15 წუთით კეტავს — ვინც ადმინის ელფოსტა იცის, პანელს
  დაკეტილს შეინარჩუნებს და ამას არავინ შეამჩნევს.
- **შედეგი:** ადმინის ანგარიშის ხელში ჩაგდება = ყველა მომხმარებლის PII.
- **გამოსწორება (ამ ID-ში — TOTP-ის გარეშე; TOTP ცალკე stage-ია):**
  1. ახალი პაროლის წესი ყველასთვის: ერთი სიმბოლოს გამეორება და მარტივი მიმდევრობები (`12345678`, `abcdefgh`,
     `qwertyui`) იკრძალება; გავრცელებული პაროლების სია ≥ 10 000 ჩანაწერი, ოფლაინ, მონაცემთა ფაილად (ახალი
     dependency-ის გარეშე; წყარო და ლიცენზია Decision Log-ში).
  2. ადმინის როლზე მინიმუმ 12 სიმბოლო (`manage_admin.py`, change-password, reset).
  3. არსებული პაროლები აგრძელებს მუშაობას — წესი მხოლოდ ახალი პაროლის დაყენებისას მოქმედებს.
  4. ადმინის ანგარიშის დაბლოკვისას შეტყობინება Telegram-ში არსებული `app/services/telegram.py`-ით
     (ელფოსტა ნიღბით, IP-ის გარეშე).
  5. ტესტები ოთხივე პუნქტზე.
- **owner:** backend-dev
- **status:** fixed (verified) — `e09ce2e` + `85bb546` (2026-11-16, TOTP-ის გარეშე). სია: SecLists 10k (MIT, `913b327`),
  `backend/app/core/common_passwords.txt` + NOTICE, sha256 ტესტით; image-ში შემოწმდა. pattern: 3-სიმბოლოიანი
  გამეორება/±1/კლავიატურის რიგი იშლება, < 5 განსხვავებული → უარი. ადმინი 12 (`ADMIN_PASSWORD_TOO_SHORT`),
  login წესს არ ამოწმებს (ძველი სუსტი პაროლი შედის — ტესტი). დაბლოკვაზე ერთი Telegram (`b***@domain`, IP-ის გარეშე),
  `AppError.after_response`-ით. ძველ კოდზე: 25 ტესტი ვარდება + `test_password_policy.py` import-ზე. re-review
  (security-auditor): should-fix — reset-ის გვერდი ადმინს „ძალიან მარტივია“-ს აჩვენებდა → რაუნდი 1/2, `85bb546`
  (ტესტი ძველ გვერდზე ვარდება); მეორე re-review — დახურულია. ნარჩენი nit-ები: A-088, A-089.

### Nit

#### A-038 · nit · უზარმაზარი `page` საჯარო endpoint-ზე 500-ს აბრუნებს
- **ფაილი:** `backend/app/core/pagination.py:22` (`page: int = Field(default=1, ge=1)`) და ყველა სხვა `page` პარამეტრი
- **სცენარი:** `GET /api/v1/products?page=9223372036854775807` (ავტორიზაციის გარეშე) → 500, asyncpg:
  `value out of int64 range` (OFFSET). იგივე `GET /admin/orders`-ზე.
- **გამოსწორება:** `le=10_000` ყველა `page`-ზე → 400 `VALIDATION_ERROR`. ტესტი: 10 000 გადის, 10 001 → 400.
- **owner:** backend-dev
- **status:** fixed (verified) — `069f8b1` (re-review: code-reviewer). საერთო `MAX_PAGE = 10_000` (`core/pagination.py`)
  ექვსივე route-ზე, სადაც `page` შედის (საჯარო `/products`, admin products/orders/customers/inventory/movements), და
  `PageParams`/`page_params`-ზეც. 25 ტესტიდან 18 ძველ route-ებზე ვარდება (10 001, 2⁶³−1, 2⁶³ × 6 route; ორკესტრატორმაც
  გაუშვა `git stash`-ით). reviewer: მომხმარებლის input-იდან offset სხვაგან არ ითვლება; `/search`-ის offset-ს მომხმარებელი
  ვერ აკონტროლებს.

#### A-039 · nit · ერთი ელფოსტით ერთდროული რეგისტრაცია 409-ის ნაცვლად 500-ს აბრუნებს
- **ფაილი:** `backend/app/services/auth.py:79-88` (ჯერ SELECT, მერე INSERT); შეამოწმე `:698`-ის მსგავსი გზაც
- **სცენარი:** gunicorn, 2 worker: `[201, 500]`. მეორე მოთხოვნა unique constraint-ზე ვარდება. იწვევს A-034-ს.
- **გამოსწორება:** ამ constraint-ის `IntegrityError` → იგივე `EMAIL_ALREADY_EXISTS` (409); SELECT რჩება.
  ტესტი ნამდვილ ბაზაზე, `asyncio.gather`-ით: `[201, 409]`.
- **owner:** backend-dev
- **status:** fixed (verified) — `227ad5d` (re-review: code-reviewer). მხოლოდ `uq_users_email`-ის `IntegrityError` →
  `EMAIL_ALREADY_EXISTS` (409), `register`-შიც და `update_profile`-ის email-ის შეცვლაზეც (იგივე race). 2 race-ტესტი
  ნამდვილ ბაზაზე, ფიქსირებული interleaving-ით (`_contend` + `_until_queued_behind`): ძველ კოდზე
  `[('ok','committed'), ('error','IntegrityError')]`, ახალზე `[('ok','committed'), ('conflict','EMAIL_ALREADY_EXISTS')]`
  (ორკესტრატორმაც გაუშვა `git stash`-ით). HTTP-ის დონეზე gunicorn-ით არ გაშვებულა.

#### A-040 · nit · ერთდროული „ძირითადი მისამართის“ შექმნა 500-ს აბრუნებს
- **ფაილი:** `backend/app/services/address.py:55-80` (`_clear_other_defaults`, `create`);
  `uq_addresses_one_default_per_user` (`backend/app/db/models/users.py:111`)
- **სცენარი:** 6 ერთდროული `POST /addresses` `isDefault: true`-ით, 3 რაუნდი → 18-დან 11 იყო 500. ორი ტრანზაქცია
  ერთდროულად ასუფთავებს ძველ default-ს და ორივე ახალს წერს — partial unique index-ზე ვარდება. იწვევს A-034-ს.
- **გამოსწორება:** `_clear_other_defaults`-მდე მომხმარებლის რიგის lock (`SELECT ... FROM users WHERE id = :id FOR UPDATE`)
  იმავე ტრანზაქციაში; იგივე update-ის გზაზეც. ტესტი: 4 ერთდროული → არცერთი 500, ბოლოს ზუსტად ერთი default.
- **owner:** backend-dev
- **status:** fixed (verified) — `a18e3ff` (re-review: code-reviewer). `_lock_default_writes`: მფლობელის `users` რიგი
  `FOR NO KEY UPDATE`-ით (იგივე დონე, რასაც `auth.py` იღებს; FK-ის `KEY SHARE`-ს არ ბლოკავს), `create`-ში მხოლოდ default-ზე,
  `update_one`-ში ყოველთვის. დამატებით `_get_owned`/`list_for_user` — `populate_existing`: route-ზე `get_current_user`
  მისამართებს (`selectin`) lock-მდე ტვირთავს, და მოლოდინში მყოფი მოთხოვნა ძველ `is_default`-ს ხედავდა → default არ რჩებოდა.
  7 race-ტესტი ძველ `address.py`-ზე 7/7 ვარდება (ორკესტრატორი, `git stash`), ახალზე გადის.

#### A-041 · nit · მისამართების რაოდენობა შეუზღუდავია და ყველა ავტორიზებულ მოთხოვნაზე იტვირთება
- **ფაილი:** `backend/app/db/models/users.py:67-68` (`lazy="selectin"`), `backend/app/core/deps.py`,
  `backend/app/services/address.py`
- **სცენარი:** ერთმა მომხმარებელმა 55 მისამართი შექმნა (500-სიმბოლოიანი ველებით, სიის პასუხი 37 KB). მომხმარებლის
  ჩატვირთვა (`deps.py`) ასრულებს 2 SQL-ს და ყველა მისამართს მეხსიერებაში ტვირთავს — ყოველ ავტორიზებულ მოთხოვნაზე.
- **გამოსწორება:**
  1. ლიმიტი 20 მისამართი მომხმარებელზე; გადაჭარბება → 409 `ADDRESS_LIMIT_REACHED`, ტექსტი
     `frontend/src/i18n/ka.json`-სა და `en.json`-ში.
  2. `lazy="selectin"` → `lazy="raise"` (ან `noload`); მისამართები ჩაიტვირთოს მხოლოდ იქ, სადაც საჭიროა, explicit
     `selectinload`-ით. ჯერ `user.addresses`-ის ყველა გამოყენება მოიძებნოს.
  3. ტესტები: 20 გადის, 21-ე → 409; `GET /auth/me` ზუსტად 1 SQL-ს ასრულებს (`before_cursor_execute` listener).
- **owner:** backend-dev
- **status:** fixed (verified) — `91420c3` (re-review: code-reviewer). `MAX_ADDRESSES_PER_USER = 20`; `create` ყოველთვის
  იღებს `_lock_default_writes`-ს და lock-ის შემდეგ ითვლის, ამიტომ ერთდროული create-ები ლიმიტს ვერ გადააჭარბებს (race-ტესტი
  19-ზე და 5-იანი burst). `User.addresses` — `lazy="raise"`, `passive_deletes=True` (FK `ON DELETE CASCADE`); სხვაგან
  `user.addresses` მხოლოდ `admin_customers`-შია, `selectinload`-ით. A-040-ის lock-ის დონე და `populate_existing` უცვლელია;
  A-040-ის `_moving` helper-ი მისამართებს ახლა explicit-ად ტვირთავს, რომ მისი წინაპირობა შენარჩუნდეს. `GET /auth/me`:
  ძველ მოდელზე 2 statement, ახალზე 1 (ორკესტრატორმა გაუშვა `git stash`-ით). ლიმიტის ტესტების ძველ კოდზე ჩავარდნა
  (5 ტესტი) დეველოპერმა აჩვენა — HEAD-ის `address.py` + მხოლოდ კონსტანტა; ორკესტრატორს ეს ნაწილი არ გაუმეორებია.
  storefront 409-ის ტექსტს `apiErrors.<code>`-ით აჩვენებს (`Addresses.jsx`-ის toast). ნარჩენი ზედმეტი 409 (უკომიტო delete-ის
  დროს დათვლა) A-071-მა მოხსნა.

#### A-042 · nit · იმავე Idempotency-Key-ით სხვა კალათა ჩუმად ძველ შეკვეთას აბრუნებს
- **ფაილი:** `backend/app/services/order.py:50` (`uq_orders_idempotency_key`), `:131` (`IDEMPOTENCY_KEY_CONFLICT`)
- **სცენარი:** სტუმრის შეკვეთა qty 1 → 201. იმავე გასაღებით და იმავე კონტაქტით, მაგრამ qty 5 → 201 და ძველი შეკვეთა
  qty 1-ით. კლიენტი ფიქრობს, რომ 5 ცალი შეუკვეთა. სხვა კონტაქტით იმავე გასაღებზე 409 სწორად ბრუნდება.
- **გამოსწორება:**
  1. შეკვეთაზე `request_hash` (sha256 კანონიკური JSON-იდან: დალაგებული items, customer, paymentMethod).
     migration `0017`, nullable სვეტი (ახალი ცხრილი არ არის → RLS არ სჭირდება).
  2. იგივე გასაღები + სხვა hash → 409 `IDEMPOTENCY_KEY_REUSED` (ტექსტი ka/en); იგივე hash → არსებული ქცევა;
     hash-ის გარეშე (ძველი) შეკვეთა → შემოწმება გამოტოვდება.
  3. ლაივ migration მხოლოდ `alembic upgrade 0016:0017 --sql`-ით (`public.`-ით), მფლობელისთვის `## Blockers`-ში.
  4. ტესტები სამივე შემთხვევაზე; `alembic upgrade head` + `alembic check`.
- **owner:** backend-dev
- **status:** fixed (verified) — `ec0c98f` (re-review: security-auditor — დახურულია). migration 0017: `orders.request_hash`
  `VARCHAR(64)` nullable, index-ის და backfill-ის გარეშე. hash = SHA-256 კანონიკური JSON-იდან (გაერთიანებული რაოდენობები
  product id-ით, ვალიდირებული customer — email/phone `owns_order`-ის ნორმალიზებით, paymentMethod). `_replay`-ში ჯერ
  მფლობელობა (უცხოს — `IDEMPOTENCY_KEY_CONFLICT`, oracle არ არის), მერე hash → `IDEMPOTENCY_KEY_REUSED`; ორივე გზაზე (pre-check
  და unique-index clash). 18 ახალი ტესტიდან 10 ძველ `order.py`-ზე ვარდება (ორკესტრატორმა `git stash`-ით გაუშვა). alembic
  upgrade head + check სუფთა scratch ბაზაზე. ლაივისთვის SQL: `docs/migrations/0017_orders_request_hash.sql`, PROGRESS.md
  `## Blockers` — **deploy-მდე**. auditor-ის nit → A-076.

#### A-043 · nit · შეკვეთის ნომრის თარიღი UTC-ია, არა თბილისის
- **ფაილი:** `backend/app/services/order.py:76` (`to_char(now(), 'YYYYMMDD')`)
- **სცენარი:** ბაზის დროის სარტყელი UTC-ია, ამიტომ თბილისის დროით 00:00–04:00 შორის მიღებული შეკვეთა წინა დღის
  თარიღს იღებს (`VB-YYYYMMDD-…`).
- **გამოსწორება:** `to_char(now() AT TIME ZONE 'Asia/Tbilisi', 'YYYYMMDD')`. ტესტი: SQL-ის დონეზე, დროის სარტყლით.
- **owner:** backend-dev
- **status:** fixed (verified) — `0765bb8` (re-review: code-reviewer — დახურულია). ტესტი სესიის სარტყელს UTC+14-სა და
  UTC−12-ზე აყენებს ერთ ტრანზაქციაში (26 საათი → ძველი გამოსახულება ნებისმიერ მომენტში ორ თარიღს იძლევა); 4-დან 2 ძველ
  კოდზე ვარდება (ორკესტრატორმა `git stash`-ით გაუშვა). „დამოუკიდებლობის" ტესტი ძველ კოდზე ყოველთვის ვარდება, პარამეტრიზებული
  შემთხვევები — მხოლოდ დღის ნაწილში. reviewer-ის nit → A-077.

#### A-044 · nit · `manage_admin.py` ელფოსტას არ ამოწმებს — იქმნება ადმინი, რომელიც ვერასოდეს შევა
- **ფაილი:** `backend/scripts/manage_admin.py:60-76`
- **სცენარი:** `create-admin --email audit-admin@example.test` → ადმინი შეიქმნა. `/auth/login` კი ამ ელფოსტას 400-ით
  უარყოფს (`EmailStr`-ს `.test` დომენი არ მოსწონს), ამიტომ ეს ანგარიში გამოუსადეგარია.
- **გამოსწორება:** იგივე ვალიდაცია, რაც `app/schemas/auth.py`-ში (pydantic `EmailStr` / `TypeAdapter`), სამივე
  ბრძანებაში; არავალიდურზე `SystemExit` გასაგები ტექსტით. ტესტი.
- **owner:** backend-dev
- **status:** fixed (verified) — `12b2723` (re-review: code-reviewer — დახურულია, ახალი პრობლემა არ არის). `create-admin` და
  `promote-user` — `TypeAdapter(EmailStr)` იმავე strip-ის შემდეგ, რაც login-ში; პაროლის კითხვამდე და ბაზამდე. ტესტი script-სა
  და `LoginRequest`-ს ერთსა და იმავე input-ებზე ადარებს. **გადახრა აუდიტის ტექსტიდან:** `demote-user` შეგნებულად არ ამოწმებს —
  როლის ჩამორთმევა ნებისმიერ არსებულ რიგზე უნდა მუშაობდეს, მათ შორის ამ შემოწმებამდე შექმნილ `.test`-იან ადმინზე (guard
  ტესტი). 22 ახალი ტესტიდან 18 ძველ script-ზე ვარდება (ორკესტრატორმა `git stash`-ით გაუშვა).

#### A-045 · nit · ძებნაში სიტყვების რაოდენობა შეუზღუდავია
- **ფაილი:** `backend/app/services/search.py:187`
- **სცენარი:** 100 ერთასოიანი სიტყვა → 89 მწმ (`/search`), 116 მწმ (`/products?q=`); ჩვეულებრივი ძებნა — 14 მწმ
  (61 პროდუქტზე). სხვაობა კატალოგთან ერთად იზრდება; endpoint საჯაროა.
- **გამოსწორება:** მაქსიმუმ 8 token (stopword-ების შემდეგ), დანარჩენი ჩუმად იკვეთება. ტესტი.
- **owner:** backend-dev
- **status:** fixed (verified) — `c4d2217` (re-review: code-reviewer). `MAX_QUERY_TOKENS = 8`, ერთი `_parse_query` ყველა
  გზისთვის (`/search`-ის ყველა ეტაპი, typo-ს ეტაპი, layout candidate, `/products?q=`-ის count/list/facets). ლიმიტამდე
  ნორმალიზებული ტექსტი იგივეა, რაც ადრე. 14 ახალი ტესტიდან 8 ძველ კოდზე ვარდება (მხოლოდ import-ის shim-ით): 30-სიტყვიანი
  მოთხოვნა ბაზაში 26 განსხვავებულ სიტყვას აგზავნიდა. დრო ხელახლა არ გაზომილა. ნარჩენი: A-074.

#### A-046 · nit · პასუხის header-ების წვრილმანები
- **ფაილი:** `backend/app/core/logging.py:20`, `backend/app/core/errors.py:95`, `backend/gunicorn.conf.py`,
  `backend/app/api/v1/routes/health.py:70`
- **სცენარი (გაშვებით):**
  - პასუხს აქვს `Server: uvicorn`;
  - 308-სიმბოლოიანი `X-Request-ID`, რომელიც `<script>`-ით მთავრდება, უცვლელად ბრუნდება და ლოგში იწერება;
  - 429-ს `Retry-After` არ ახლავს;
  - `GET /health` აჩვენებს `environment`-ს.
- **გამოსწორება:** `server_header` გამოირთოს (uvicorn worker-ის კონფიგით); შემოსული `X-Request-ID` მიიღება მხოლოდ
  `^[A-Za-z0-9-]{8,64}$`-ზე, სხვა შემთხვევაში იქმნება ახალი; 429-ს `Retry-After`; `/health`-იდან `environment`
  ამოიღოს (ჯერ შემოწმდეს, ვინ კითხულობს). ტესტები.
- **owner:** backend-dev
- **status:** fixed (verified) — `65a241f`. აშენებულ image-ზე (gunicorn + `NoServerHeaderWorker`, მხოლოდ ლოკალური env):
  `server:` header არ არის; `X-Request-ID: abc<script>` → ახალი 16-hex id, `trace-12345678` რჩება (header-შიც და ლოგშიც);
  მე-6 login წუთში → 429 `retry-after: 59`; `/health` → `{"status","version","database"}`. `environment`-ს არავინ
  კითხულობდა. 22 ახალი ტესტი ძველ კოდზე ვარდება; gunicorn-ის ერთი ტესტი Windows-ზე skip-ია (Linux CI-ზე ეშვება).
  ნარჩენი: A-083 (ორ AppError 429-ს Retry-After არ აქვს); გზად ნაპოვნი A-080.

#### A-047 · nit · ორივე ენის და ადმინის ყველა ტექსტი storefront-ის საწყის bundle-შია
- **ფაილი:** `frontend/src/i18n/*`, `frontend/vite.config.js`
- **სცენარი:** `npm run build` (http): `constants-*.js` 84.75 kB (22.34 kB gzip) შეიცავს ქართულს, ინგლისურს და ადმინის
  ტექსტებს, და ყველა გვერდზე იტვირთება. საწყისი JS ჯამში ≈ 138 kB gzip.
- **გამოსწორება:** ინგლისური — მხოლოდ `/en`-ზე, ადმინის ტექსტები — ადმინის chunk-ში. build-ის ზომები ცვლილებამდე
  და შემდეგ — report-ში.
- **owner:** frontend-dev
- **status:** fixed (verified) — `e63ac33`. entry-ის `constants` 22.92 → 12.95 kB gzip (http), 22.89 → 12.92 (mock);
  `en` ცალკე chunk-ია (9.01 kB), მხოლოდ `/en`-ზე. ადმინის 38 `apiErrors` → `src/admin/i18n/ka.json`.
  `loading.test.js`-ის 6 ტესტი ძველ კოდზე ვარდება. re-review: code-reviewer — დახურულია.

#### A-048 · nit · `robots.txt` ინგლისურ პირად გვერდებს არ ფარავს
- **ფაილი:** `frontend/public/robots.txt:8-11`
- **სცენარი:** იკრძალება `/admin`, `/checkout`, `/account`, `/cart`, მაგრამ არა `/en/checkout`, `/en/account`, `/en/cart`.
- **გამოსწორება:** დაემატოს `/en/` ვარიანტები.
- **owner:** frontend-dev
- **status:** fixed (verified) — `87db0fd`. `src/robotsTxt.test.js`-ის 3 ტესტი ძველ ფაილზე ვარდება; `dist/robots.txt`-ში ხაზები
  ჩანს. re-review: code-reviewer — დახურულია. ნარჩენი: A-082 (`/en/search?`).

#### A-049 · nit · frontend-ის 9 ფაილს ტესტი საერთოდ არ აქვს; 22 `act()` გაფრთხილება
- **ფაილი:** `frontend/src/pages/Register.jsx`, `frontend/src/pages/Account/Addresses.jsx`,
  `frontend/src/components/catalog/Pagination.jsx`, `frontend/src/components/search/SearchSuggestions.jsx`,
  `frontend/src/admin/pages/{InventoryList,CustomerList,CategoryList,CustomerDetail,AdminDashboard}.jsx`
- **სცენარი:** `vitest --coverage`: ამ ფაილებზე 0% ხაზი; ჯამში ხაზები 67.5%, ფუნქციები 55.9%. `npm test`-ის
  გამოსავალში 22-ჯერ `not wrapped in act(...)` (მაგ. `ToastProvider`).
- **გამოსწორება:** ტესტები პრიორიტეტით: Register (ვალიდაცია, redirect, სერვერის შეცდომა), Addresses (CRUD, default),
  Pagination; ადმინის გვერდებზე smoke (რენდერი, ცარიელი მდგომარეობა, შეცდომა). `act()` გაფრთხილებები გასწორდეს.
- **owner:** frontend-dev
- **status:** fixed (verified) — `3b0e283`. 9-ვე ფაილს ტესტი აქვს; `act()` გაფრთხილებები 25 → 0 (ითვლება
  `vitest run --reporter=default`-ით — agent-ის shell-ში ჩვეულებრივი `npm test` გამავალი ტესტების console-ს მალავს).
  Addresses-ს edit და „set default" ღილაკი არ აქვს, ამიტომ ისინი არ მოწმდება. re-review: code-reviewer — დახურულია.

#### A-050 · nit · დოკუმენტაცია კოდს ჩამორჩება
- **ფაილი / სცენარი:**
  - `README.md:11`, `frontend/README.md:60` — „React Router 6“, `package.json` — `react-router ^7.18.4`;
  - `frontend/vite.config.js:51` — `vendor` „66.9 kB“, build-ში vendor 89.04 kB gzip;
  - `frontend/src/context/AuthContext.jsx:8` — „MOCK ONLY — replace with real auth API“ (რეალური API კარგა ხანია მუშაობს);
  - `TODO.md` №18 — „სრული e2e CI-ში არაა“, `.github/workflows/e2e.yml` კი არსებობს (განრიგით + `workflow_dispatch`).
- **გამოსწორება:** ოთხივე ადგილი სიმართლეს შეესაბამოს.
- **owner:** task-executor
- **status:** fixed (reviewed) — `43dffb4`. ოთხივე ჯერ კიდევ არსებობდა; ასევე `MOCK ONLY` Login/Register/ChangePassword-ში
  და `frontend/README.md`-ის mock-ავტორიზაციის შენიშვნა. re-review: code-reviewer — დახურულია.

#### A-051 · nit · დაუდასტურებელი შეკვეთა მარაგს უვადოდ იკავებს
- **ფაილი:** `backend/app/services/order.py`, `backend/app/services/order_status.py`
- **სცენარი (კოდით):** `pending` შეკვეთა მარაგს მაშინვე იკავებს და ავტომატურად არასოდეს ათავისუფლებს. დაცვა მხოლოდ
  IP-ლიმიტია (5/წთ; 30/დღე); სტუმრის ელფოსტა არ მოწმდება. IP-ის ცვლით შესაძლებელია პოპულარული პროდუქტის მთელი
  მარაგის „დაჯავშნა“.
- **გამოსწორება:** ბიზნეს-გადაწყვეტილებაა (ვადა, გაუქმების მექანიზმი უფასო Render-ზე cron-ის გარეშე) → Stage 4-ის
  დაგეგმვაში.
- **owner:** backend-dev
- **status:** needs decision

### Nit — A-030/A-031-ის re-review (2026-11-12)

#### A-052 · nit · `REFRESH_RATE_LIMIT`-ის კომენტარი refresh token-ს „256-bit"-ს უწოდებს
- **ფაილი:** `backend/app/core/rate_limit.py:51`
- **სცენარი (კოდით):** `backend/app/core/security.py:132` — `secrets.token_urlsafe(48)` = 384 ბიტი. რიცხვი რეალურზე
  ნაკლებია, ასე რომ დასკვნა („არანაირი სიჩქარით არ გამოიცნობა") ძალაში რჩება. `PROJECT.md`-ის Decision Log უკვე
  გასწორებულია. იქვე `:77` (სტუმრის lookup token) „256-bit"-ს ამბობს — არ შემოწმებულა.
- **გამოსწორება:** „384-bit (`token_urlsafe(48)`)".
- **owner:** backend-dev
- **status:** fixed (reviewed) — `efd3525`. `:77` (lookup token) მართლა 256-ია (`token_urlsafe(32)`); იგივე შეცდომა
  `security.py:8`-ის docstring-შიც იყო. re-review: code-reviewer — დახურულია.

#### A-053 · nit · A-030-ის ტესტი შეცდომის status-ს არ აფიქსირებს
- **ფაილი:** `frontend/src/services/sessionLost.test.js:122`
- **სცენარი (კოდით):** ტესტი მხოლოდ `error.name !== 'SessionExpiredError'`-ს ამოწმებს. `AdminSessionContext.jsx:50`
  „unreachable" ეკრანს მხოლოდ არა-401 შეცდომაზე აჩვენებს; თუ `ApiError(..., 0)` ოდესმე 401-იანი შეცდომით
  შეიცვლება, ტესტი გაივლის, ადმინი კი refresh-ის 503-ზე login-ზე გადავა.
- **გამოსწორება:** `expect(error).toMatchObject({ name: 'ApiError', status: 0 })`.
- **owner:** frontend-dev
- **status:** fixed (verified) — `bfc457d`. throw-ის status 401-ზე → 4-ვე შემთხვევა (429/500/502/503) ვარდება.
  re-review: code-reviewer — დახურულია.

#### A-054 · nit · `session.js`-ის ორი კომენტარი ახალ ქცევას აღარ ემთხვევა
- **ფაილი:** `frontend/src/services/session.js:89` („Called on logout and when a refresh fails" — ახლა მხოლოდ 401-ზე
  ან token-ის გარეშე 2xx-ზე); `:222-223` („let the caller surface the original error" — caller ახლა
  `apiErrors.fallback`-ს აჩვენებს; ქსელის შეცდომაზე `apiErrors.network` უფრო ზუსტი იქნებოდა).
- **გამოსწორება:** კომენტარების ტექსტი; სურვილისამებრ ქსელის შემთხვევაში `apiErrors.network`.
- **owner:** frontend-dev
- **status:** fixed (verified) — `bca370f`. ორივე კომენტარი + ქსელის შემთხვევაში `apiErrors.network` (429/5xx — fallback).
  `session.test.js`-ის ქსელის ტესტი ძველ კოდზე ვარდება (`git stash`). re-review: code-reviewer — დახურულია.

### A-032/A-033-ის re-review და ინციდენტი (2026-11-12)

#### A-061 · critical · ტესტების fixture `downgrade base`-ს ნებისმიერ ბაზაზე უშვებს, რომელსაც `settings` აჩვენებს
- **ფაილი:** `backend/tests/conftest.py:50-72` (`_run_alembic`, `_create_schema`), `backend/alembic/env.py:30`
- **სცენარი (მოხდა 2026-11-12):** დაცვა (`VOLTBOX_NO_DOTENV=1`, `DATABASE_URL` → `voltbox_test`) მხოლოდ მაშინ მუშაობს, თუ
  `app`-ს პირველი conftest აიმპორტებს. pytest plugin (`-p`), რომელმაც `app.core.config` ადრე დააიმპორტა, `Settings`-ი
  `backend/.env`-იდან შექმნა, და autouse session fixture-მა `alembic downgrade base` იმ ბაზაზე გაუშვა — ორჯერ. 0016→0011
  შესრულდა, 0010-ზე ჩავარდა (`ck_orders_payment_method_allowed does not exist` — ლოკალურ ბაზებზე ეს constraint არსებობს,
  ამიტომ ბაზა სავარაუდოდ ლაივ Supabase იყო). ერთ ტრანზაქციაში იყო, ამიტომ კოდის მიხედვით rollback-ით გაუქმდა.
- **შედეგი:** ერთი შეცდომა plugin-ში ან სკრიპტში = ლაივ სქემის და მონაცემების (`name_en`, `deleted_at`,
  `password_reset_tokens`, …) წაშლა, თუ downgrade ბოლომდე გავა.
- **გამოსწორება:** `_run_alembic` alembic-მდე ამოწმებს, რომ `settings.database_url` ზუსტად `TEST_DATABASE_URL`-ია (ან host
  `localhost`/`127.0.0.1` და ბაზის სახელი `_test`-ით მთავრდება), სხვა შემთხვევაში `pytest.exit` გასაგები ტექსტით; ტესტი,
  რომელიც ამ დაცვას ამოწმებს. სურვილისამებრ `alembic/env.py`-ში `downgrade` არა-ლოკალურ host-ზე იკრძალება.
- **owner:** backend-dev
- **status:** fixed (verified) — `6ca1bdc` (+ CLAUDE.md-ის წესი `1e4a0c0`). ლაივ სქემა მფლობელმა გადაამოწმა (0016, დაზიანება
  არ არის). `app/db/local_url.py`; conftest import-ზე ამოწმებს cached settings-ს და `engine.url`-ს (ლოკალური host + `_test`),
  `_run_alembic` — alembic-ის URL-ს `command.*`-მდე; `alembic/env.py` ონლაინ რეჟიმში არალოკალურ host-ს უარყოფს
  `VOLTBOX_ALLOW_REMOTE_MIGRATION=1`-ის გარეშე, `--sql` უცვლელია. 37 ახალი ტესტი, 27 ძველ conftest/env.py-ზე ვარდება.
  ორკესტრატორმა ხელით: `alembic downgrade base` `db.invalid.example`-ზე → `FAILED: Refusing to run alembic online …`;
  `TEST_DATABASE_URL=…db.invalid.example/voltbox_test pytest` → conftest-ის import-ის შეცდომა collection-მდე; ლოკალური
  `upgrade head` + `check` სუფთაა. re-review (security-auditor): 0 critical, 0 should-fix; nit-ები A-064–A-066, ახალი A-063.

#### A-063 · should-fix · `docker-compose.yml`-ის `api` service `backend/.env`-ს container-ში ტვირთავს
- **ფაილი:** `backend/docker-compose.yml:51-52` (`env_file: - .env`, profile `full`)
- **სცენარი (კოდით):** `docker compose --profile full up` `.env`-ის ყველა ცვლადს container-ში აწვდის. `DATABASE_URL`-ს და
  `REDIS_URL`-ს `environment:` გადაფარავს, მაგრამ `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `RESEND_API_KEY` ლაივია —
  ლოკალური API ლაივ bucket-ში ატვირთავს და ნამდვილ Telegram/ელფოსტას გააგზავნის. CLAUDE.md: „`backend/.env` container-ში
  არასდროს". A-061-მდეც ასე იყო. ახლა `.env` პროექტიდან გატანილია, ამიტომ ეს profile ჯერ საერთოდ არ ეშვება.
- **გამოსწორება:** `env_file` ამოღება და საჭირო ცვლადები (`JWT_SECRET` ლოკალური მნიშვნელობით, გარე credentials ცარიელი)
  `environment:`-ში; ან `env_file: .env.example`-ის მსგავსი ლოკალური ფაილი.
- **owner:** backend-dev
- **status:** fixed (verified) — `ca58669`. `env_file` აღარ არის; `api`-ს მხოლოდ ლოკალური DATABASE_URL/REDIS_URL, აშკარად
  სატესტო JWT_SECRET, `DB_SSL_MODE=disable` (host `db` ლოკალურად არ ითვლება) და ცარიელი SUPABASE_*/TELEGRAM_*/RESEND_API_KEY/
  EMAIL_FROM. `docker compose --profile full config` ✅ (profile არ გაშვებულა). `tests/test_compose_file.py`: 3 / 4 ძველ ფაილზე
  ვარდება; secret-ების სია `Settings`-იდან გამოითვლება. re-review: security-auditor — დახურულია.

#### A-064 · nit · conftest-ის module-level შემოწმებებს ტესტი არ იცავს
- **ფაილი:** `backend/tests/conftest.py` (`require_settings_built_for_this_run()` და `require_test_database(engine.url, …)`
  module level-ზე)
- **სცენარი:** ამ ორი გამოძახების წაშლისას `test_database_guard.py` მწვანე რჩება (ფუნქციებს პირდაპირ იძახებს). დამანგრეველ
  გზას (`_run_alembic`) ტესტი იცავს, ამიტომ რისკი დაბალია.
- **გამოსწორება:** subprocess ტესტი, რომელიც ინციდენტს plugin-ის გარეშე იმეორებს: ჯერ `app.core.config`, მერე `tests.conftest`
  იმპორტი, `DATABASE_URL=…db.invalid.example/voltbox` → exit ≠ 0 და `built before tests/conftest.py`.
- **owner:** backend-dev
- **status:** fixed (verified) — `0c42877`. `tests/test_conftest_guard.py` + `tests/_guard_child.py`; conftest-ის ორი
  გამოძახების გათიშვისას უარის ტესტები ვარდება, საკონტროლო გადის. re-review: code-reviewer — დახურულია.

#### A-065 · nit · `alembic/env.py`-ში `%`-იანი პაროლი URL-ს traceback-ში ბეჭდავს (fix-მდეც ასე იყო)
- **ფაილი:** `backend/alembic/env.py` (`config.set_main_option("sqlalchemy.url", …)`)
- **სცენარი:** percent-encoded პაროლი (`%40`) ConfigParser-ის interpolation-ზე `ValueError("invalid interpolation syntax in
  '<URL პაროლით>'")`-ს აგდებს, `--sql`-ზეც. A-061-ის შემოწმებაზე გავლენა არ აქვს (`get_main_option` და `get_section`
  ერთნაირად interpolate-ს აკეთებენ).
- **გამოსწორება:** `settings.database_url.get_secret_value().replace("%", "%%")`.
- **owner:** backend-dev
- **status:** fixed (verified) — `13eb2b0`. guard-ი და engine ორიგინალ (`%40`) URL-ს იღებენ, offline — `settings`-იდან. 4 ახალი
  ტესტი ძველ env.py-ზე ვარდება. re-review: security-auditor — დახურულია.

#### A-066 · nit · ლაივზე `alembic check` ახლა override-ს ითხოვს; docs ამას არ ამბობს
- **ფაილი:** `docs/deployment.md` §5 („`alembic check` სუფთაა"; იქვე „ბაზა `0011`-ზეა" — მოძველებულია, ახლა 0016),
  `docs/pre-deployment-checklist.md:73`
- **სცენარი:** მფლობელს ლაივზე წასაკითხი `alembic check` სჭირდება `VOLTBOX_ALLOW_REMOTE_MIGRATION=1`-ით; shell-ში `export`-ით
  დატოვებული ცვლადი მომდევნო `upgrade`/`downgrade`-ზეც თიშავს დაცვას.
- **გამოსწორება:** §5-ში: ლაივის შემოწმება მხოლოდ `VOLTBOX_ALLOW_REMOTE_MIGRATION=1 alembic check` ერთ ბრძანებაზე, `export`-ის
  გარეშე; „0011" → მიმდინარე revision.
- **owner:** backend-dev
- **status:** fixed (reviewed) — `e2a2a81` + `f5b0cd3`. live check — ერთი ბრძანება (`VOLTBOX_ALLOW_REMOTE_MIGRATION=1
  VOLTBOX_NO_DOTENV=1 JWT_SECRET=… DATABASE_URL=… alembic check`), `export` აკრძალულია; რევიზია იკითხება და არ ინახება.
  ორკესტრატორმა გაუშვა: `alembic heads` მიუწვდომელ host-ზე → `0017 (head)`; `--sql`-ის ახალი ფორმა `.env`-ის გარეშე →
  0016→0017 SQL. re-review: code-reviewer ×2 — დახურულია; ნარჩენი nit-ები A-084.

#### A-062 · should-fix (დაუდასტურებელი) · bucket-ში უკვე შენახული პატარა ფოტოები GPS-ს ინარჩუნებენ
- **ფაილი:** ლაივ `product-images` bucket; `backend/app/services/storage.py` (`shrink_to_fit`)
- **სცენარი:** A-033 მხოლოდ ახალ ატვირთვებზე მოქმედებს. `6469e57`-მდე ატვირთული ≤1600 px ფოტო ბაიტ-ბაიტ ინახებოდა, ამიტომ
  ტელეფონის GPS / `Make` საჯარო URL-ზე რჩება. მფლობელი რეალურ პროდუქტებს ადმინიდან ტვირთავს. bucket-ზე წვდომა არ გვქონდა.
- **გამოსწორება:** მფლობელის გადაწყვეტილება: ერთჯერადი გადამუშავება (`shrink_to_fit` თითოეულ ობიექტზე, იგივე key-ით) ან
  ფოტოების ხელახლა ატვირთვა ადმინიდან და ძველის წაშლა. ჯერ — რამდენ ობიექტს აქვს EXIF.
- **owner:** მფლობელი
- **status:** needs decision

#### A-055 · nit · `_PROCESSING`-ის კომენტარი „40 by default in anyio"-ს ამბობს
- **ფაილი:** `backend/app/services/admin_image.py:52-54`
- **სცენარი (კოდით):** `asyncio.to_thread` loop-ის ნაგულისხმევ executor-ს იყენებს: `min(32, process_cpu_count() + 4)`.
  40 anyio-ს `run_in_threadpool`-ისაა. დასკვნა („გიგაბაიტები") ძალაში რჩება.
- **გამოსწორება:** „up to the default executor's size, min(32, CPUs + 4)".
- **owner:** backend-dev
- **status:** fixed (verified) — `84d1b1f`. მხოლოდ კომენტარი; ფორმულა Python 3.14-ის `concurrent/futures/thread.py:181`-ით
  გადამოწმდა (`min(32, (os.process_cpu_count() or 1) + 4)`), `app/`-ში `run_in_threadpool` არ არის. re-review: code-reviewer — დახურულია.

#### A-056 · nit · WebP-ის `method=6` encode-ის დრო გაზომილი არ არის
- **ფაილი:** `backend/app/services/storage.py` (`shrink_to_fit`, WebP-ის შტო)
- **სცენარი:** `method=6` libwebp-ის ყველაზე ნელი რეჟიმია. A-032-ის შემდეგ ის loop-ს აღარ ბლოკავს, მაგრამ semaphore-ის ქვეშ
  CPU-ს წვავს და სხვა ატვირთვებს აყოვნებს.
- **გამოსწორება:** გაზომვა (1600 px შედეგი, `method` 4 vs 6: დრო და ზომა); მერე გადაწყვეტა.
- **owner:** backend-dev
- **status:** fixed (verified) — `6b2d585` (+ `aa98335`, კომენტარის „2-4%"). გაზომვა (Windows, Ryzen 7 4700U, Pillow 13 /
  libwebp 1.6, 1600×1186 შედეგი): ნაწილობრივ გამჭვირვალე WebP-ზე `method=6` 2.2–4.0 წმ, 4 და 5 — 0.18–0.73 წმ, ფაილი 2–4%-ით
  პატარა; გაუმჭვირვალე ფოტოზე m5 16%-ით სწრაფია m6-ზე (1.4% დიდი ფაილი), m4 m5-ზე მხოლოდ 5%-ით. → `method=5`. `DECODE_COST`,
  ბიუჯეტი და `Semaphore(1)` უცვლელია; `TestDecodeMemoryIsBounded` გადის (WebP-ის peak Windows-ზე 90 → 58 MiB). ტესტი ძველ
  კოდზე ვარდება (ორკესტრატორი, `git stash`). re-review: code-reviewer — დახურულია. Linux-ის დრო არ გაზომილა → A-100.

#### A-057 · nit · PNG, რომლის `eXIf` IDAT-ის შემდეგაა, ორიენტაციას კარგავს
- **ფაილი:** `backend/app/services/storage.py` (`_exif_orientation`)
- **სცენარი:** ასეთ ფაილზე `info["exif"]` გახსნისას არ არსებობს, ამიტომ ორიენტაცია 1-ად ითვლება; chunk-ი იშლება, ფოტო
  შეიძლება გვერდზე ჩანდეს. კამერები PNG-ს ასე არ წერენ.
- **გამოსწორება:** byte-level `eXIf` ძებნა header-only წაკითხვისთვის, ან ასეთი ფაილის `INVALID_IMAGE`.
- **owner:** backend-dev
- **status:** fixed (verified) — `93e8fd1`. byte-level გზა: `_png_exif` chunk-ების სიას დადის (length/type, pixel-ის გარეშე),
  PNG-ის EXIF ყოველთვის იქიდან იკითხება; `validate_image` და `shrink_to_fit` ერთსა და იმავე `_exif_orientation(probe, data)`-ს
  ეკითხებიან, ამიტომ გვიანი eXIf ბიუჯეტით ისევე ფასდება. ცალკე ზღვარი არ დაემატა: 5 MiB ცარიელი chunk-ები — 0.18 წმ, `verify()`
  იმავე ფაილზე 0.63 წმ. 15 ახალი ტესტიდან 10 ძველ კოდზე ვარდება (ორკესტრატორი, `git stash`). re-review: code-reviewer — დახურულია.

#### A-058 · nit · PNG/WebP-ის stripper denylist-ია; JPEG-ის APP0/APP14 identifier-ს არ ამოწმებს
- **ფაილი:** `backend/app/services/storage.py` (`_PNG_METADATA`, `_strip_webp`, `_strip_jpeg`-ის `keep`)
- **სცენარი (კოდით):** PNG-ში რჩება `caBX` (C2PA, შეიძლება ავტორი), `exIf`/`zxIf`, `iDOT`, private chunk-ები; WebP-ში
  ნებისმიერი უცნობი FourCC (`C2PA`). JPEG-ში APP0 (JFXX-ის thumbnail-ით) და APP14 მთლიანად რჩება. JPEG-ის C2PA (APP11)
  კი იშლება — ფორმატები განსხვავებულად იქცევიან.
- **გამოსწორება:** allowlist: PNG — IHDR, PLTE, IDAT, IEND, tRNS, gAMA, cHRM, sRGB, iCCP, sBIT, bKGD, pHYs, cICP, mDCV, cLLI,
  acTL, fcTL, fdAT; WebP — VP8X, VP8, VP8L, ALPH, ANIM, ANMF, ICCP; APP0 მხოლოდ `JFIF\0`-ით, APP14 მხოლოდ `Adobe`-ით.
- **owner:** backend-dev
- **status:** fixed (verified) — `a837692`. ზუსტად აუდიტის allowlist-ები (WebP-ის FourCC `VP8 ` space-ით); APP2 — მხოლოდ ICC.
  ANMF-ის შიგთავსიც იფილტრება (მხოლოდ ALPH/VP8/VP8L, ერთი დონე), რადგან spec ფრეიმში უცნობ chunk-ს უშვებს. VP8X-ში მხოლოდ
  EXIF/XMP bit-ები იწმინდება. 15 ახალი ტესტიდან (HTTP-ის გზაც) 14 ძველ კოდზე ვარდება (ორკესტრატორი, `git stash`).
  re-review: security-auditor — დახურულია, 0 critical / 0 should-fix; ნარჩენი (ძველი) JFIF-ის შიდა thumbnail → A-098.

#### A-059 · nit · resize-ის გზაზე stripper-ის შეცდომა უკვე მზა re-encode-ს უარყოფს
- **ფაილი:** `backend/app/services/storage.py` (`shrink_to_fit`-ის ბოლო ორი ხაზი)
- **სცენარი (კოდით):** >1600 JPEG EOI-ის გარეშე — Pillow დეკოდავს (budget-ში), მაგრამ შედარებისთვის `_STRIP_METADATA`
  `INVALID_IMAGE`-ს ისვრის და ატვირთვა 400-ია, თუმცა სუფთა `shrunk` უკვე არსებობს.
- **გამოსწორება:** `try: stripped = …` / `except ValidationError: return shrunk`.
- **owner:** backend-dev
- **status:** fixed (verified) — `d446b70`. აუდიტის ზუსტი მაგალითი (>1600 JPEG, EOI მოჭრილი) stripper-მდე ვერ აღწევს —
  Pillow decode-ზე `OSError`-ს აგდებს (სხვა დეფექტი → A-097). დადასტურდა ფაილით, რომლის EOI walk-ისთვის წაუკითხავი კუდით
  არის ჩანაცვლებული (Pillow ბოლო MCU-ზე ჩერდება): ძველ კოდზე HTTP 400. ახლა მხოლოდ შედარების ეტაპი იჭერს walk-ის
  `ValidationError`-ს და re-encode-ს აბრუნებს; ≤1600 upright ფაილი ისევ `INVALID_IMAGE`-ია. PNG/WebP-ზე ეს გზა მიუწვდომელია
  (`verify()` ადრე უარყოფს). 9 ტესტიდან 6 ძველ კოდზე ვარდება (ორკესტრატორი, `git stash`). re-review: code-reviewer — დახურულია.

#### A-060 · nit · JPEG-ის walker-ს marker-ების რაოდენობის ზღვარი არ აქვს
- **ფაილი:** `backend/app/services/storage.py` (`_strip_jpeg`)
- **სცენარი (კოდით, გაზომილი არ არის):** JPEG-ის `verify()` SOS-ის შემდეგ არაფერს ამოწმებს; 5 MB `FF 01`/`FF FF 00` ≈ 2.5M
  Python iteration — შეფასებით რამდენიმე წამი CPU ერთ ატვირთვაზე (მხოლოდ ავტორიზებული ადმინი).
- **გამოსწორება:** marker-ების ლიმიტი (მაგ. 65 536) → `INVALID_IMAGE`; გაზომვა.
- **owner:** backend-dev
- **status:** fixed (verified) — `cc6abee` (re-review: security-auditor — დახურულია). `_MAX_JPEG_MARKERS = 65_536`
  (რატომ — Decision Log 2026-11-15); fill-ბაიტები ერთი regex-ით გამოიტოვება. გაზომვა (5 MiB, best of 7): `FF 01` 1073 → 35 ms,
  `FF FF 00` scan-ში 1532 → 84 ms, მხოლოდ `FF` 263 → 2.6 ms; ლეგიტიმურ ფაილში 12–27 marker-ია. ძველ walker-ზე (მხოლოდ
  კონსტანტით) 2 ტესტი ქცევითად ვარდება: `DID NOT RAISE` — 65 536-ზე მეტ marker-იანი ფაილი მიიღებოდა (ორკესტრატორმა გაუშვა).
  auditor: მრიცხველს ვერცერთი ტოტი ვერ უვლის, `_SCAN_END`-ის ძებნა კვადრატული არ არის, ლეგიტიმური ფაილის შედეგი უცვლელია.
  ნარჩენი: A-075 (WEBP, დაუდასტურებელი).

### A-039/A-040/A-034-ის re-review (2026-11-14)

#### A-067 · should-fix · `scrub` Postgres-ის `Failing row contains (…)` DETAIL-ს არ ასუფთავებს
- **ფაილი:** `backend/app/core/logging.py:30` (`PG_DETAIL_VALUE = r"(Key \([^)]*\)=\()[^)]*\)"`), `:35`
- **სცენარი (კოდით, security-auditor; regex-ში `Key \(` სიტყვასიტყვით წერია):** asyncpg-ის `__str__` DETAIL-ს სიტყვასიტყვით
  სვამს (`asyncpg/exceptions/_base.py:168-175`), ამიტომ `hide_parameters=True` მას ვერ აჩერებს. NOT NULL და CHECK-ის დარღვევისას
  DETAIL არის `Failing row contains (<მთელი სტრიქონი>)`. ეს ხაზი არ იწმინდება ლოგის არცერთ ხაზში (`voltbox.error`,
  `uvicorn.error`, ჯაჭვური asyncpg-ის გამონაკლისი). `orders`-ის CHECK-ზე (`models/orders.py:75-94`) ეს `guest_email`-ია,
  `guest_phone` და `customer` JSON; `users`-ზე — `email` და `password_hash`. დღეს ჩვეულებრივი გზა ამას ვერ იწვევს (სქემის
  ვალიდაცია, `order_status.py`), მაგრამ A-034-ის მიზანი, „DETAIL-ის მნიშვნელობა არცერთ ხაზში", ამ ფორმაზე არ სრულდება.
- **გამოსწორება:** DETAIL-ის მნიშვნელობა ხაზის ბოლომდე ჩამოიჭრას, მაგ.
  `(Key \(.*?\)=\(|Failing row contains \()[^\n]*` → `\1…)` (ხურავს A-068-საც და `Key (lower(email))=(…)`-საც). რაც
  ძალაში რჩება: მრავალხაზიანი მნიშვნელობის (`notes`) მომდევნო ხაზები. ტესტი: `uvicorn.error`-ზე
  `Failing row contains (…, x@y.com, …)` → გამოსავალში `x@y.com` არ არის.
- **owner:** backend-dev
- **status:** fixed (verified) — `0452669` (re-review: security-auditor — დახურულია, ახალი პრობლემა არ არის). ზუსტად
  შემოთავაზებული regex, ჩანაცვლება `\1…)`; მნიშვნელობა ხაზის ბოლომდე იჭრება, ამიტომ ` already exists.`-იც ქრება. 6 ახალი
  ტესტი (`Failing row contains` `uvicorn.error`/`gunicorn.error`-ზე და `%s`-ში; `)`-იანი მნიშვნელობა; `lower(email::text)`)
  ძველ `logging.py`-ზე ვარდება (ორკესტრატორმაც გაუშვა `git stash`-ით). auditor: regex-ს catastrophic backtracking არ აქვს;
  `orders`-ში PII-იანი სვეტები `notes`-მდეა, ამიტომ მიღებული შეზღუდვა (მრავალხაზიანი მნიშვნელობის შემდეგი ხაზები) მხოლოდ
  `notes`-ის დარჩენილ ტექსტს და მის შემდეგ სვეტებს (`idempotency_key`, დროები) ეხება.

#### A-068 · nit · `)`-იანი მნიშვნელობა `Key (…)=(…)`-ში ნაწილობრივ ჟონავს
- **ფაილი:** `backend/app/core/logging.py:30` (`[^)]*` პირველ `)`-ზე ჩერდება)
- **სცენარი (კოდით):** `Key (name)=(Foo) Bar) already exists.` → `Key (name)=(…) Bar) already exists.`. PII-იანი unique სვეტი
  მხოლოდ `users.email`-ია, email-ის ვალიდაცია კი `)`-ს არ უშვებს, ამიტომ დღეს რეალური გაჟონვა არ არის.
- **გამოსწორება:** A-067-ის regex.
- **owner:** backend-dev
- **status:** fixed (verified) — `0452669`, A-067-თან ერთად (ტესტი `Key (name)=(Foo) Bar)` ძველ კოდზე ` Bar`-ს ტოვებდა).

#### A-069 · nit · `test_server_log_secrecy.py`-ის fixture root-ზე pytest-ის ძველ `LogCaptureHandler`-ს ტოვებს
- **ფაილი:** `backend/tests/test_server_log_secrecy.py:34-46` (`restore_logging`)
- **სცენარი (კოდით):** handler-ები setup ფაზაში ინახება და teardown-ში ბრუნდება. ამიტომ setup ფაზის caplog handler-ი root-ზე
  რჩება, ფაზის ბოლოს pytest მას ვეღარ შლის: 14 ტესტის შემდეგ 14 მკვდარი handler, სანამ lifespan-იანი ტესტი root-ს არ
  გაასუფთავებს. შედეგზე გავლენა არ ჩანს, მხოლოდ მეხსიერება იხარჯება.
- **გამოსწორება:** მდგომარეობის შენახვა და აღდგენა ტესტის სხეულში (context manager), ან teardown-ში pytest-ის მიმდინარე handler-ების შენარჩუნება.
- **owner:** backend-dev
- **status:** not reproduced (measured, 2026-11-15) — კოდი არ შეცვლილა. pytest 9.1.1-ში `LoggingPlugin` `caplog_handler`-სა
  და `report_handler`-ს ერთხელ ქმნის (`_pytest/logging.py:674-676`) და ყველა ფაზაში იმავე instance-ს ამაგრებს root-ზე
  (`catching_logs.__enter__`/`__exit__`). teardown-ში დაბრუნებული „setup-ის handler-ი" იგივე ობიექტია, რომელსაც pytest
  teardown-ის ბოლოს თვითონ ხსნის, ამიტომ არაფერი გროვდება. გაზომვა: დროებითმა ტესტმა, რომელიც ამ მოდულის 17 ტესტის შემდეგ
  გაეშვა, root-ზე ძველ fixture-ზეც 2 `LogCaptureHandler` დაითვალა (მიმდინარე ფაზის caplog + report), არა 19. დეველოპერის
  ცვლილება (`_pytest.logging`-ის კერძო კლასზე ფილტრი და guard, რომელიც ფაზებს ცალ-ცალკე instance-ებით აწყობდა, რაც pytest-ს
  არ აქვს) არ შევიდა. რაც ძალაში რჩება: თუ pytest ფაზაზე ახალ instance-ს შექმნის, აუდიტის სცენარი აღდგება.

#### A-070 · nit · ტესტში `dictConfig(uvicorn.config.LOGGING_CONFIG)` პროცესის ყველა handler-ს ხურავს
- **ფაილი:** `backend/tests/test_server_log_secrecy.py:68`
- **სცენარი (კოდით):** non-incremental `dictConfig` → `_clearExistingHandlers()` → `logging.shutdown(...)`. pytest-ის
  `_FileHandler` ამის შემდეგ ჩანაწერებს ჩუმად აგდებს. ზიანი მხოლოდ `--log-file`-ით გაშვებისას ჩნდება.
- **გამოსწორება:** uvicorn-ის dev wiring ხელით აწყობა (`uvicorn` logger-ს საკუთარი handler, `uvicorn.error` propagate), `dictConfig`-ის გარეშე.
- **owner:** backend-dev
- **status:** fixed (verified) — `ccb494d` (re-review: code-reviewer — დახურულია, ახალი პრობლემა არ არის). helper `uvicorn`-ს
  (საკუთარი `StreamHandler`, `DefaultFormatter`, level, propagate) და `uvicorn.error`-ს (handler-ის გარეშე, propagate) თავად
  `LOGGING_CONFIG`-ის მნიშვნელობებით აწყობს, ფორმის assert-ებით. guard (root-ზე mode `'w'` `FileHandler` wiring-ის შემდეგაც
  წერს) ძველი `dictConfig`-ით ვარდება (ორკესტრატორმა დროებით ჩასვა და გაუშვა). scrubber-ის ტესტები გაფუჭებულ `scrub`-ზე ისევ
  ვარდება (16/18, დეველოპერის გაშვება). მხოლოდ ტესტის ცვლილებაა.

#### A-071 · nit (დაუდასტურებელი) · ერთდროული `DELETE` და `PUT` ერთ მისამართზე შეიძლება 500 იყოს
- **ფაილი:** `backend/app/services/address.py` (`update_one`-ის flush, `remove`). ფიქსამდეც ასე იყო.
- **სცენარი (კოდით, code-reviewer, არ გამეორებულა):** T2 X-ს შლის და commit არ გაუკეთებია. T1 `_get_owned`-ით X-ს ისევ ხედავს,
  მისი UPDATE T2-ს ელოდება. T2-ის commit-ის შემდეგ ORM UPDATE 0 რიგს ემთხვევა → `StaleDataError`, ანუ 500. მონაცემები
  შეთანხმებული რჩება, რადგან T1 rollback-დება.
- **გამოსწორება:** `remove`-მაც აიღოს `_lock_default_writes`, ან `update_one`-მა `StaleDataError` → 404 `ADDRESS_NOT_FOUND`.
  ტესტი: `_contend(remove, _moving)`.
- **owner:** backend-dev
- **status:** fixed (verified) — `50905ba` (re-review: code-reviewer). **დადასტურდა** ძველ კოდზე: `_contend(_removing, _moving)` →
  `[('ok','committed'), ('error','StaleDataError')]` (500). `remove` ახლა პირველ რიგში `_lock_default_writes`-ს იღებს →
  იგივე race 404 `ADDRESS_NOT_FOUND`-ია. ამავე ცვლილებით მოიხსნა A-041-ის ნარჩენი: create, რომელიც 20-ე მისამართის უკომიტო
  delete-ის დროს ითვლიდა, ზედმეტ 409-ს იღებდა. 3 race-ტესტიდან 2 ძველ კოდზე ვარდება (ორკესტრატორმაც გაუშვა `git stash`-ით),
  მესამე (update პირველი) ძველზეც გადიოდა და guard-ად რჩება. reviewer: lock-ის რიგი ყველგან users → addresses, deadlock
  არ არის. race HTTP-ის დონეზე არ შემოწმებულა (service-ის დონეზე; 404 არსებული handler-იდან მოდის).

### A-067/A-038/A-007/A-041/A-071/A-045/A-060-ის re-review (2026-11-15)

#### A-072 · nit · `products.stock`-ის ჯამს ზედა ზღვარი არ აქვს
- **ფაილი:** `backend/app/services/inventory.py` (`adjust_stock`: `previous + change`), `backend/app/db/models/catalog.py:142`
  (მხოლოდ `stock >= 0` CHECK)
- **სცენარი (კოდით, backend-dev):** A-007-ის შემდეგ ერთი ცვლილება ±100 000-ია, მაგრამ ~21 475 ცვლილება +100 000-ით (ან
  2³¹-თან ახლოს მყოფ stock-ზე ნებისმიერი დამატება) int4-ს გადააჭარბებს → 500. რეალურად ნაკლებად სავარაუდოა; A-007-მდეც ასე იყო.
- **გამოსწორება:** ზედა ზღვარი `adjust_stock`-ში (მაგ. 1 000 000) კოდით (`STOCK_LIMIT_EXCEEDED`, ka/en) + DB CHECK; ზღვრის
  მნიშვნელობა მფლობელის გადაწყვეტილებაა.
- **owner:** backend-dev
- **status:** fixed (verified) — `23566e9` (re-review: code-reviewer — დახურულია, nit-ები → A-078). `inventory.MAX_STOCK =
  1_000_000` (მფლობელის მნიშვნელობა); `adjust_stock` ყოველ ზრდას, რომლის შედეგი ზღვარს გადააჭარბებს, 400
  `STOCK_LIMIT_EXCEEDED`-ით უარყოფს, სანამ რამე ჩაიწერება (ka/en). შემცირება არასდროს — ზღვარს ზემოთ ძველი row ისევ იყიდება.
  **გადახრა აუდიტის ტექსტიდან:** DB CHECK და migration არ დაემატა (მფლობელმა მხოლოდ 0017-ის `request_hash` დაამტკიცა;
  `adjust_stock` ერთადერთი ჩამწერია — reviewer-მა grep-ით დაადასტურა). გაუქმების restock-იც ზღვარს ექვემდებარება; უარი
  ტრანზაქციას მთლიანად აბრუნებს (reviewer). 12 ახალი ტესტიდან 6 ძველ `inventory.py`-ზე (+ მხოლოდ კონსტანტა) ვარდება
  (ორკესტრატორმა გაუშვა).

#### A-073 · nit · სამ სხვა admin int ველს ზედა ზღვარი არ აქვს → int4 overflow → 500
- **ფაილი:** `backend/app/schemas/admin_product.py:108` (`ProductCreate.stock`, `ge=0`), `:105`/`:150`
  (`low_stock_threshold` create/update), `backend/app/schemas/admin_catalog.py:73`/`:91` (`Category.position` create/update)
- **სცენარი (კოდით, code-reviewer; ორკესტრატორმა კოდში გადაამოწმა):** admin პროდუქტს `"stock": 3000000000`-ით ქმნის → 500
  (transaction rollback-დება, მონაცემი არ ფუჭდება). საწყისი `stock` A-007-ის ±100 000-ს გვერდს უვლის (2 000 000 000 მიიღება,
  `REASON_INITIAL`-ის movement-ში შესაბამისი `change`-ით). იგივე `low_stock_threshold`-ზე და კატეგორიის `position`-ზე.
- **გამოსწორება:** `le=MAX_STOCK_ADJUSTMENT` `stock`-ზე, გონივრული `le=` დანარჩენზე (მაგ. 100 000 და 10 000); out-of-range
  ტესტები, როგორც `test_stock_adjust_bounds.py`-ში.
- **owner:** backend-dev
- **status:** fixed (verified) — `4a15441` (re-review: code-reviewer — დახურულია). საწყისი `stock` ≤ `MAX_STOCK_ADJUSTMENT`
  (100 000), `low_stock_threshold` ≤ `MAX_LOW_STOCK_THRESHOLD` (100 000), კატეგორიის `position` ≤ `MAX_CATEGORY_POSITION`
  (10 000), create-ზეც და update-ზეც; გადაჭარბება → 400 `VALIDATION_ERROR`, არაფერი იწერება. 15 ახალი HTTP ტესტიდან 10 ძველ
  სქემებზე ვარდება (ორკესტრატორმა `git stash`-ით გაუშვა). reviewer: სხვა client-input გზა ამ ველებს არ იღებს; PATCH
  `exclude_unset`-ით მუშაობს, მაგრამ admin UI ამ ველებს ყოველ შენახვაზე ხელახლა აგზავნის — ლაივზე ზღვარს ზემოთ არსებული row
  panel-იდან ვერ შეინახება, სანამ მნიშვნელობას არ შეამცირებ (შემოწმების SQL — PROGRESS.md `## Blockers`). import script → A-078.

#### A-074 · nit · ძებნის ლიმიტი ნორმალიზებულ token-ებს ითვლის, არა აკრეფილ სიტყვებს
- **ფაილი:** `backend/app/services/search.py` (`_parse_query`)
- **სცენარი (კოდით, code-reviewer):** `normalize` „100W“-ს, „2მ“-ს და „USB-C“-ს ორ-ორ token-ად ყოფს, გამეორებული token-ები
  ცალ-ცალკე ითვლება. პროდუქტის სრული 8-სიტყვიანი სახელი („Baseus Flash Series USB-C — USB-C 100W კაბელი 2მ“) 12 token-ია, და
  „w კაბელი 2 m“ იკვეთება. შედეგი ცარიელი არ ხდება, უფრო ფართოა: იმავე ხაზის სხვა სიგრძის/სიმძლავრის ვარიანტებიც ჩანს.
- **გამოსწორება:** token-ების dedupe ლიმიტამდე (რიგის შენარჩუნებით) და `normalize`-ის მიერ გაყოფილი რიცხვი+ერთეული ერთ
  სიტყვად ჩაითვალოს (ან ლიმიტი აკრეფილ, whitespace-ით გაყოფილ სიტყვებზე). მფლობელმა „8 token“ დაამტკიცა — „8 სიტყვაზე“
  გადასვლა მისი გადაწყვეტილებაა. ტესტი: `_parse_query("Baseus Flash Series USB-C — USB-C 100W კაბელი 2მ")` ყველა token-ს ინახავს.
- **owner:** backend-dev
- **status:** fixed (verified) — `0927590`. მფლობელის გადაწყვეტილებით `MAX_QUERY_TOKENS` 8 → 16, dedupe-ისა და დათვლის
  ცვლილების გარეშე (Decision Log განახლდა). Baseus-ის სახელი (12 token) მთლიანად იკითხება; A-045-ის ზღვრის ტესტები
  `MAX_QUERY_TOKENS`-ზე გადავიდა (30-სიტყვიანი მოთხოვნა ბაზაში ზუსტად ამდენ სიტყვას აგზავნის). 4 ტესტი ძველ `search.py`-ზე
  ვარდება (ორკესტრატორმა `git stash`-ით გაუშვა). რაც ძალაში რჩება: ზღვარი ნორმალიზებულ token-ებზეა. re-review: code-reviewer —
  დახურულია; ხარჯი წრფივად ×2 (ერთ statement-ში ≤64 token-clause, `/products?q=` ≤320 ერთ request-ზე, ადრე 160); nit-ები → A-079.

#### A-075 · nit (დაუდასტურებელი) · WEBP-ის stripper-ს chunk-ების რაოდენობის ზღვარი არ აქვს
- **ფაილი:** `backend/app/services/storage.py:541-556` (`_strip_webp`)
- **სცენარი (კოდით, security-auditor, არ გაზომილა):** ვალიდური VP8X WebP, რომლის `riff_end`-მდე ნულოვანი სიგრძის უცნობი
  chunk-ებია (8 ბაიტი თითო) → 5 MiB-ში ≈ 655 000 Python iteration; შეფასებით ასობით ms – ~1 წმ CPU (მხოლოდ ადმინი).
  დაუდასტურებელია, მიიღებს თუ არა libwebp ასეთ ფაილს, და ხარჯის ზომა. PNG-ის მსგავს გზას Pillow-ის `verify()` თავადაც იხდის,
  ამიტომ ის ცალკე პრობლემად არ ჩაითვალა.
- **გამოსწორება (თუ დადასტურდება):** chunk-ების მრიცხველი → `INVALID_IMAGE`, როგორც A-060-ში.
- **owner:** backend-dev
- **status:** fixed (verified) — `bb7ae36`. **დადასტურდა** გაზომვით: libwebp ცარიელ უცნობ chunk-ებს image data-ს შემდეგაც და
  ANMF-ის შიგნითაც იღებს; 5 MiB (655 000 chunk) `validate_image`-ს 3–65 ms-ში გადის, walk — 285 ms. `_MAX_WEBP_CHUNKS = 65_536`,
  ერთი ბიუჯეტი ფაილისა და ყველა ფრეიმისთვის → 33 ms და `INVALID_IMAGE`; 3 000-ფრეიმიანი ანიმაცია ბაიტ-ბაიტ ინახება. 9 ტესტიდან
  8 ძველ კოდზე ვარდება (ორკესტრატორი, `git stash`). re-review: security-auditor — დახურულია (ბიუჯეტი მართლაც საერთოა,
  off-by-one არ არის, რეკურსია ერთი დონეა).

### A-042/A-043/A-044/A-069/A-070/A-072/A-073/A-074-ის re-review (2026-11-15)

#### A-076 · nit · `IDEMPOTENCY_KEY_REUSED`-ის ტექსტი „სხვა კალათას" ამბობდა
- **ფაილი:** `frontend/src/i18n/ka.json`, `en.json` (`apiErrors.IDEMPOTENCY_KEY_REUSED`)
- **სცენარი (კოდით, security-auditor):** 409 მხოლოდ სახელის/მისამართის/კომენტარის ცვლილებაზეც ბრუნდება, ტექსტი კი კალათას ასახელებდა.
- **owner:** backend-dev
- **status:** fixed (reviewed) — `23566e9`, A-072-თან ერთად: „სხვა მონაცემებით" / „with different details".

#### A-077 · nit · შეკვეთის ნომრის სარტყელი პირდაპირ წერია, admin-ის ფილტრები `settings.store_timezone`-ს იყენებს
- **ფაილი:** `backend/app/services/order.py` (`_next_order_number`), `app/core/config.py` (`store_timezone`), `admin_orders.py:34`
- **სცენარი (კოდით, code-reviewer):** `STORE_TIMEZONE` სხვა მნიშვნელობით რომ დაყენდეს, „დღეს"-ის ფილტრი და ნომრის თარიღი
  ერთმანეთს აღარ დაემთხვევა. დღეს ეს არ ხდება: `render.yaml` მას არ აყენებს, ნაგულისხმევი Asia/Tbilisi-ა; მფლობელმა
  პირდაპირი მნიშვნელობა დაამტკიცა.
- **გამოსწორება:** `AT TIME ZONE :tz` bind-პარამეტრით, `{"tz": settings.store_timezone}`.
- **owner:** backend-dev
- **status:** fixed (verified) — `9d2f96a`. bind-პარამეტრი `settings.store_timezone`-ით (ნაგულისხმევი Asia/Tbilisi). ამ
  ცვლილებით არასწორი `STORE_TIMEZONE` ყოველ checkout-ს 500-ად აქცევდა, ამიტომ `Settings`-ს დაემატა `known_store_timezone`
  (ZoneInfo, startup-ზე უარი). A-043-ის ტესტები გადის (ახლა setting-ს კითხულობენ); ახალი ტესტებიდან 6 ძველ კოდზე ვარდება
  (ორკესტრატორი, `git stash`). tzdata უკვე `requirements.txt`-შია. re-review: code-reviewer — დახურულია.

#### A-078 · nit · `import_products.py` ახალ ზღვრებს `validate()`-ში წინასწარ არ ამოწმებს; ცოტა რამ A-072-ის ტესტებში
- **ფაილი:** `backend/scripts/import_products.py:78` (`validate`), `:130`, `:160-163`; `backend/tests/test_stock_ceiling.py`;
  `backend/app/services/inventory.py:74-76` (კომენტარი)
- **სცენარი (კოდით, code-reviewer ×2):** `"stock": 2000000` ან `"lowStockThreshold": 3000000000` `--dry-run`-ზე „✔ validation"-ს
  იღებს, ნამდვილი გაშვება კი raw traceback-ით ჩერდება (`STOCK_LIMIT_EXCEEDED` `ProductImportError` არ არის; threshold-ზე int4
  overflow `flush`-ზე). ერთი commit-ია, ამიტომ არაფერი ნახევრად არ იწერება. ამასთან: product-create-ის გზაზე ზღვრის ტესტი არ
  არის (კოდით სწორია); კომენტარი გაუქმებისას ზღვართან დაშორებას „20 × 10"-ს წერს, სინამდვილეში თითო პროდუქტზე ≤ 10-ია
  (`MAX_LINE_QUANTITY`); `test_checkout_below_the_ceiling_is_unaffected` ზღვარს ზემოთ იწყება.
- **გამოსწორება:** `validate()`-ში `MAX_STOCK` (ან `MAX_STOCK_ADJUSTMENT`) და `MAX_LOW_STOCK_THRESHOLD` → `ProductImportError`
  + unit-ტესტი; create-ის ტესტი `test_stock_ceiling.py`-ში; კომენტარისა და ტესტის სახელის გასწორება.
- **owner:** backend-dev
- **status:** fixed (verified) — `33c3cfe`. `validate()` (ანუ `load_rows`, session-მდე, `--dry-run`-იც) უარყოფს `stock`-ს
  0..`MAX_STOCK`-ის გარეთ, `lowStockThreshold`-ს 0..`MAX_LOW_STOCK_THRESHOLD`-ის გარეთ და არა-მთელ მნიშვნელობას (ახალი `to_int`;
  `true`/`false`, `1.5`, `null`, ტექსტი) — `ProductImportError` slug-ით, ველით, მნიშვნელობით და ზღვრით. `MAX_STOCK` და არა
  100 000, რადგან `adjust_stock` მხოლოდ მას ამოწმებს. create-ის ზღვრის ტესტი (service-ის დონეზე), checkout-ის ტესტი ახლა
  ზღვარს ქვემოთ იწყება (ზემოდან გაყიდვა ცალკე ტესტია), კომენტარი: გაუქმება ერთ პროდუქტზე ≤ 10 ერთეულს აბრუნებს. 38 ტესტიდან
  29 ძველ სკრიპტზე ვარდება (ორკესტრატორი, `git stash`). სკრიპტი მხოლოდ pytest-ით, ლოკალურ ბაზაზე. re-review: code-reviewer —
  დახურულია; `reviewsCount` → A-099.

#### A-079 · nit · ძებნის cap-ის ტესტები: ერთი კომენტარი არასწორია, layout candidate-ის გზა არ მოწმდება
- **ფაილი:** `backend/tests/test_search.py:286-287`, `:351-378`
- **სცენარი (კოდით, code-reviewer):** კომენტარი ამბობს, რომ ძველი cap „usb c usb c 100 w"-ის შემდეგ ჭრიდა — მერვე token `100`-ია.
  SQL-ის ტესტები params-ში ლათინურ სიტყვებს ეძებს, layout candidate კი ქართულ/ტრანსლიტ ფორმებს აგზავნის, ამიტომ თუ ის
  მომავალში `_parse_query`-ს გვერდს აუვლის, ტესტები მაინც გაივლის. ახლანდელი კოდი სწორია (`_run` ორივეს `_parse_query`-ით კითხულობს).
- **გამოსწორება:** კომენტარში `"... 100"`; `:365`/`:378`-ზე იგივე შემოწმება `to_latin(fix_layout(word))`-ზე.
- **owner:** backend-dev
- **status:** fixed (verified) — `172a3ba`, მხოლოდ ტესტი. კომენტარი + `words[:8]`-ის assert. ორივე cap-ტესტი სიტყვას სამივე
  ფორმით ეძებს (`word`, `fix_layout(word)`, `to_latin(fix_layout(word))`) და ამოწმებს, რომ layout candidate მართლა გაიგზავნა.
  დროებითი bypass `search._run`-ში (ქართული candidate cap-ის გარეშე) → ორივე ვარდება (`30 == 16`); search.py აღდგა უცვლელად.
  სინთეზური სიტყვები შეიცვალა: ძველი round trip-ზე ერთმანეთს ემთხვეოდა (q/k → k, w/c → ts). re-review: code-reviewer — დახურულია.

### A-063/A-036/A-046/A-010/A-011/A-048/A-065/A-066-ის re-review (2026-11-15)

#### A-080 · should-fix · ნაგულისხმევი 60/წთ ლიმიტი decorator-ის გარეშე route-ებზე არ მოქმედებს (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/core/rate_limit.py:105,130` (`DEFAULT_LIMIT`, `default_limits`), `backend/app/main.py` (`SlowAPIMiddleware`)
- **სცენარი (გაზომილი):** აშენებულ image-ზე (lock-ის ვერსიები: fastapi 0.141.1, slowapi 0.1.10, starlette 1.6.0) 70 ზედიზედ
  `GET /api/v1/categories` — 70 × 200. backend-dev-მა ლოკალურად 65 × `GET /health/live` იგივე შედეგით გაზომა. მიზეზი (მისი
  კოდის კითხვით): FastAPI 0.141-ის `app.routes`-ში `_IncludedRouter` ობიექტებია `.endpoint`-ის გარეშე, slowapi-ის
  `_find_route_handler` None-ს აბრუნებს და middleware შემოწმებას გამოტოვებს.
- **შედეგი:** ლიმიტი მხოლოდ `@limiter.limit`-იან route-ებზეა (auth, orders, quote, lookup, client-errors). კატალოგი, კალათა და admin-ის
  route-ები შეუზღუდავია, თუმცა `PROJECT.md` Security & Privacy და `rate_limit.py`-ის docstring 60/წთ-ს ამბობს.
- **გამოსწორება:** გადაწყვეტა სჭირდება — slowapi-ის route-ის ძებნა FastAPI-ის ახალ სტრუქტურაზე, ან ნაგულისხმევი ლიმიტი საკუთარ
  middleware-ში `limiter.limiter.hit`-ით. ტესტი: decorator-ის გარეშე route-ზე 61-ე მოთხოვნა → 429.
- **owner:** backend-dev
- **status:** fixed (verified) — `1d9e314` (+ კომენტარები `a36741f`). მფლობელის გადაწყვეტილებით 300/წთ ერთ კლიენტზე,
  ერთი საერთო bucket decorator-ის გარეშე ყველა route-ზე (slowapi-ის application limit), app-wide FastAPI dependency-ით
  (`enforce_default_limit`); `/api/v1/health` და `/health/live` გამონაკლისია; decorator-იანი route მხოლოდ თავის ლიმიტს
  ითვლის. 301-ე `GET /api/v1/categories` → 429 `RATE_LIMITED` + Retry-After (ტესტი ნამდვილ app-ზე); 6 ტესტი ძველ კოდზე
  ვარდება. re-review (security-auditor) — დახურულია; nit-ები: გაუპარსავი body არ ითვლება (Decision Log-ში ჩაიწერა),
  ძველი კომენტარი `routes/auth.py`-ში (`a36741f`-ში გასწორდა), A-094.

#### A-081 · nit · `Settings.requires_ssl` TLS-ს URL-ის ნებისმიერ ადგილას ნაპოვნი „localhost"-ით თიშავს
- **ფაილი:** `backend/app/core/config.py` (`requires_ssl`: `not any(host in url for host in ("localhost", "127.0.0.1"))`)
- **სცენარი (კოდით, backend-dev):** `postgresql://postgres:localhost1234@db.<ref>.supabase.co:5432/postgres` → `requires_ssl` False
  → `build_connect_args()` `{}` → დისტანციურ ბაზასთან კავშირი TLS-ის გარეშე, `verify-full`-ზეც. იგივე — user/ბაზის სახელში
  `localhost` ან `127.0.0.1`. ჩვეულებრივ გამოყენებაში (Supabase-ის შემთხვევითი პაროლი) ნაკლებად სავარაუდოა, ამიტომ nit.
- **გამოსწორება:** URL-ის parse და მხოლოდ hostname-ის შედარება `{"localhost","127.0.0.1","::1"}`-თან (`app/db/local_url.py`-ს
  უკვე აქვს ეს ლოგიკა); ტესტი.
- **owner:** backend-dev
- **status:** fixed (verified) — `77f1e58`. `requires_ssl` = `not is_local_database_url(url)`; გაუპარსავი URL, host-ის
  გარეშე ან `?host=`/`?hostaddr=` → TLS; `[::1]` და `LOCALHOST` ლოკალურია. 18 ახალი შემთხვევა ძველ `config.py`-ზე ვარდება
  (მათ შორის `build_connect_args()` → `{}` remote URL-ზე). re-review (security-auditor) — დახურულია; nit: A-092.

#### A-082 · nit · `robots.txt`-ში `/en/search?` არ არის
- **ფაილი:** `frontend/public/robots.txt`
- **სცენარი (კოდით, frontend-dev):** `/search?` აკრძალულია, `/en/search?…` — არა (`routes.jsx:134`, `/en` basename).
- **გამოსწორება:** `Disallow: /en/search?` + ტესტი `robotsTxt.test.js`-ში. (A-048-ში მხოლოდ სამი გზა იყო დამტკიცებული.)
- **owner:** frontend-dev
- **status:** fixed (verified) — `737c83c`. ტესტი ძველ ფაილზე ვარდება (`git stash`). re-review: code-reviewer — დახურულია.

#### A-083 · nit · ორი AppError 429-ს `Retry-After` header არ აქვს
- **ფაილი:** `backend/app/services/auth.py:149` (`_password_check_locked`; წამები მხოლოდ body-ში, `retryAfterSeconds`),
  `backend/app/api/v1/routes/auth.py:248` (`TOO_MANY_RESET_REQUESTS`)
- **გამოსწორება:** `AppError`-ს არასავალდებულო `headers` და `handle_app_error`-ში მისი გადაცემა; reset-ის ლიმიტზე წამები
  `get_window_stats`-ით.
- **owner:** backend-dev
- **status:** fixed (verified) — `a36741f`. `AppError(headers=...)`; ანგარიშის დაბლოკვის 429 — `max(1, retryAfterSeconds)`,
  reset-ის 429 — ფანჯრის დარჩენილი წამები (store → process fallback → 3600). API-ის ყველა 429-ს ახლა Retry-After აქვს;
  შესვლის lock 401-ად რჩება header-ის გარეშე (ტესტით). 8 ტესტი ძველ კოდზე ვარდება. re-review (code-reviewer) —
  დახურულია; nit: A-090.

#### A-084 · nit · docs/deployment.md-ის წვრილმანები (code-reviewer, f5b0cd3-ის re-review)
- **ფაილი:** `docs/deployment.md` (§5 ≈626–670, §10 ≈761, ≈804–814)
- **სცენარი:** (1) CLI ბეჭდავს `FAILED: Target database is not up to date.`, docs კი `CommandError: …`-ს წერს; (2) `--sql`-ის
  placeholder `DATABASE_URL='<ბაზის URL>'` ლაივ პაროლის ჩასმისკენ უბიძგებს, თუმცა `--sql`-ისთვის URL მხოლოდ დიალექტს
  განსაზღვრავს (`postgresql://unused@localhost/unused` საკმარისია); „alembic-ის ნებისმიერ გაშვებას" — `alembic heads` env.py-ს
  არ უშვებს; (3) FORWARDED_ALLOW_IPS-ის შემოწმებაში „ერთი ქსელიდან მნიშვნელობა იცვლება" ქმედების გარეშეა; მობილურ
  ინტერნეტზე CGNAT IP-ს შეიძლება ცვლიდეს (დაუდასტურებელი) — განმეორებითი მოთხოვნები სჯობს Wi-Fi-დან.
- **owner:** backend-dev
- **status:** fixed (reviewed) — `45c8326` (docs; alembic-ის ტექსტი alembic-ის წყაროთი დადასტურდა, ბრძანება არ
  გაშვებულა). re-review (code-reviewer) — დახურულია; nit: A-091.

#### A-085 · nit (მფლობელის გადაწყვეტილება) · storefront-ის HSTS-ის ბლოკს `TEMP-ONRENDER` მარკერი არ აქვს
- **ფაილი:** `frontend/render.yaml:76-88`, `docs/deployment.md` §0 (ცხრილი ≈40–53)
- **სცენარი (კოდით, code-reviewer):** §0 ამბობს, რომ ყველა დროებით მნიშვნელობას `TEMP-ONRENDER` ახლავს და ერთი ძებნით იპოვება.
  `max-age=300` დროებითია, მაგრამ მარკერი არ აქვს, ამიტომ დომენზე გადასვლისას `grep TEMP-ONRENDER` მას გამოტოვებს.
  A-010-ში მფლობელმა მარკერების უცვლელობა მოითხოვა, ამიტომ არ დაემატა (`test_storefront_blueprint.py` რაოდენობას 2-ზე აფიქსირებს).
- **გამოსწორება:** HSTS-ის ბლოკს მარკერი (რაოდენობა ტესტში 3), §0-ის ცხრილში ხაზი `Strict-Transport-Security | max-age=300 |
  max-age=31536000`.
- **owner:** frontend-dev
- **status:** fixed (verified) — `f5f948b`. მფლობელმა მესამე მარკერი დაუშვა (2026-11-16); ძველი ორი ბაიტ-ბაიტ უცვლელია,
  ტესტი 3-ს აფიქსირებს (ძველი 2 ახალ yaml-ზე ვარდება), §0-ში HSTS-ის ხაზი. re-review (code-reviewer) — დახურულია;
  nit: A-093.

#### A-086 · nit · DB TLS-ის წვრილმანები (security-auditor)
- **ფაილი:** `backend/app/db/ssl.py:57`, `:71-80`; `backend/.env.example:59-62`
- **სცენარი (კოდით):** (1) `DB_SSL_MODE=disable` დეპლოიზე WARNING-ის გარეშე გადის (`require`-ზე სუსტია; ჩვენამდეც ასე იყო);
  (2) `require`-ის WARNING `session.py`-ის import-ზე, `configure_logging`-მდე იწერება — უბრალო ტექსტით, თითო worker-ზე (docs ამას
  ამბობს); (3) `.env.example` ახალ WARNING-ს არ ახსენებს.
- **გამოსწორება:** `disable`-ზეც WARNING დეპლოიზე; სურვილისამებრ warning lifespan-ში; `.env.example`-ის კომენტარი.
- **owner:** backend-dev
- **status:** fixed (verified) — `3c72ab5`. `log_tls_mode()` lifespan-ში, `configure_logging`-ის შემდეგ (JSON, ყოველ
  worker-ზე ერთხელ); დეპლოიზე `disable` + არალოკალური host → „unencrypted“ (`not authenticated`-ს არ შეიცავს, მფლობელის
  შემოწმება უცვლელია); `build_connect_args` ჩუმია. 14 ტესტი ძველ კოდზე ვარდება. `.env.example` და docs „ბაზასთან TLS“.
  re-review (code-reviewer) — დახურულია.

#### A-087 · nit · `test_configuring_twice_does_not_stack_a_second_filter` logging-ის გლობალურ მდგომარეობას ბოლომდე არ აბრუნებს
- **ფაილი:** `backend/tests/test_log_secrecy.py:363-378`
- **სცენარი (კოდით, security-auditor):** ტესტი `configure_logging()`-ს იძახებს და `uvicorn.access.disabled = True`-ს, server
  logger-ების handler-ებს და `propagate`-ს არ აბრუნებს. `test_server_log_secrecy.py`-ის `restore_logging` შემდეგ ამას „საწყისად"
  ინახავს, ამიტომ `test_the_access_log_of_uvicorn_is_still_off` `logging.py:215`-ის წაშლას ვეღარ დაიჭერს.
- **გამოსწორება:** ტესტმა `every_line` fixture-ის აღდგენა გამოიყენოს.
- **owner:** backend-dev
- **status:** fixed (verified) — `95c98b5`. ერთი `_logging_restored()` (root, server logger-ები, `uvicorn.access`, slowapi:
  handlers, filters, level, propagate, disabled) fixture-შიც და ამ ტესტშიც + ორი ტესტი, რომ მდგომარეობა ბრუნდება.
  გაჟონვა გაზომილია (probe ტესტმა ძველი ტესტის შემდეგ `disabled=True` ნახა, ახლა — არა). **აუდიტის მექანიზმი არ
  დადასტურდა:** disable-ის ხაზის წაშლა გაჟონვასაც აქრობს, ამიტომ `test_the_access_log_of_uvicorn_is_still_off` ძველ
  ტესტ-ფაილთანაც ვარდება; გაჟონვა ლატენტური იყო. re-review: code-reviewer — დახურულია (configure_logging-ის ყველა ცვლილება
  დაფარულია, მექანიზმის შეფასება სწორია); nit: A-095.

### A-080/A-037/A-081/A-083–A-087-ის re-review-ის მიგნებები (2026-11-16)

#### A-088 · nit · common-სიის შემოწმება ციფრით დაწყებულ/დამთავრებულ ჩანაწერს მორთულ ფორმაში ვერ ცნობს
- **ფაილი:** `backend/app/core/security.py` (`is_common_password`, `_DECORATION`)
- **სცენარი (კოდით, security-auditor):** კიდეებიდან ციფრებიც იჭრება, ამიტომ `1q2w3e4r!` → `q2w3e4r`, `1qaz2wsx!` → `qaz2wsx`,
  `q1w2e3r4!` → `q1w2e3r` — სიაში არ არის, pattern-იც ვერ იჭერს → მიიღება (შიშველი ფორმები უარყოფილია). ასევე
  `passwordpassword`, `P@ssw0rd` (სიტყვის გამეორება, leetspeak — მფლობელის წესის გარეთ).
- **გამოსწორება:** მესამე შემოწმება — მხოლოდ punctuation/whitespace-ით ჩამოჭრილი ფორმა; ტესტი სამივე მაგალითზე.
- **owner:** backend-dev
- **status:** fixed (verified) — მესამე look-up (ციფრები რჩება) + მფლობელის მოთხოვნით pattern-ის წესი ორ მეზობელ რიგს
  შორის keyboard walk-ს იჭერს (`_is_keyboard_walk`). სამივე მაგალითი (და `zaq12wsx`, `1q2w3e4r5t`, `!1q2w3e4r`, …)
  ორივე წესით ცალ-ცალკე უარყოფილია register/change/reset-ზე; არსებული `1q2w3e4r!` hash-ით შესვლა 200 (customer, admin).
  65 ტესტი ძველ `security.py`-ზე ვარდება (`git stash`), 222 გადის. შემთხვევითი 8-სიმბოლოიანი პაროლის უარი 1.1–2.3%
  (ადრე 0.35–0.74%), 12+ — < 0.04%.

#### A-089 · nit · storefront-ი ახალ პაროლის წესს მხოლოდ უარის შემდეგ ამბობს
- **ფაილი:** `frontend/src/pages/Account/ChangePassword.jsx:58`, `frontend/src/pages/ResetPassword.jsx:142`
- **სცენარი (კოდით, security-auditor + backend-dev):** change-password-ზე pattern/common უარი ზოგად `VALIDATION_ERROR`-ს
  („ზოგი მონაცემი არასწორია“) აჩვენებს (ასე იყო common-სიაზეც); ველის მინიშნება ყველას „მინიმუმ 8“-ს უწერს, ადმინსაც.
- **გამოსწორება:** change-password-ზე `newPassword` ველის შეცდომა ისე, როგორც reset-ზე; მინიშნებაში „გამეორება და
  მიმდევრობა არ შეიძლება“. ადმინის 12 — ადმინის პანელის პაროლის შეცვლის ფორმაზე (თუ ასეთი არსებობს).
- **owner:** frontend-dev
- **status:** fixed (verified) — `a4763f3`. ChangePassword/Reset/Register: სერვერის უარი ველთან, toast-ის გარეშე;
  12 ახალი ტესტი ძველ კოდზე ვარდება (`git stash`). ადმინ პანელში პაროლის ფორმა არ არსებობს. re-review:
  security-auditor და code-reviewer — დახურულია. ნარჩენი: A-107.

#### A-090 · nit · reset-ის Retry-After-ის ორი ტესტი გაფუჭებულ ფუნქციასაც გაატარებდა
- **ფაილი:** `backend/tests/test_app_error_headers.py:110-117`, `backend/tests/test_password_reset.py:545-547`
- **სცენარი (კოდით, code-reviewer):** ასერტები `<= 3600` / `1 <= x <= 3600` ყოველთვის სრულდება; თუ `_address_key` ან route-ის
  `scope` შეიცვლება, ფუნქცია `1`-ს დააბრუნებს („სცადე 1 წამში“, ფანჯარა კი საათია) და ტესტები გაივლის.
- **გამოსწორება:** ორივე ადგილას `>= 3590`.
- **owner:** backend-dev
- **status:** fixed (verified) — ორივე `3590 <= x <= 3600`. mutation (`_address_key(...) + "MUTATION"` lookup-ში →
  ფუნქცია 1-ს აბრუნებს): ორივე შეცვლილი ტესტი (reset-ისა — known/unknown) `assert 3590 <= 1`-ზე ვარდება; mutation დაბრუნდა.

#### A-091 · nit · docs/deployment.md: ორი წვრილმანი A-084-ის შემდეგ
- **ფაილი:** `docs/deployment.md` (§10 ≈819-824; §5 ≈640-642)
- **სცენარი (კოდით, code-reviewer):** (1) ცოტა ტრაფიკზე „სხვა მომხმარებლების ხაზები“ არ არის და ახალი bullet „ქსელი/VPN
  შეცვალეთ და გაიმეორეთ“-ზე ტრიალებს — სჯობს საკუთარი საჯარო IP-ის შედარება (`curl -s https://api.ipify.org` ორჯერ);
  (2) `alembic history -i` / `history current:` env.py-ს უშვებს — „`history` (`-i`/`current`-ის გარეშე)“.
- **owner:** backend-dev
- **status:** fixed (reviewed) — §10 ერთ პროცედურად გადაიწერა: ორივე ქსელიდან ორ-ორჯერ ipify + `/health/live`,
  ჯერ IP-ების შედარება, მერე `client`-ის „მიჰყვება IP-ს / არ მიჰყვება"; „სხვა ხაზები" და „VPN შეცვალეთ" წაიშალა.
  §5: `history` (`-i`/`current`-ის გარეშე) — alembic-ის `command.history`-ის კოდით შემოწმდა (`run_env` მხოლოდ
  `current`-ზე ან `-i`/`revision_environment`-ზე). PROGRESS.md-ის A-036 Blocker-იც ამას მიჰყვება. ცოცხალზე არ გაშვებულა.

#### A-092 · nit · `local_url.py`-ის docstring არ ამბობს, რომ TLS-ის გამოტოვებაც მასზეა
- **ფაილი:** `backend/app/db/local_url.py:1-13`, `:36-40`
- **სცენარი (კოდით, security-auditor):** guard-ის მოხერხებულობისთვის `LOCAL_HOSTS`-ის გაფართოება (`db`, `host.docker.internal`)
  ამ ჰოსტებზე TLS-ს ჩუმად გამორთავს (`Settings.requires_ssl`, A-081).
- **გამოსწორება:** docstring-ში ერთი წინადადება.
- **owner:** backend-dev
- **status:** fixed (reviewed) — module docstring-ში და `LOCAL_HOSTS`-თან: `requires_ssl = not is_local_database_url(...)`,
  ასე რომ დამატებული ჰოსტი ბაზას TLS-ის გარეშე უკავშირდება ყველა გარემოში. კოდი უცვლელია.

#### A-093 · nit · `test_storefront_blueprint.py`-ის კომენტარი მარკერებს „მისამართებს“ უწოდებს
- **ფაილი:** `backend/tests/test_storefront_blueprint.py:11` — მესამე მარკერი `max-age=300`-ია; „temporary onrender.com values“.
- **owner:** frontend-dev
- **status:** fixed (reviewed) — backend-ის ტესტის კომენტარია, ამიტომ backend-dev-მა გაასწორა: „temporary onrender.com
  values: the sitemap rewrite target, the connect-src address, and the HSTS max-age=300“ (`frontend/render.yaml`-თან
  შედარებით). `TEMP_ONRENDER_MARKERS` და ასერტები უცვლელია.

#### A-094 · nit (მფლობელის გამონაკლისი) · `/api/v1/health` ლიმიტის გარეშე ბაზას ეხება
- **ფაილი:** `backend/app/api/v1/routes/health.py:56` (`SELECT 1`), `backend/app/core/rate_limit.py` (`HEALTH_PATHS`)
- **სცენარი (კოდით, security-auditor):** ერთ მისამართს შეუძლია `/health`-ს ურტყას ლიმიტის გარეშე, ყოველ ჯერზე pool-იდან
  კავშირით. Render და Docker `HEALTHCHECK` მხოლოდ `/health/live`-ს იყენებენ (Dockerfile:73). მფლობელმა ორივე გამოიყვანა
  ლიმიტიდან — თუ `/health` მხოლოდ ხელით შემოწმებისთვისაა, მისი ლიმიტში დაბრუნება მარტივია.
- **owner:** backend-dev
- **status:** fixed (verified) — მფლობელის გადაწყვეტილებით `/health` → `@limiter.limit("30/minute")` (429 `RATE_LIMITED`
  + `Retry-After`, 300-იან ვედროს არ ხარჯავს); `/health/live` (`LIVENESS_PATH`) — ლიმიტის გარეშე, 350 მოთხოვნა → 200.
  31-ე მოთხოვნის ტესტი ძველ კოდზე ვარდება (`200 == 429`; `git stash`-ით კოლექცია `HEALTH_RATE_LIMIT`-ზე ჩერდება).
  render.yaml / Dockerfile უცვლელია. შესამოწმებელი (Redis socket timeout) — ღიაა, უცვლელი; `/health`-იც ახლა Redis-ს ეხება.
- **შესამოწმებელი (A-080-თან):** ახლა decorator-ის გარეშე ყოველი მოთხოვნა Redis-ის სინქრონულ hit-ს აკეთებს event loop-ზე;
  თუ Redis-მდე პაკეტები ჩუმად იკარგება, redis-py-ის socket timeout-ის გარეშე loop შეიძლება დიდხანს დაიბლოკოს (ადრეც ასე
  იყო decorator-იან route-ებზე). Render Redis-ზე არ შემოწმებულა.

#### A-095 · nit · `test_server_log_secrecy.py`-ის `restore_logging` slowapi-ის filter-ს ტოვებს (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/tests/test_server_log_secrecy.py:32-47`; `backend/tests/test_log_secrecy.py:402-403` (docstring)
- **სცენარი (კოდით, code-reviewer):** `WATCHED`-ში `slowapi` არ არის და filter-ები არ ბრუნდება, ამიტომ `_configure`-ის შემდეგ
  `PseudonymiseRateLimitKey` სესიის ბოლომდე რჩება. `pytest tests/test_server_log_secrecy.py tests/test_rate_limit.py` რიგით
  `test_the_default_limit_warning_does_not_name_the_raw_address` მეორე filter-ს ამატებს, key ორჯერ ფსევდონიმდება და ასერტი
  ვარდება. CI-ის ანბანურ რიგში არ ჩანს (randomly/xdist არ არის). docstring `:402-403` ჯერ კიდევ ამბობს, რომ გაჟონვა
  წაშლილ ხაზს მალავდა — 95c98b5-მა აჩვენა, რომ არა.
- **გამოსწორება:** `_logging_restored` → `tests/factories.py`, `restore_logging`-მაც ის გამოიყენოს (+ `voltbox.error`);
  docstring-ის გასწორება.
- **owner:** backend-dev
- **status:** fixed (verified) — `logging_restored()` / `logging_state()` → `tests/factories.py` (root, server logger-ები,
  `uvicorn.access`, `slowapi`, `voltbox.error`: handlers, filters, level, propagate, disabled); `restore_logging` მას
  იყენებს, `WATCHED` წაიშალა; A-087-ის docstring გასწორდა. `pytest tests/test_server_log_secrecy.py tests/test_rate_limit.py`
  ძველ ტესტ-ფაილებზე 1 failed (`git stash`, ორკესტრატორმაც გაიმეორა), ახლა 131 passed; შებრუნებული რიგიც და ცალ-ცალკეც გადის.

### A-055–A-059/A-075/A-077–A-079-ის გასწორებისა და re-review-ის მიგნებები (2026-11-16)

ორი should-fix დეველოპერებმა გასწორების დროს იპოვეს; ორივე ჩვენამდეც ასე იყო და ამ გაშვების scope-ის (მხოლოდ მითითებული
ID-ები) გარეთაა, ამიტომ ღიად დარჩა.

#### A-096 · should-fix · PNG, რომელიც IEND-ის header-ის შუაშია მოჭრილი, `verify()`-ზე `SyntaxError`-ს აგდებს → 500 (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`validate_image`, `except (UnidentifiedImageError, OSError, ValueError)`)
- **სცენარი (გაშვებით, backend-dev, დროებითი ტესტი წაიშალა):** 64×64 PNG, ბოლოდან 5 ან 8 ბაიტი მოჭრილი (IEND-ის 4-ბაიტიანი
  სიგრძე რჩება, header არასრულია) → Pillow `SyntaxError: broken PNG file (chunk b'IEN')`; ის `except`-ში არ არის და HTTP-ის
  test client-მა `ExceptionGroup`-ად ამოაგდო → uvicorn-ქვეშ 500. 1/3/11 ბაიტზე — 400, როგორც საჭიროა. ნაწილობრივ
  ჩამოტვირთული ფაილის ატვირთვა (მხოლოდ ადმინი) generic შეცდომას იღებს `INVALID_IMAGE`-ის ნაცვლად.
- **გამოსწორება:** `SyntaxError` `except`-ის tuple-ში + HTTP ტესტი ამ ორ ზომაზე (400 `INVALID_IMAGE`).
- **owner:** backend-dev
- **status:** fixed (verified), `e7487a4` (ტესტი ძველ კოდზე ვარდება: 5 და 8 ბაიტი); security-auditor — დახურულია.

#### A-097 · should-fix · >1600 px (ან მოსაბრუნებელი) JPEG, რომლის entropy data დაზიანებულია, `shrink_to_fit`-ში `OSError`-ს აგდებს → 500 (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`shrink_to_fit`: `image.thumbnail` / decode)
- **სცენარი (გაშვებით `shrink_to_fit`-ის დონეზე, backend-dev; HTTP-ზე არა):** 1700×1300 JPEG, EOI მოჭრილი, ან `FF`-ით, ან
  `FF D8`-ით ჩანაცვლებული — `validate_image` იღებს (`verify()` SOS-ის შემდეგ არაფერს ამოწმებს), decode კი `OSError: image file
  is truncated` / `broken data stream`-ს აგდებს. `prepare_upload` მას `ValidationError`-ად არ აქცევს → 500. ეს A-059-ის
  აუდიტის ზუსტი მაგალითია.
- **გამოსწორება:** decode/re-encode-ის `OSError` → `INVALID_IMAGE` (მხოლოდ Pillow-ის decode-ის ირგვლივ) + HTTP ტესტი სამივე კუდზე.
- **owner:** backend-dev
- **status:** fixed (verified), `d503a1e` (24 HTTP ტესტი — JPEG, PNG, WebP; ყველა ძველ კოდზე ვარდება); security-auditor — დახურულია.

#### A-098 · nit · JFIF APP0-ის შიდა thumbnail (და APP14 12 ბაიტის მიღმა) ბაიტ-ბაიტ ინახება (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`_strip_jpeg`-ის `keep`)
- **სცენარი (კოდით, security-auditor):** `JFIF\0` APP0 მთლიანად კოპირდება; payload-ის 12–13 ბაიტი Xthumbnail/Ythumbnail-ია,
  რომელსაც 3·X·Y ბაიტი შეუკუმშავი RGB მოსდევს (≈147×148-მდე) — crop-მდელი კადრის მინიატურა შეიძლება საჯარო ფაილში დარჩეს.
  ტელეფონები thumbnail-ს APP1-ში წერენ (ის იშლება), ამიტომ რეალურად იშვიათია; `shrink_to_fit`-ის docstring კი „thumbnails"-ის
  წაშლას გვპირდება.
- **გამოსწორება:** JFIF-დან მხოლოდ პირველი 14 ბაიტი, thumbnail-ის ზომა 0, სიგრძე 16; APP14-დან პირველი 12 ბაიტი. ტესტი
  Xthumb/Ythumb ≠ 0-ით.
- **owner:** backend-dev
- **status:** fixed (verified), `5a31a38` (7 ტესტიდან 3 ძველ კოდზე ვარდება, დანარჩენი ინვარიანტია); code-reviewer — დახურულია.

#### A-099 · nit · `import_products.py`: `reviewsCount` წინასწარ არ მოწმდება, `isActive` ტექსტს `"false"`-ს `True`-ად კითხულობს (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/scripts/import_products.py` (`import_one`: `int(row.get("reviewsCount", 0))`, `bool(row.get(...))`)
- **სცენარი (კოდით, code-reviewer, backend-dev):** `"reviewsCount": 3000000000` → dry-run OK, ნამდვილი გაშვება int4 overflow-ზე
  ჩერდება; `"abc"` → raw `ValueError` (A-078-ის „dry-run ტყუის" კლასი). `"isActive": "false"` ჩუმად აქტიური ხდება.
- **გამოსწორება:** `to_int` + დიაპაზონი `reviewsCount`-ზე `validate()`-ში; boolean ველებზე `isinstance(value, bool)`.
- **owner:** backend-dev
- **status:** fixed (verified), `3a5aef4` (42 შემთხვევა ძველ კოდზე ვარდება); code-reviewer — დახურულია.

#### A-100 · nit · WEBP-ის `DECODE_COST` `method=6`-ით იყო გაზომილი; `method=5`-ზე ზედა ზღვარია
- **ფაილი:** `backend/app/services/storage.py` (`DECODE_COST["WEBP"]`, კომენტარი)
- **სცენარი (გაზომვით Windows-ზე, backend-dev):** A-056-ის შემდეგ ბიუჯეტის ყველაზე ძვირი WebP 90 → 58 MiB-ია, lossy RGBA
  97 → 82. ზღვარი უსაფრთხოა, მაგრამ WebP-ს 1.9 MP-ზე მეტს არ აძლევს, თუმცა შეიძლება შეეძლოს. მფლობელმა `DECODE_COST`
  უცვლელად დატოვა.
- **გამოსწორება:** production image-ში (Linux) `TestDecodeMemoryIsBounded`-ის WEBP-ის ხელახალი გაზომვა; მერე გადაწყვეტა.
- **owner:** backend-dev (გადაწყვეტა — მფლობელის)
- **status:** fixed (verified), `ddde89e` — Linux-ზე გაიზომა (production image), `DECODE_COST["WEBP"]` უცვლელია (cut-out ბიუჯეტს 2.3–2.6 MP-ზე აღწევს); გაზომვამ A-103 იპოვა; code-reviewer — დახურულია.

#### A-101 · nit · >1600 px APNG / ანიმირებული WebP ერთ ფრეიმად ინახება, პატარა — ანიმაციით (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`shrink_to_fit`), `validate_image`
- **სცენარი (გაშვებით, backend-dev):** A-058-ის შემდეგ ≤1600 ანიმაცია ყველა ფრეიმს ინახავს; დიდი re-encode-ზე პირველ ფრეიმად
  იქცევა. ორივეს `validate_image` იღებს.
- **გამოსწორება:** მფლობელის გადაწყვეტილება — ანიმირებული პროდუქტის ფოტო საჭიროა? თუ არა, `validate_image` უარყოფს ანიმაციას.
- **owner:** backend-dev (გადაწყვეტა — მფლობელის: ანიმაცია პროდუქტის ფოტოსთვის საჭირო არ არის)
- **status:** fixed (verified), `da165ea` — 400 `IMAGE_ANIMATED`, ტექსტი ka/en.json-ში, vitest; 10 backend ტესტი და vitest ძველ კოდზე ვარდება; security-auditor — დახურულია (გვერდის ავლა ორი `acTL`-ით → A-104).

### A-096–A-101-ის გასწორებისა და re-review-ის მიგნებები (2026-11-16)

A-102 security-auditor-მა იპოვა და მფლობელის წესის („არცერთი სურათის შეცდომა 500-მდე") ფარგლებში იმავე გაშვებაში
გასწორდა. A-103 A-100-ის გაზომვამ აჩვენა; მისი ღირებულება მფლობელის გადაწყვეტილებაა. ოთხივე ჩვენამდეც ასე იყო.

#### A-102 · should-fix · JPEG, რომლის SOF ნაკლებ კომპონენტს ჩამოთვლის, ან PNG IDAT-ის გარეშე → `IndexError` → 500 (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`validate_image`-ის except)
- **სცენარი (security-auditor — კოდით; backend-dev — HTTP-ზე გაშვებით):** (1) SOF0 ამბობს Nf=3, ჩამოთვლის 0/1/2 კომპონენტს —
  Pillow `layer`-ს ჩამოთვლილით ავსებს, `_decode_cost` → `JpegImagePlugin.get_sampling` → `layer[1]` → `IndexError`;
  (2) signature + IHDR + IEND სწორი CRC-ებით — `verify()` → `self.tile[0]` → `IndexError`. Pillow `IndexError`-ს `SyntaxError`-ად
  მხოლოდ `_open`-ის შიგნით აქცევს.
- **გამოსწორება:** `IndexError` except-ის დახურულ tuple-ში (try-ში ჩვენი კოდი არაფერს ინდექსავს) + HTTP ტესტები.
- **owner:** backend-dev
- **status:** fixed (verified), `fbb132a` (4 ტესტი ძველ კოდზე ვარდება, `git stash`); security-auditor — დახურულია.

#### A-103 · should-fix · RGBA WebP, რომლის alpha ხმაურია, ბიუჯეტზე მეტს ხარჯავს (108–113 MiB / 100); ტესტის ფიქსტურა ამას ვერ აჩვენებს (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`DECODE_COST["WEBP"] = (71 MiB, 16)`), `backend/tests/test_admin_images.py`
  (`TestDecodeMemoryIsBounded`-ის WEBP ფიქსტურა ერთფეროვანია)
- **სცენარი (გაზომვით, backend-dev, production image Linux-ზე — Docker Desktop WSL2, Pillow 13.0.0, libwebp 1.6.0,
  `method=5`):** 1601×1187 (ბიუჯეტის მაქსიმუმი) — ერთფეროვანი RGBA 51 MiB, soft-edged cut-out 82.5, ხმაურიანი alpha
  108.8, RGBA ხმაური lossy 109.4 / lossless 113.4. მხოლოდ მოტრიალების გზაზე (orientation 6, 1378×1378 / 1600×1187):
  107.9–108.1 და 112.5–112.8. decode 47–55 MiB-ია ყოველთვის; libwebp-ის alpha encoder ხმაურზე +58 MiB-ს იღებს. ატვირთვა
  მხოლოდ ადმინს შეუძლია; `config.py`-ის არითმეტიკით (512 MB, 2 worker) 2 × 113 MiB მაინც ეტევა — OOM არ არის, მაგრამ
  ბიუჯეტის დაპირება ირღვევა. A-056-მდე (`method=6`) ალბათ უარესიც იყო.
- **გამოსწორება (მფლობელის გადაწყვეტილება):** (ა) ხმაურიანი alpha-ს ფიქსტურა ტესტში + WebP-ის ახალი ფასი (backend-dev-ის
  შეფასებით ≈ (7 MiB, 56 B/px), ≈ 1.5 MP; code-reviewer-ის მოდელით ≈ 1.0 MP — გაუზომავია, ჯერ გაზომვა; ორივე დღევანდელზე
  მკაცრია: 1601×1187 WebP აღარ მიიღება); (ბ) გადაჭარბების მიღება Accepted Risks-ში;
  (გ) re-encode `alpha_quality < 100`-ით ან `method=4`-ით — ჯერ გაზომვა.
- **owner:** მფლობელი (შემდეგ backend-dev)
- **status:** accepted (მფლობელი, 2026-11-16, ვარიანტი ბ) — `PROJECT.md` Accepted Risks; კოდი და `DECODE_COST` უცვლელია.
  კომენტარები და docstring-ები, რომლებიც სხვას ამბობდა, გასწორდა (`72361f8`).

#### A-104 · nit · APNG ორი `acTL` chunk-ით Pillow-ს ერთ ფრეიმად ეჩვენება და `IMAGE_ANIMATED`-ს გვერდს უვლის (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`validate_image`-ის `n_frames`, `_PNG_KEPT`)
- **სცენარი (კოდით, security-auditor; ბრაუზერში არ შემოწმებულა):** IDAT-მდე მეორე `acTL`-ზე Pillow `n_frames`-ს 1-ად ტოვებს
  (`PngImagePlugin.py:712-715`); ≤1600 და orientation 1 ფაილს byte-strip ორივე `acTL`-ს და ყველა `fcTL`/`fdAT`-ს უნახავს —
  ბრაუზერმა შეიძლება ააანიმიროს. ასევე `acTL num_frames=1` + ზედმეტი `fcTL`/`fdAT` (backend-dev): მკვდარი ბაიტები. ფაილი
  განზრახ უნდა აეწყოს და მხოლოდ ადმინს შეუძლია ატვირთვა.
- **გამოსწორება:** `_PNG_KEPT`-იდან `acTL`/`fcTL`/`fdAT` ამოიღონ (ყოველი მიღებული APNG ერთკადრიანია, მისი IDAT ფრეიმი 0-ია,
  ასე რომ შენახული ფაილი სტატიკური PNG ხდება) — Decision Log-ის „What still holds" და walker-ის ტესტების განახლებით.
- **owner:** backend-dev
- **status:** fixed (verified) — `_PNG_KEPT`-ში acTL/fcTL/fdAT აღარ არის; ორი-`acTL`-იანი და `acTL`=1 + ზედმეტი ფრეიმის
  ფაილი სტატიკურ PNG-ად ინახება (იგივე პიქსელები). 7 ტესტი ძველ `storage.py`-ზე ვარდება (`git stash`, ორკესტრატორმაც
  გაიმეორა), `test_admin_images.py` 226 გადის.

#### A-105 · nit · „re-encode უფრო დიდი გამოვიდა → stripped ორიგინალი" წესი 1600 px-ზე გრძელ სურათს ინახავს (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py` (`shrink_to_fit`-ის ბოლო, „A re-encode that came out larger…")
- **სცენარი (გაშვებით, backend-dev, სინთეზური ფაილით):** 1700×50 `I;16` PNG გლუვი/პერიოდული მონაცემით — re-encode ორიგინალზე
  დიდია, ამიტომ 1700×50 ინახება, `MAX_STORED_EDGE`-ის მიუხედავად. decode-ის ბიუჯეტით შეზღუდულია და კოდში აღწერილია;
  ნამდვილ ფოტოზე არ დაფიქსირებულა.
- **გამოსწორება:** თუ საჭიროა — „უფრო პატარა" წესი მხოლოდ მაშინ, როცა ორიგინალი ზღვარშია.
- **owner:** backend-dev
- **status:** fixed (verified) — წესი წაიშალა: decode მხოლოდ ზღვარს გადაცილებულ ან მოსაბრუნებელ სურათზე ხდება, ხოლო
  შედარება მხოლოდ orientation 1-ზე ეშვებოდა, ასე რომ „მხოლოდ ზღვარში მყოფზე" პირობა არასდროს შესრულდებოდა. decode-ის
  შემდეგ ყოველთვის re-encode ინახება. 4 ტესტი (1700×50 `L`/`I;16`, პირდაპირ და HTTP-ით) ძველ კოდზე ვარდება (`git stash`).

#### A-106 · nit · ორი ძველი კომენტარი WebP-ის ღირებულებაზე ზედმეტს ამბობს (ჩვენამდეც ასე იყო)
- **ფაილი:** `backend/app/services/storage.py:393-394`, `backend/tests/test_admin_images.py` (`largest_that_fits`, `largest_that_is_turned`)
- **სცენარი (კოდით, code-reviewer):** „A WebP buys roughly a third of the pixels a phone's JPEG does" — `DECODE_COST`-ით 1.9 / 13.3
  MP ≈ მეშვიდედია (იმავე ფაილის WEBP-ის კომენტარიც ასე ამბობს). `largest_that_fits` / `largest_that_is_turned`: „the most
  expensive image(s)" — WebP-ზე მხოლოდ ფორმით (შინაარსი, A-103, ასევე მნიშვნელოვანია).
- **გამოსწორება:** „roughly a seventh" (ან რიცხვები); „the most expensive shape".
- **owner:** backend-dev
- **status:** fixed (reviewed) — მხოლოდ კომენტარები: „a seventh … 13.3 megapixels against 1.9" (JPEG 4:2:0 vs WEBP,
  100 MiB-ზე); `largest_that_fits` / `largest_that_is_turned` — „shape", A-103-ის მითითებით. კოდი და მნიშვნელობები უცვლელია.

### A-089/A-049/A-047/A-050/A-052–A-054/A-064/A-082-ის გასწორებისა და re-review-ის მიგნებები (2026-11-17)

#### A-107 · nit · `Profile.jsx`-ზე დაკავებული ელფოსტა http რეჟიმში მხოლოდ toast-ით ჩანს (ჩვენამდეც ასე იყო)
- **ფაილი:** `frontend/src/pages/Account/Profile.jsx:92`
- **სცენარი (კოდით, security-auditor + code-reviewer):** `error?.details?.email` მხოლოდ mock-ის ფორმას ემთხვევა; ნამდვილი API
  `EMAIL_ALREADY_EXISTS`-ს `details`-ის გარეშე აბრუნებს. A-089-მა იგივე Register-ზე გაასწორა (კოდით შემოწმება).
- **გამოსწორება:** Register-ის მსგავსად `error?.details?.code === 'EMAIL_ALREADY_EXISTS'` → email ველთან, toast-ის გარეშე; ტესტი.
- **owner:** frontend-dev
- **status:** open

#### A-108 · nit (დაუდასტურებელი) · refresh-ის `fetch`-ს ვადა არ აქვს (ჩვენამდეც ასე იყო)
- **ფაილი:** `frontend/src/services/session.js:~228`
- **სცენარი (კოდით, code-reviewer):** refresh-ის მოთხოვნას `timeoutSignal` არ აქვს. თუ სერვერი კავშირს იღებს და არასდროს პასუხობს,
  ყველა მოთხოვნა, რომელიც ამ refresh-ს ელოდება, ჩერდება. ჩვეულებრივ მოთხოვნებს httpClient-ის timeout აქვს. გაშვებით არ შემოწმებულა.
- **გამოსწორება:** იგივე timeout, რაც httpClient-ის მოთხოვნებს; ვადის გასვლა = ქსელის შეცდომა (სესია რჩება, `apiErrors.network`).
- **owner:** frontend-dev
- **status:** open

#### A-109 · nit · `/en`-ზე ინგლისური chunk წინასწარ არ იტვირთება
- **ფაილი:** `frontend/src/i18n/index.js` (`loadEnglish`), `frontend/index.html`
- **სცენარი (A-047-ის trade-off):** `en-*.js` (9.01 kB gzip) entry-ის შესრულების შემდეგ ითხოვება — ინგლისურ გვერდს პირველ
  რენდერამდე ერთი დამატებითი round trip აქვს. ქართულ გვერდს არ ეხება.
- **გამოსწორება (თუ საჭირო გახდება):** `/en`-ზე `modulepreload` ინგლისური chunk-ისთვის (build-ის დროს ცნობილი სახელით).
- **owner:** frontend-dev
- **status:** open

#### A-110 · should-fix · კატეგორიების ერთი ჩავარდნილი ჩატვირთვა ყველა კატეგორიის გვერდს „ვერ მოიძებნა"-დ აქცევს reload-მდე (ჩვენამდეც ასე იყო)
- **ფაილი:** `frontend/src/hooks/useProducts.js:~95` (`useCategories`), `frontend/src/pages/Category.jsx:~55`
- **სცენარი (კოდით, code-reviewer; ორკესტრატორმა წაიკითხა):** `categoriesPromise` უარყოფილ promise-საც ინახავს გვერდის
  სიცოცხლის ბოლომდე. `GET /categories` ერთხელ ჩავარდა (ქსელი, deploy, 5xx) → ყოველი შემდეგი `useCategories` იმავე rejected
  promise-ს იღებს, `Category.jsx`-ის `!categoriesLoading && !category` → „კატეგორია ვერ მოიძებნა", retry არსად არის — მხოლოდ
  სრული reload შველის. `useDeliveryRules.js:19-22` (`loadDeliveryRules`) იგივე cache-ს `.catch`-ში ასუფთავებს; აქ — არა.
  გაშვებით არ შემოწმებულა. ამ ბრენჩის ფარგლებს (დამტკიცებული ID-ები) სცდება, ამიტომ არ გასწორებულა.
- **გამოსწორება:** `loadDeliveryRules`-ის pattern: `api.getCategories().catch((e) => { categoriesPromise = null; throw e; })`;
  ტესტი: ჯერ ჩავარდნა, მერე წარმატება — მეორე mount კატეგორიას აჩვენებს.
- **owner:** frontend-dev
- **status:** open
