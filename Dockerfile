FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     DEBIAN_FRONTEND=noninteractive     CHROME_BIN=/usr/bin/chromium     CHROMIUM_PATH=/usr/bin/chromium     PLAYWRIGHT_BROWSERS_PATH=0     PORT=8000

WORKDIR /app

# Install system libraries, Chromium browser, and Tamil fonts for 100% pixel-perfect PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     curl     chromium     chromium-driver     fonts-noto-core     fonts-noto-ui-core     fonts-noto-extra     fonts-lohit-taml     libnss3     libnspr4     libatk1.0-0     libatk-bridge2.0-0     libcups2     libdrm2     libxkbcommon0     libxcomposite1     libxdamage1     libxfixes3     libxrandr2     libgbm1     libpango-1.0-0     libcairo2     libasound2     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN chmod +x /app/start.sh /app/build.sh
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["./start.sh"]
