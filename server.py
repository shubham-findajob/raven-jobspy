from flask import Flask, jsonify, request
from jobspy import scrape_jobs
import traceback

app = Flask(__name__)

SEARCHES = [
    {'keyword': 'chief of staff',     'location': 'India',   'remote': False},
    {'keyword': 'growth manager',      'location': 'India',   'remote': False},
    {'keyword': 'strategy associate',  'location': 'India',   'remote': False},
    {'keyword': 'business analyst',    'location': 'India',   'remote': False},
    {'keyword': 'AI analyst',          'location': 'India',   'remote': False},
    {'keyword': 'data analyst',        'location': 'India',   'remote': False},
    {'keyword': 'operations manager',  'location': 'India',   'remote': False},
    {'keyword': 'business analyst remote',     'location': 'Germany',     'remote': True},
    {'keyword': 'data analyst remote',         'location': 'Germany',     'remote': True},
    {'keyword': 'business analyst remote',     'location': 'France',      'remote': True},
    {'keyword': 'data analyst remote',         'location': 'Netherlands', 'remote': True},
    {'keyword': 'AI analyst remote',           'location': 'Europe',      'remote': True},
    {'keyword': 'growth manager remote',       'location': 'Europe',      'remote': True},
]

FIELDS = ['id', 'title', 'company', 'location', 'job_url', 'date_posted', 'description', 'job_type']

# Staffing agencies / job-board aggregators that post fake bulk listings
BLOCKED_COMPANIES = {'scoutit', 'argo intern', 'wake up whistle', 'toloka annotators', 'yo it consulting', 'crossing hurdles', 'talentgigs', 'golden opportunities'}

@app.route('/health')
def health():
    return 'ok'

@app.route('/jobs')
def jobs():
    hours = int(request.args.get('hours', 25))
    all_jobs = []
    errors = []

    for s in SEARCHES:
        try:
            df = scrape_jobs(
                site_name=['linkedin'],
                search_term=s['keyword'],
                location=s['location'],
                results_wanted=25,
                hours_old=hours,
                is_remote=s.get('remote', False),
                linkedin_fetch_description=False,
            )
            if df is not None and not df.empty:
                available = [f for f in FIELDS if f in df.columns]
                records = df[available].fillna('').to_dict('records')
                all_jobs.extend(records)
        except Exception as e:
            errors.append({'search': s['keyword'], 'error': str(e)})
            print(f"Error: {s['keyword']} — {traceback.format_exc()}")

    # Deduplicate by job_url
    seen, unique = set(), []
    for j in all_jobs:
        key = str(j.get('job_url') or j.get('id') or '')
        if not key or key in seen:
            continue
        # Skip blocked companies
        co = str(j.get('company', '')).lower()
        if any(b in co for b in BLOCKED_COMPANIES):
            continue
        # Skip non-English / student jobs from Germany searches
        title = str(j.get('title', ''))
        if any(w in title.lower() for w in ['werkstudent', 'praktikum', 'entwickler', 'annotator', 'annotieren', '(m/w/d)', 'befristet', 'spezialist', 'berater', 'ingenieur', 'sachbearbeiter']):
            continue
        if key not in seen:
            seen.add(key)
            # Convert non-serializable types
            for k, v in j.items():
                if hasattr(v, 'isoformat'):
                    j[k] = v.isoformat()
                elif v != v:  # NaN check
                    j[k] = ''
            unique.append(j)

    return jsonify({'jobs': unique, 'count': len(unique), 'errors': errors})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
