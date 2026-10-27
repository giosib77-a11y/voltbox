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
