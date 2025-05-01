# app.py
from flask import Flask, render_template, request, jsonify, redirect, session, url_for, flash
import requests
import os
from dotenv import load_dotenv
import random
import base64
from threading import Thread
import log_parser
import logging
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

API_KEYS = {
    'NASA': os.getenv('NASA_API_KEY'),
    'NEWS': os.getenv('NEWS_API_KEY'),
    'TREFLE': os.getenv('TREFLE_API_KEY'),
    'SPOTIFY': os.getenv('SPOTIFY_CLIENT_ID'),
    'SPOTIFY_CLIENT_SECRET': os.getenv('SPOTIFY_CLIENT_SECRET'),
    'OMDB': os.getenv('OMDB_API_KEY'),
    'UNSPLASH': os.getenv('UNSPLASH_ACCESS_KEY')
}

CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = os.getenv('SPOTIFY_SCOPE')

def get_wiki_image(scientific_name):
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "original",
            "titles": scientific_name
        }
        response = requests.get(search_url, params=params)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            image_url = page.get("original", {}).get("source")
            if image_url:
                return image_url
    except Exception as e:
        print("[WIKI ERROR]", e)
    return None  # fallback if no image

def get_plant_image(plant_name):
    access_key = API_KEYS['UNSPLASH']
    url = f"https://api.unsplash.com/search/photos?query={plant_name}&client_id={access_key}"
    response = requests.get(url)
    data = response.json()
    
    if response.status_code == 200 and 'results' in data and data['results']:
        photo = data["results"][0]
        trigger_unsplash_download(photo['id'])  # log the download
        return photo["urls"]["regular"]
    else:
        print(f"Error fetching image for {plant_name}: {response.status_code}")
        return "/static/no_image.jpg"

def trigger_unsplash_download(photo_id):
    url = f"https://api.unsplash.com/photos/{photo_id}/download"
    headers = {"Authorization": f"Client-ID {API_KEYS['UNSPLASH']}"}
    requests.get(url, headers=headers)

@app.after_request
def log_request(response):
    """Log all requests in Apache Combined Log Format"""
    timestamp = datetime.now().strftime('%d/%b/%Y:%H:%M:%S')
    log_line = f'{request.remote_addr} - - [{timestamp}] "{request.method} {request.path} HTTP/1.1" {response.status_code} {response.content_length} "{request.referrer}" "{request.user_agent}"\n'
    
    # Write to access.log
    with open('access.log', 'a') as f:
        f.write(log_line)
    
    return response

@app.route('/')
def home():
    return render_template('index.html')

# Country Data API
@app.route('/countries', methods=['GET', 'POST'])
def countries():
    if request.method == 'POST':
        country_input = request.form.get('country_input')
        country_select = request.form.get('country_select')

        # Prefer input field if both are filled
        country_name = country_input or country_select

        if country_name:
            response = requests.get(f'https://restcountries.com/v3.1/name/{country_name}')
            data = response.json()[0] if response.ok and response.json() else None
            return render_template('countries.html', data=data)
        else:
            return render_template('countries.html', data=None)

    return render_template('countries.html')

@app.template_filter('number_format')
def number_format(value):
    return f"{value:,}"

# Plants API
@app.route('/plants', methods=['GET', 'POST'])
def search_plants():
    plants = []
    search_term = ""
    retry_after = 0
    error_msg = None

    if request.method == 'POST':
        search_term = request.form.get('search', '').strip()
        if search_term:
            search_url = "https://en.wikipedia.org/w/api.php"
            search_params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': search_term
            }

            try:
                response = requests.get(search_url, params=search_params)
                response.raise_for_status()
                search_results = response.json().get('query', {}).get('search', [])

                for result in search_results:
                    title = result['title']
                    page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    wiki_image = get_wiki_image(title)
                    image_url = wiki_image if wiki_image else get_plant_image(title)

                    plants.append({
                        'title': title,
                        'page_url': page_url,
                        'image_url': image_url
                    })

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    error_msg = "Too many requests. Please wait before retrying."
                    retry_after = 20  # seconds
                else:
                    error_msg = "Error fetching plant data."
                print("Error fetching plant data:", e)

    return render_template('plants.html', plants=plants, search_term=search_term,
                           retry_after=retry_after, error_msg=error_msg)

# NASA APOD
@app.route('/nasa')
def nasa():
    response = requests.get(
        f'https://api.nasa.gov/planetary/apod?api_key={API_KEYS["NASA"]}'
    )
    apod = response.json() if response.ok else None
    return render_template('nasa.html', apod=apod)

