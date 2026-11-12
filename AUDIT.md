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

ყველას status: open.

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
  eslint ✅ · **vitest 677 / 57** (baseline 672 + 5). საბოლოო შემოწმება — ქვემოთ, tester.

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
- **status:** open

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
- **status:** open

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
- **status:** open

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
- **status:** open

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
- **status:** open

### Nit

#### A-038 · nit · უზარმაზარი `page` საჯარო endpoint-ზე 500-ს აბრუნებს
- **ფაილი:** `backend/app/core/pagination.py:22` (`page: int = Field(default=1, ge=1)`) და ყველა სხვა `page` პარამეტრი
- **სცენარი:** `GET /api/v1/products?page=9223372036854775807` (ავტორიზაციის გარეშე) → 500, asyncpg:
  `value out of int64 range` (OFFSET). იგივე `GET /admin/orders`-ზე.
- **გამოსწორება:** `le=10_000` ყველა `page`-ზე → 400 `VALIDATION_ERROR`. ტესტი: 10 000 გადის, 10 001 → 400.
- **owner:** backend-dev
- **status:** open

#### A-039 · nit · ერთი ელფოსტით ერთდროული რეგისტრაცია 409-ის ნაცვლად 500-ს აბრუნებს
- **ფაილი:** `backend/app/services/auth.py:79-88` (ჯერ SELECT, მერე INSERT); შეამოწმე `:698`-ის მსგავსი გზაც
- **სცენარი:** gunicorn, 2 worker: `[201, 500]`. მეორე მოთხოვნა unique constraint-ზე ვარდება. იწვევს A-034-ს.
- **გამოსწორება:** ამ constraint-ის `IntegrityError` → იგივე `EMAIL_ALREADY_EXISTS` (409); SELECT რჩება.
  ტესტი ნამდვილ ბაზაზე, `asyncio.gather`-ით: `[201, 409]`.
- **owner:** backend-dev
- **status:** open

#### A-040 · nit · ერთდროული „ძირითადი მისამართის“ შექმნა 500-ს აბრუნებს
- **ფაილი:** `backend/app/services/address.py:55-80` (`_clear_other_defaults`, `create`);
  `uq_addresses_one_default_per_user` (`backend/app/db/models/users.py:111`)
- **სცენარი:** 6 ერთდროული `POST /addresses` `isDefault: true`-ით, 3 რაუნდი → 18-დან 11 იყო 500. ორი ტრანზაქცია
  ერთდროულად ასუფთავებს ძველ default-ს და ორივე ახალს წერს — partial unique index-ზე ვარდება. იწვევს A-034-ს.
- **გამოსწორება:** `_clear_other_defaults`-მდე მომხმარებლის რიგის lock (`SELECT ... FROM users WHERE id = :id FOR UPDATE`)
  იმავე ტრანზაქციაში; იგივე update-ის გზაზეც. ტესტი: 4 ერთდროული → არცერთი 500, ბოლოს ზუსტად ერთი default.
- **owner:** backend-dev
- **status:** open

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
- **status:** open

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
- **status:** open

#### A-043 · nit · შეკვეთის ნომრის თარიღი UTC-ია, არა თბილისის
- **ფაილი:** `backend/app/services/order.py:76` (`to_char(now(), 'YYYYMMDD')`)
- **სცენარი:** ბაზის დროის სარტყელი UTC-ია, ამიტომ თბილისის დროით 00:00–04:00 შორის მიღებული შეკვეთა წინა დღის
  თარიღს იღებს (`VB-YYYYMMDD-…`).
- **გამოსწორება:** `to_char(now() AT TIME ZONE 'Asia/Tbilisi', 'YYYYMMDD')`. ტესტი: SQL-ის დონეზე, დროის სარტყლით.
- **owner:** backend-dev
- **status:** open

#### A-044 · nit · `manage_admin.py` ელფოსტას არ ამოწმებს — იქმნება ადმინი, რომელიც ვერასოდეს შევა
- **ფაილი:** `backend/scripts/manage_admin.py:60-76`
- **სცენარი:** `create-admin --email audit-admin@example.test` → ადმინი შეიქმნა. `/auth/login` კი ამ ელფოსტას 400-ით
  უარყოფს (`EmailStr`-ს `.test` დომენი არ მოსწონს), ამიტომ ეს ანგარიში გამოუსადეგარია.
- **გამოსწორება:** იგივე ვალიდაცია, რაც `app/schemas/auth.py`-ში (pydantic `EmailStr` / `TypeAdapter`), სამივე
  ბრძანებაში; არავალიდურზე `SystemExit` გასაგები ტექსტით. ტესტი.
- **owner:** backend-dev
- **status:** open

#### A-045 · nit · ძებნაში სიტყვების რაოდენობა შეუზღუდავია
- **ფაილი:** `backend/app/services/search.py:187`
- **სცენარი:** 100 ერთასოიანი სიტყვა → 89 მწმ (`/search`), 116 მწმ (`/products?q=`); ჩვეულებრივი ძებნა — 14 მწმ
  (61 პროდუქტზე). სხვაობა კატალოგთან ერთად იზრდება; endpoint საჯაროა.
