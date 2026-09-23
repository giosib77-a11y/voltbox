# მრავალსაფეხურიანი build — საბოლოო იმიჯში კომპილატორი და dev-პაკეტები არ რჩება.
#
# `# syntax=` ხაზი განზრახ არ არის. ის BuildKit-ს build-ის დროს Docker Hub-იდან
# parser-ის image-ს ჩამოატვირთინებს და გაუშვებინებს: tag-ით გადაწერადს, digest-ით
# გაყინულს. აქ დაწერილს builder-ში ჩაშენებული parser-ი სრულად კითხულობს —
# `RUN --mount`, heredoc და სხვა ახალი სინტაქსი არ გამოიყენება. ამიტომ ჩამოტვირთვა
# არაფერს გვაძლევს. თუ ასეთი სინტაქსი დაგჭირდათ, ხაზი digest-ით დაამატეთ, FROM-ის
# მსგავსად, და მაშინ მისი განახლებაც ხელით მოგიწევთ.
#
# base image digest-ით, ორივე stage-ში ერთი: tag-ი გადაწერადია, digest-ი — არა.
# ვერსია tag-შია, იმავე ხაზზე: როცა ორივე წერია, Docker digest-ს იღებს და tag-ი
# მხოლოდ წასაკითხია. ხაზის ბოლოს comment-ი შეუძლებელია — Dockerfile-ში `#`
# მხოლოდ ხაზის თავშია comment-ი; გაზომილი: FROM-ი parse-ზე ჩავარდა.
# ფასი: Debian-ის security fix-ები image-ში მხოლოდ digest-ის განახლებით შემოდის.
# ამას Dependabot-ი აკეთებს (.github/dependabot.yml-ის `docker` entry, 7-დღიანი
# cooldown-ით). ლოდინი თუ არ შეიძლება, ხელით — Digest და PYTHON_VERSION აქედან:
#   docker buildx imagetools inspect python:3.14-slim
#   docker buildx imagetools inspect python:3.14-slim --format '{{json (index .Image "linux/amd64").Config.Env}}'
FROM python:3.14.7-slim-trixie@sha256:ef30e8ee3a7f227b0b5b39669b2e656f35b56b918c6631820357c2a55ff5a428 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build

# დამოკიდებულებები lock-იდან, კოდამდე: ყველა ვერსია ფიქსირებულია, ყველა ფაილი
# hash-ით მოწმდება, და ეს layer-ი მხოლოდ lock-ის ცვლილებაზე ხელახლა აეწყობა.
# pip-ი image-ისაა და განზრახ არ ახლდება — `--upgrade pip` ერთადერთ download-ი
# იქნებოდა, რომელსაც არაფერი ამოწმებს, თანაც ზუსტად ის, ვინც hash-ებს ამოწმებს.
# lock-ები Linux container-ში generate-დება, არასდროს laptop-ზე — იხ. README.
# --only-binary: hash-ი wheel-ზე რომ არ ემთხვეოდეს, pip-ი refuse-ის ნაცვლად
# ჩუმად sdist-ზე გადავიდოდა და მის build backend-ს ვერსიისა და hash-ის გარეშე
# ჩამოწერდა. გაზომილი: fastapi-ის wheel-ის hash-ში ერთ სიმბოლოს შეცვლის შემდეგ
# install-ი ამის გარეშე exit 0-ით გავიდა, ამით — „DO NOT MATCH THE HASHES".
COPY requirements.txt requirements-build.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes --only-binary=:all: -r requirements.txt \
    && python -m venv /opt/build \
    && /opt/build/bin/pip install --require-hashes --only-binary=:all: -r requirements-build.txt

# პროექტი: wheel-ს lock-ის hatchling-ი აგებს ცალკე venv-ში. build isolation-ით pip-ი
# hatchling-ს ვერსიისა და hash-ის გარეშე ჩამოწერდა, და მის კოდი ამ stage-ში,
# /opt/venv-ის გვერდით ეშვებოდა; /opt/build-ი runtime-ში არ ხვდება.
# --no-deps: lock-ის მიღმა pip-ი არაფერს resolve-ავს.
# pip check: pyproject.toml-ში დამატებული, lock-ში კი regenerate-ის გარეშე
# დარჩენილი დამოკიდებულება build-ს აქ ჩერს, არა production-ში.
COPY pyproject.toml README.md ./
COPY app ./app
RUN /opt/build/bin/pip wheel --no-deps --no-build-isolation --check-build-dependencies --wheel-dir /wheels . \
    && /opt/venv/bin/pip install --no-deps /wheels/*.whl \
    && /opt/venv/bin/pip check

FROM python:3.14.7-slim-trixie@sha256:ef30e8ee3a7f227b0b5b39669b2e656f35b56b918c6631820357c2a55ff5a428 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# root-ით არასდროს არ ვუშვებთ პროცესს
RUN useradd --create-home --uid 1000 voltbox
WORKDIR /srv/app

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY gunicorn.conf.py ./

USER voltbox
EXPOSE 8000

# liveness და არა /health: ბაზის გათიშვაზე კონტეინერის რესტარტი არაფერს შველის
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live').status==200 else 1)"

# gunicorn + uvicorn worker — გრეისფული რესტარტისა და worker-ების მართვისთვის.
# პარამეტრები gunicorn.conf.py-შია და არა აქ: exec-form CMD-ში ${VAR} არ
# ჩანაცვლდება (shell არ არის), ხოლო FORWARDED_ALLOW_IPS გარემოდან უნდა მოვიდეს.
CMD ["gunicorn", "-c", "gunicorn.conf.py"]
