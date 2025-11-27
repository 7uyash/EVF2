"""
Internet Check Module
Provides integrations for checking email presence across the internet
Supports Google Custom Search (if API key + CSE id provided) and Have I Been Pwned (optional API key)

Robustness: performs retries/backoff and user-agent rotation for Google scraping; the code will
use Google's Custom Search API when credentials are provided, and will return structured
errors (status_code, error) when scraping fails (e.g., 403/429).
"""
import os
import requests
import random
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse, parse_qs
from bs4 import BeautifulSoup

# Common UA strings used when scraping; rotate to reduce risk of bot blocks
DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0',
]


def _get_env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ('1', 'true', 'yes', 'on')


def search_google(email: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Try to find the email via Google search.

    If GOOGLE_API_KEY and GOOGLE_CSE_ID are set, we use Google's Custom Search API.
    Otherwise, we fall back to a lightweight HTML scrape of search results (best-effort).
    """
    results: List[Dict[str, str]] = []
    api_key = os.getenv('GOOGLE_API_KEY')
    cse_id = os.getenv('GOOGLE_CSE_ID')

    # Use a resilient requests session with retries
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504, 403],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Use UA rotation to try to minimize 403s when scraping
    # Use module-level UA list so other functions can reuse it when needed
    ua_list = DEFAULT_USER_AGENTS

    def _do_get(url, **kwargs):
        # rotate UA headers
        headers = kwargs.pop('headers', {})
        headers['User-Agent'] = random.choice(ua_list)
        try:
            return session.get(url, headers=headers, timeout=7, **kwargs)
        except Exception:
            # If session.get failed, fallback to requests.get
            return requests.get(url, headers=headers, timeout=7, **kwargs)

    # If we have API keys, use Google Custom Search API
    if api_key and cse_id:
        url = 'https://www.googleapis.com/customsearch/v1'
        params = {
            'key': api_key,
            'cx': cse_id,
            'q': email,
            'num': max_results,
        }
        try:
            resp = _do_get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('items', [])[:max_results]
                for it in items:
                    results.append({ 'title': it.get('title', ''), 'url': it.get('link', '') })
            else:
                logging.warning('Google CSE returned non-200 status: %s', resp.status_code)
                return { 'count': 0, 'results': [], 'error': f'Google CSE error {resp.status_code}', 'status_code': resp.status_code }
        except Exception:
            pass
    else:
        # Lightweight HTML scrape (user-agent: pretend to be a browser)
        try:
            params = {'q': email, 'num': max_results}
            resp = _do_get('https://www.google.com/search', params=params)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Google results are in <a href="/url?q=TARGET..."> anchors
                anchors = soup.find_all('a')
                seen_urls = set()
                for a in anchors:
                    href = a.get('href', '')
                    if href.startswith('/url?'):
                        parsed = parse_qs(urlparse(href).query)
                        q = parsed.get('q')
                        if q:
                            url_val = q[0]
                            if url_val not in seen_urls:
                                seen_urls.add(url_val)
                                title = a.get_text().strip() or ''
                                results.append({ 'title': title, 'url': url_val })
                        if len(results) >= max_results:
                            break
            elif resp.status_code == 403:
                logging.warning('Google search returned 403; likely blocked')
                return { 'count': 0, 'results': [], 'error': 'google_403', 'status_code': 403 }
            else:
                logging.warning('Google search returned non-200 status: %s', resp.status_code)
                return { 'count': 0, 'results': [], 'error': f'google_status_{resp.status_code}', 'status_code': resp.status_code }
        except Exception as e:
            logging.exception('Google search scrape error')
            return { 'count': 0, 'results': [], 'error': str(e) }

    return { 'count': len(results), 'results': results }


def check_hibp(email: str) -> Dict[str, Any]:
    """
    Check Have I Been Pwned for breaches for the given email using the HIBP API
    Requires HIBP_API_KEY env var to be set; otherwise returns skipped.
    """
    api_key = os.getenv('HIBP_API_KEY')
    if not api_key:
        # Mark as skipped but still return a structured response so callers treat this as an explicit skip
        return { 'skipped': True, 'reason': 'HIBP_API_KEY not set' }

    url = f'https://haveibeenpwned.com/api/v3/breachedaccount/{email}'
    # Use same session with retries for HIBP and sensible UA
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {
        'hibp-api-key': api_key,
        'User-Agent': random.choice(DEFAULT_USER_AGENTS)
    }
    try:
        resp = session.get(url, headers=headers, timeout=7)
        if resp.status_code == 200:
            # Returns list of breaches
            return { 'skipped': False, 'breaches': resp.json(), 'count': len(resp.json()) }
        elif resp.status_code == 404:
            return { 'skipped': False, 'breaches': [], 'count': 0 }
        else:
            return { 'skipped': False, 'error': f'HIBP API error {resp.status_code}', 'status_code': resp.status_code }
    except Exception as e:
        logging.exception('HIBP API error')
        return { 'skipped': False, 'error': str(e) }


def check_internet_presence(email: str, *, enable_hibp: Optional[bool] = None, max_google_results: int = 5) -> Dict[str, Any]:
    """
    Wrapper to perform multiple internet checks and return a combined result dictionary.
    """
    # Force google search and hibp checks to be run by default (unless explicitly disabled via env)
    if enable_hibp is None:
        enable_hibp = _get_env_bool('ENABLE_HIBP', True)

    # Google search (always run unless explicitly disabled)
    google = search_google(email, max_results=max_google_results)

    # HIBP check is attempted if enabled; if no key present, we return skipped but do not suppress
    hibp = check_hibp(email) if enable_hibp else { 'skipped': True }
    return { 'google': google, 'hibp': hibp }
