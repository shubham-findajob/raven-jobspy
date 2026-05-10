from flask import Flask, jsonify, request
from jobspy import scrape_jobs
from concurrent.futures import ThreadPoolExecutor, as_completed
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
BLOCKED_COMPANIES = {
    # known spam / fake-listing mills
    'scoutit', 'argo intern', 'wake up whistle', 'toloka annotators',
    'yo it consulting', 'crossing hurdles', 'talentgigs', 'golden opportunities',

    # job boards & aggregators (repost others' jobs, no real contact)
    'jobgether', 'reycruit', 'mygwork', 'dataannotation', 'efinancialcareers',
    'digital lead international', 'quik hire staffing', 'nas nuvens', 'bm digital',
    'foundit', 'shine', 'timesjobs', 'apna', 'instahyre', 'iimjobs', 'hirist',

    # Indian staffing / body-shop agencies
    'uplers', 'teamlease', 'quess', 'manpowergroup', 'manpower group',
    'randstad', 'adecco', 'gi group', 'abc consultants', 'careernet',
    'xpheno', 'antal international', 'ikya', 'firstmeridian',

    # Global staffing / executive search (wrong channel for cold email)
    'michael page', 'hays', 'robert half', 'korn ferry', 'spencer stuart',
    'egon zehnder', 'russell reynolds', 'hudson', 'kelly services',

    # Anonymous / uncontactable listings
    'confidential',

    # Irrelevant industries
    'wpp media', 'frankfinn', 'alorica', 'muthoottu',
}

@app.route('/health')
def health():
    return 'ok'

def run_search(s, hours):
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
            return df[available].fillna('').to_dict('records'), None
        return [], None
    except Exception as e:
        print(f"Error: {s['keyword']} — {traceback.format_exc()}")
        return [], {'search': s['keyword'], 'error': str(e)}

@app.route('/jobs')
def jobs():
    hours = int(request.args.get('hours', 25))
    all_jobs = []
    errors = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(run_search, s, hours): s for s in SEARCHES}
        for future in as_completed(futures):
            records, error = future.result()
            if error:
                errors.append(error)
            else:
                all_jobs.extend(records)

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
        # Skip recruiting / TA roles (not what Shubham is applying for)
        title = str(j.get('title', ''))
        if any(w in title.lower() for w in ['talent acquisition', 'recruiter', 'recruitment', 'hr manager', 'human resources']):
            continue
        # Skip non-English / student jobs from Germany searches
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