# News API
@app.route('/news')
def news():
    country = request.args.get('country', 'us')  # Default to 'us' if no country provided
    try:
        response = requests.get(
            f'https://newsapi.org/v2/top-headlines?apiKey={API_KEYS["NEWS"]}&country={country}'
        )
        response.raise_for_status()
        data = response.json()
        articles = data.get('articles', [])
        for article in articles:
            if 'description' not in article or article['description'] is None:
                article['description'] = ''
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        articles = []
    return render_template('news.html', articles=articles, selected_country=country)

# Sunrise/Sunset
@app.route('/sun-times')
def sun_times():
    lat = request.args.get('lat', '40.7128')
    lng = request.args.get('lng', '-74.0060')
    response = requests.get(f'https://api.sunrise-sunset.org/json?lat={lat}&lng={lng}')
    results = response.json().get('results', {}) if response.ok else {}
    return render_template('sun_times.html', results=results)

# Pokémon API
@app.route('/pokemon/<name>')
def pokemon(name):
    response = requests.get(f'https://pokeapi.co/api/v2/pokemon/{name}')
    data = response.json() if response.ok else None
    return render_template('pokemon.html', pokemon=data)

# Movies API
@app.route('/movies')
def movies():
    title = request.args.get('title', 'The Matrix')
    response = requests.get(f'http://www.omdbapi.com/?apikey={API_KEYS["OMDB"]}&t={title}')
    movie = response.json() if response.ok else None
    return render_template('movies.html', movie=movie)

# Cat Facts
@app.route('/cat-facts')
def cat_facts():
    response = requests.get('https://catfact.ninja/facts?limit=5')
    facts = response.json().get('data', []) if response.ok else []
    return render_template('cat_facts.html', facts=facts)

# Dog API

@app.route('/dogs')
def dogs():
    # Step 1: Get all breed data
    breed_response = requests.get('https://api.thedogapi.com/v1/breeds')
    all_breeds = breed_response.json() if breed_response.ok else []

    # Step 2: Randomly pick 5 breeds
    selected_breeds = random.sample(all_breeds, 5)

    dog_data = []

    # Step 3: Fetch image for each selected breed
    for breed in selected_breeds:
        breed_id = breed['id']
        image_response = requests.get(f'https://api.thedogapi.com/v1/images/search?breed_id={breed_id}')
        image_data = image_response.json()

        if image_data and 'url' in image_data[0]:
            dog_data.append({
                'image_url': image_data[0]['url'],
                'breed_info': breed
            })

    return render_template('dogs.html', dogs=dog_data)


@app.route("/login")
def login():
    auth_url = f"{SPOTIFY_AUTH_URL}?response_type=code&client_id={CLIENT_ID}&scope={SCOPE}&redirect_uri={REDIRECT_URI}&show_dialog=true"
    return redirect(auth_url)

@app.route("/music")
def callback():
    code = request.args.get("code")
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    res = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    res_data = res.json()

    session['access_token'] = res_data.get("access_token")
    return redirect("/top-tracks")

@app.route("/top-tracks")
def top_tracks():
    token = session.get('access_token')
    if not token:
        return redirect('/login')

    res = requests.get(
        "https://api.spotify.com/v1/me/top/tracks?limit=5",
        headers={"Authorization": f"Bearer {token}"}
    )

    tracks = res.json().get("items", [])
    return render_template("music.html", tracks=[
    {
        "name": track["name"],
        "artist": track["artists"][0]["name"],
        "image": track["album"]["images"][0]["url"] if track["album"]["images"] else "",
        "preview_url": track.get("preview_url")
    }
    for track in tracks 
])


@app.route('/send-logs', methods=['POST'])
def send_logs():
    logs = log_parser.get_and_clear_logs()
    if not logs:
        flash('No logs available to send.', 'info')
    else:
        success = log_parser.send_email(logs)
        if success:
            flash('Logs sent successfully!', 'success')
        else:
            flash('Failed to send logs. Please try again.', 'danger')
    return redirect(url_for('home'))

# app.py (replace the existing logging config)
if __name__ == '__main__':
    # Remove existing logging config
    werkzeug_log = logging.getLogger('werkzeug')
    werkzeug_log.disabled = True  # Disable Werkzeug's default logs

    # Start monitor thread safely
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        monitor_thread = Thread(target=log_parser.monitor_logs)
        monitor_thread.daemon = True
        monitor_thread.start()

    app.run(debug=True, port=8000, use_reloader=True)