import urllib.request
import re
import json
import ssl
import logging
from decimal import Decimal
from bs4 import BeautifulSoup
from django.utils import timezone

logger = logging.getLogger(__name__)

def _clean_amount(val_str):
    """Clean monetary strings like 'Rs. 14,270(-15)' into integer 14270."""
    if not val_str:
        return 0
    cleaned = re.sub(r'\(.*?\)', '', str(val_str))
    cleaned = re.sub(r'[^0-9.]', '', cleaned)
    try:
        return int(round(float(cleaned)))
    except Exception:
        return 0

def fetch_live_gold_rate():
    """
    Fetches the latest live market gold prices in INR per gram.
    Prioritizes GoodReturns Chennai (Tamil Nadu local bullion market benchmark),
    with graceful fallback to global currency spot and COMEX futures.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    now = timezone.now()
    now_local = timezone.localtime(now) if timezone.is_aware(now) else now
    fetched_date_str = now_local.strftime('%d %b %Y')
    fetched_time_str = now_local.strftime('%I:%M:%S %p')

    # -------------------------------------------------------------------------
    # Provider 1: GoodReturns Chennai (Tamil Nadu Live Retail Market Rates)
    # -------------------------------------------------------------------------
    try:
        url = 'https://www.goodreturns.in/gold-rates/chennai.html'
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=7) as res:
            html = res.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, 'html.parser')
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if not rows:
                continue
            headers_row = [th.get_text(strip=True).upper() for th in rows[0].find_all(['th', 'td'])]
            if 'GRAM' in headers_row and ('22K' in headers_row or '24K' in headers_row):
                idx_gram = headers_row.index('GRAM') if 'GRAM' in headers_row else -1
                idx_24k = headers_row.index('24K') if '24K' in headers_row else -1
                idx_22k = headers_row.index('22K') if '22K' in headers_row else -1
                idx_18k = headers_row.index('18K') if '18K' in headers_row else -1

                rate_24k_1g = None
                rate_22k_1g = None
                rate_18k_1g = None
                sovereign_22k_8g = None

                for tr in rows[1:]:
                    cols = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if not cols:
                        continue
                    gram_text = cols[idx_gram].strip() if idx_gram != -1 and idx_gram < len(cols) else ''

                    if gram_text == '1':
                        if idx_24k != -1 and idx_24k < len(cols):
                            rate_24k_1g = _clean_amount(cols[idx_24k])
                        if idx_22k != -1 and idx_22k < len(cols):
                            rate_22k_1g = _clean_amount(cols[idx_22k])
                        if idx_18k != -1 and idx_18k < len(cols):
                            rate_18k_1g = _clean_amount(cols[idx_18k])
                    elif gram_text == '8':
                        if idx_22k != -1 and idx_22k < len(cols):
                            sovereign_22k_8g = _clean_amount(cols[idx_22k])

                if rate_22k_1g and rate_22k_1g > 1000:
                    rate_24k = rate_24k_1g or int(round(rate_22k_1g * 24.0 / 22.0))
                    rate_20k = int(round(rate_24k * 20.0 / 24.0))
                    rate_18k = rate_18k_1g or int(round(rate_24k * 18.0 / 24.0))
                    sovereign_8g = sovereign_22k_8g or (rate_22k_1g * 8)

                    return {
                        'success': True,
                        'source': 'GoodReturns Chennai (Tamil Nadu Retail Market)',
                        'rate_24k_per_gram': rate_24k,
                        'rate_22k_per_gram': rate_22k_1g,
                        'rate_20k_per_gram': rate_20k,
                        'rate_18k_per_gram': rate_18k,
                        'sovereign_8g': sovereign_8g,
                        'pavpon_8g': sovereign_8g,
                        'fetched_at_date': fetched_date_str,
                        'fetched_at_time': fetched_time_str,
                        'fetched_at_datetime': f"{fetched_date_str} at {fetched_time_str}",
                        'fetched_at_iso': now.isoformat(),
                    }
    except Exception as e:
        logger.warning(f"GoodReturns Chennai gold rate provider failed: {e}")

    # -------------------------------------------------------------------------
    # Provider 2: Fawazahmed0 Currency API / XAU Spot to INR
    # -------------------------------------------------------------------------
    try:
        req = urllib.request.Request(
            'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/xau.json',
            headers=headers
        )
        with urllib.request.urlopen(req, context=ctx, timeout=6) as res:
            data = json.loads(res.read().decode('utf-8'))
            inr_per_oz = data.get('xau', {}).get('inr')
            if inr_per_oz and float(inr_per_oz) > 0:
                rate_24k_raw = (float(inr_per_oz) / 31.1034768) * 1.06
                rate_24k = int(round(rate_24k_raw / 10.0) * 10)
                rate_22k = int(round((rate_24k * 22.0 / 24.0) / 10.0) * 10)
                rate_20k = int(round((rate_24k * 20.0 / 24.0) / 10.0) * 10)
                rate_18k = int(round((rate_24k * 18.0 / 24.0) / 10.0) * 10)

                return {
                    'success': True,
                    'source': 'Global Bullion Spot (XAU/INR Domestic Basis)',
                    'rate_24k_per_gram': rate_24k,
                    'rate_22k_per_gram': rate_22k,
                    'rate_20k_per_gram': rate_20k,
                    'rate_18k_per_gram': rate_18k,
                    'sovereign_8g': rate_22k * 8,
                    'pavpon_8g': rate_22k * 8,
                    'fetched_at_date': fetched_date_str,
                    'fetched_at_time': fetched_time_str,
                    'fetched_at_datetime': f"{fetched_date_str} at {fetched_time_str}",
                    'fetched_at_iso': now.isoformat(),
                }
    except Exception as e:
        logger.warning(f"Secondary gold price provider failed: {e}")

    # -------------------------------------------------------------------------
    # Provider 3: Yahoo Finance COMEX Gold Futures (GC=F) & USD/INR (USDINR=X)
    # -------------------------------------------------------------------------
    try:
        req_gold = urllib.request.Request(
            'https://query1.finance.yahoo.com/v8/finance/chart/GC=F',
            headers=headers
        )
        with urllib.request.urlopen(req_gold, context=ctx, timeout=6) as res:
            g_data = json.loads(res.read().decode('utf-8'))
            gold_usd_oz = float(g_data['chart']['result'][0]['meta']['regularMarketPrice'])

        req_inr = urllib.request.Request(
            'https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X',
            headers=headers
        )
        with urllib.request.urlopen(req_inr, context=ctx, timeout=6) as res:
            i_data = json.loads(res.read().decode('utf-8'))
            usd_inr = float(i_data['chart']['result'][0]['meta']['regularMarketPrice'])

        if gold_usd_oz > 0 and usd_inr > 0:
            intl_24k = ((gold_usd_oz * usd_inr) / 31.1034768) * 1.065
            rate_24k = int(round(intl_24k / 10.0) * 10)
            rate_22k = int(round((rate_24k * 22.0 / 24.0) / 10.0) * 10)
            rate_20k = int(round((rate_24k * 20.0 / 24.0) / 10.0) * 10)
            rate_18k = int(round((rate_24k * 18.0 / 24.0) / 10.0) * 10)

            return {
                'success': True,
                'source': 'COMEX Gold Futures & FX (Yahoo Finance)',
                'rate_24k_per_gram': rate_24k,
                'rate_22k_per_gram': rate_22k,
                'rate_20k_per_gram': rate_20k,
                'rate_18k_per_gram': rate_18k,
                'sovereign_8g': rate_22k * 8,
                'pavpon_8g': rate_22k * 8,
                'fetched_at_date': fetched_date_str,
                'fetched_at_time': fetched_time_str,
                'fetched_at_datetime': f"{fetched_date_str} at {fetched_time_str}",
                'fetched_at_iso': now.isoformat(),
            }
    except Exception as e:
        logger.warning(f"Tertiary gold price provider failed: {e}")

    return {
        'success': False,
        'error': 'Unable to connect to live gold price feeds at this moment. Please enter rates manually or try again in a few seconds.',
        'fetched_at_date': fetched_date_str,
        'fetched_at_time': fetched_time_str,
    }
