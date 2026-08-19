FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system zorysa \
    && adduser --system --ingroup zorysa zorysa

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY --chown=zorysa:zorysa app ./app
COPY --chown=zorysa:zorysa migrations ./migrations
COPY --chown=zorysa:zorysa alembic.ini ./

USER zorysa

CMD ["python", "-m", "app.main"]
