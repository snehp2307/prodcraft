# DEMO WITH PLANTED ISSUES — do not use
# planted: unpinned base image, runs as root, copies .env into the image, no healthcheck
FROM python:latest
WORKDIR /srv
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
