"""Personal library metadata and optional public Steam review summaries."""
import json
import time
from urllib.request import Request, urlopen

STATUSES = ('Unsorted', 'Want to play', 'Playing', 'Completed', 'On hold', 'Dropped')

def validate_profile(raw):
    if not isinstance(raw, dict): raise ValueError('Invalid game details')
    rating = raw.get('rating', 0)
    if type(rating) is not int or not 0 <= rating <= 5: raise ValueError('Rating must be between 0 and 5')
    status = raw.get('status', 'Unsorted')
    if status not in STATUSES: raise ValueError('Invalid play status')
    notes = raw.get('notes', '')
    collections = raw.get('collections', [])
    if not isinstance(notes, str) or len(notes) > 5000: raise ValueError('Notes may contain up to 5000 characters')
    if not isinstance(collections, list) or len(collections) > 12: raise ValueError('Use up to 12 collections')
    clean = []
    for name in collections:
        if not isinstance(name, str) or len(name) > 40: raise ValueError('Collection names may contain up to 40 characters')
        name = name.strip()
        if name and name.casefold() not in [c.casefold() for c in clean]: clean.append(name)
    return dict(rating=rating, status=status, notes=notes, collections=clean)

def fetch_reviews(appid):
    if not str(appid).isdigit(): raise ValueError('Invalid Steam app ID')
    url = f'https://store.steampowered.com/appreviews/{appid}?json=1&language=all&purchase_type=all&review_type=all&filter=all&day_range=365&cursor=*&num_per_page=1'
    request = Request(url, headers={'User-Agent': 'OrbitLauncher/2.0', 'Accept': 'application/json'})
    with urlopen(request, timeout=12) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000: raise ValueError('Steam response too large')
    payload = json.loads(raw)
    if payload.get('success') != 1: raise ValueError('Steam reviews are currently unavailable')
    info = payload['query_summary']
    positive, negative = int(info['total_positive']), int(info['total_negative'])
    total = positive + negative
    return dict(positive=positive, negative=negative, total=total,
                percent=round(positive / total * 100) if total else None,
                label=str(info.get('review_score_desc', 'No reviews'))[:100], fetched=int(time.time()))