- **გამოსწორება:** მაქსიმუმ 8 token (stopword-ების შემდეგ), დანარჩენი ჩუმად იკვეთება. ტესტი.
- **owner:** backend-dev
- **status:** open

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
- **status:** open

#### A-047 · nit · ორივე ენის და ადმინის ყველა ტექსტი storefront-ის საწყის bundle-შია
- **ფაილი:** `frontend/src/i18n/*`, `frontend/vite.config.js`
- **სცენარი:** `npm run build` (http): `constants-*.js` 84.75 kB (22.34 kB gzip) შეიცავს ქართულს, ინგლისურს და ადმინის
  ტექსტებს, და ყველა გვერდზე იტვირთება. საწყისი JS ჯამში ≈ 138 kB gzip.
- **გამოსწორება:** ინგლისური — მხოლოდ `/en`-ზე, ადმინის ტექსტები — ადმინის chunk-ში. build-ის ზომები ცვლილებამდე
  და შემდეგ — report-ში.
- **owner:** frontend-dev
- **status:** open

#### A-048 · nit · `robots.txt` ინგლისურ პირად გვერდებს არ ფარავს
- **ფაილი:** `frontend/public/robots.txt:8-11`
- **სცენარი:** იკრძალება `/admin`, `/checkout`, `/account`, `/cart`, მაგრამ არა `/en/checkout`, `/en/account`, `/en/cart`.
- **გამოსწორება:** დაემატოს `/en/` ვარიანტები.
- **owner:** frontend-dev
- **status:** open

#### A-049 · nit · frontend-ის 9 ფაილს ტესტი საერთოდ არ აქვს; 22 `act()` გაფრთხილება
- **ფაილი:** `frontend/src/pages/Register.jsx`, `frontend/src/pages/Account/Addresses.jsx`,
  `frontend/src/components/catalog/Pagination.jsx`, `frontend/src/components/search/SearchSuggestions.jsx`,
  `frontend/src/admin/pages/{InventoryList,CustomerList,CategoryList,CustomerDetail,AdminDashboard}.jsx`
- **სცენარი:** `vitest --coverage`: ამ ფაილებზე 0% ხაზი; ჯამში ხაზები 67.5%, ფუნქციები 55.9%. `npm test`-ის
  გამოსავალში 22-ჯერ `not wrapped in act(...)` (მაგ. `ToastProvider`).
- **გამოსწორება:** ტესტები პრიორიტეტით: Register (ვალიდაცია, redirect, სერვერის შეცდომა), Addresses (CRUD, default),
  Pagination; ადმინის გვერდებზე smoke (რენდერი, ცარიელი მდგომარეობა, შეცდომა). `act()` გაფრთხილებები გასწორდეს.
- **owner:** frontend-dev
- **status:** open

#### A-050 · nit · დოკუმენტაცია კოდს ჩამორჩება
- **ფაილი / სცენარი:**
  - `README.md:11`, `frontend/README.md:60` — „React Router 6“, `package.json` — `react-router ^7.18.4`;
  - `frontend/vite.config.js:51` — `vendor` „66.9 kB“, build-ში vendor 89.04 kB gzip;
  - `frontend/src/context/AuthContext.jsx:8` — „MOCK ONLY — replace with real auth API“ (რეალური API კარგა ხანია მუშაობს);
  - `TODO.md` №18 — „სრული e2e CI-ში არაა“, `.github/workflows/e2e.yml` კი არსებობს (განრიგით + `workflow_dispatch`).
- **გამოსწორება:** ოთხივე ადგილი სიმართლეს შეესაბამოს.
- **owner:** task-executor
- **status:** open

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
- **status:** open

#### A-053 · nit · A-030-ის ტესტი შეცდომის status-ს არ აფიქსირებს
- **ფაილი:** `frontend/src/services/sessionLost.test.js:122`
- **სცენარი (კოდით):** ტესტი მხოლოდ `error.name !== 'SessionExpiredError'`-ს ამოწმებს. `AdminSessionContext.jsx:50`
  „unreachable" ეკრანს მხოლოდ არა-401 შეცდომაზე აჩვენებს; თუ `ApiError(..., 0)` ოდესმე 401-იანი შეცდომით
  შეიცვლება, ტესტი გაივლის, ადმინი კი refresh-ის 503-ზე login-ზე გადავა.
- **გამოსწორება:** `expect(error).toMatchObject({ name: 'ApiError', status: 0 })`.
- **owner:** frontend-dev
- **status:** open

#### A-054 · nit · `session.js`-ის ორი კომენტარი ახალ ქცევას აღარ ემთხვევა
- **ფაილი:** `frontend/src/services/session.js:89` („Called on logout and when a refresh fails" — ახლა მხოლოდ 401-ზე
  ან token-ის გარეშე 2xx-ზე); `:222-223` („let the caller surface the original error" — caller ახლა
  `apiErrors.fallback`-ს აჩვენებს; ქსელის შეცდომაზე `apiErrors.network` უფრო ზუსტი იქნებოდა).
- **გამოსწორება:** კომენტარების ტექსტი; სურვილისამებრ ქსელის შემთხვევაში `apiErrors.network`.
- **owner:** frontend-dev
- **status:** open
