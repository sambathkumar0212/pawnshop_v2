import urllib.request
import json
import ssl
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

def fetch_live_gold_rate():
    """
    Fetches the latest live market gold prices in INR per gram using reliable market feeds.
    Falls back gracefully between multiple data providers:
    1. Global Bullion Currency Feed (XAU/INR spot + domestic benchmark basis)
    2. COMEX Gold Futures (GC=F) & USD/INR FX (Yahoo Finance)
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
    }

    # Provider 1: Fawazahmed0 Currency API / XAU Spot to INR
    try:
        req = urllib.request.Request(
            'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/xau.json',
            headers=headers
        )
        with urllib.request.urlopen(req, context=ctx, timeout=6) as res:
            data = json.loads(res.read().decode('utf-8'))
            inr_per_oz = data.get('xau', {}).get('inr')
            if inr_per_oz and float(inr_per_oz) > 0:
                # 1 Troy Oz = 31.1034768 grams. Domestic Indian retail standard import duty basis (~6%)
                rate_24k_raw = (float(inr_per_oz) / 31.1034768) * 1.06
                rate_24k = int(round(rate_24k_raw / 10.0) * 10)
                rate_22k = int(round((rate_24k * 22.0 / 24.0) / 10.0) * 10)
                rate_20k = int(round((rate_24k * 20.0 / 24.0) / 10.0) * 10)
                rate_18k = int(round((rate_24k * 18.0 / 24.0) / 10.0) * 10)
                
                return {
                    'success': True,
                    'source': 'Global Bullion Market Spot (XAU/INR Domestic Basis)',
                    'rate_24k_per_gram': rate_24k,
                    'rate_22k_per_gram': rate_22k,
                    'rate_20k_per_gram': rate_20k,
                    'rate_18k_per_gram': rate_18k,
                    'sovereign_8g': rate_22k * 8,
                }
    except Exception as e:
        logger.warning(f"Primary gold price provider failed: {e}")

    # Provider 2: Yahoo Finance COMEX Gold Futures (GC=F) & USD/INR (USDINR=X)
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
            }
    except Exception as e:
        logger.warning(f"Secondary gold price provider failed: {e}")

    return {
        'success': False,
        'error': 'Unable to connect to live gold price APIs at this moment. Please enter rates manually or try again in a few seconds.',
    }
