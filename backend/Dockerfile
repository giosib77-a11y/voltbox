# syntax=docker/dockerfile:1
# მრავალსაფეხურიანი build — საბოლოო იმიჯში კომპილატორი და dev-პაკეტები არ რჩება.
FROM python:3.14-slim AS builder

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

FROM python:3.14-slim AS runtime

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

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status==200 else 1)"

# gunicorn + uvicorn worker — გრეისფული რესტარტისა და worker-ების მართვისთვის.
# პარამეტრები gunicorn.conf.py-შია და არა აქ: exec-form CMD-ში ${VAR} არ
# ჩანაცვლდება (shell არ არის), ხოლო FORWARDED_ALLOW_IPS გარემოდან უნდა მოვიდეს.
CMD ["gunicorn", "-c", "gunicorn.conf.py"]
