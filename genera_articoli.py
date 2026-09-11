import os
import re
import datetime
import random
import socket
import json
import requests
import feedparser
from google import genai

# Timeout globale di sicurezza sulle connessioni di rete
socket.setdefaulttimeout(15)

# Caricamento delle credenziali dal file separato config.json
CONFIG_FILE = "config.json"
config = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or config.get("telegram_bot_token", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or config.get("telegram_chat_id", "")

RSS_SOURCES = [
    "https://www.kodami.it/feed/",
    "https://www.dogster.com/feed",
    "https://www.catster.com/feed",
    "https://iheartdogs.com/feed",
    "https://iheartcats.com/feed",
    "https://dogtime.com/feed",
    "https://cattime.com/feed",
    "https://www.lovemeow.com/feed",
    "https://katzenworld.co.uk/feed",
    "https://www.dogingtonpost.com/feed",
    "https://moderndogmagazine.com/rss.xml",
    "https://moderncat.com/rss.xml",
    "https://goodnewsforpets.com/feed",
    "https://www.petmd.com/rss",
    "https://www.thesprucepets.com/rss",
    "https://thebark.com/feed",
    "https://www.petsradar.com/rss.xml",
    "https://www.akc.org/feed",
    "https://animalwellnessmagazine.com/feed",
    "https://www.whole-dog-journal.com/feed",
    "https://www.rover.com/blog/feed/",
    "https://worldanimalnews.com/feed",
    "https://blogpaws.com/feed",
    "https://cattitude-daily.com/feed",
    "https://www.lifewithdogs.tv/feed",
    "https://www.petgazette.biz/feed/",
    "https://www.vetstreet.com/feed/",
    "https://bestfriends.org/news/rss.xml",
    "https://catbehaviorassociates.com/feed",
    "https://apnews.com/hub/pets",
    "https://www.amorepet.it/feed/",
    "https://www.mondopets.it/feed/",
    "https://www.GreenMe.it/tag/animali/feed/"
]

EXCLUDED_ANIMALS = [
    'uccello', 'uccelli', 'pappagallo', 'rettili', 'serpente', 'tartaruga', 
    'cavallo', 'cavalli', 'pesci', 'acquario', 'criceto', 'coniglio', 
    'ferretto', 'bird', 'birds', 'reptile', 'snake', 'turtle', 'horse', 
    'fish', 'rabbit', 'hamster', 'ferret'
]

PROMO_KEYWORDS = [
    'sponsored', 'sponsorizzato', 'promozionale', 'sconto', 'codice sconto', 
    'compra ora', 'in collaborazione con', 'recensione prodotto', 'offertissima', 
    'amazon prime day', 'black friday', 'pubblicità', 'ad'
]

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def get_existing_images():
    used = set()
    if os.path.exists("index.html"):
        try:
            with open("index.html", "r", encoding="utf-8") as f:
                content = f.read()
                srcs = re.findall(r'<img[^>]+src="([^">]+)"', content)
                for s in srcs:
                    used.add(s)
        except Exception:
            pass
    return used

def get_rss_image(entry):
    if 'enclosures' in entry and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href')
    if 'media_content' in entry and entry.media_content:
        for media in entry.media_content:
            if media.get('medium') == 'image' or media.get('type', '').startswith('image/'):
                return media.get('url')
    if 'media_thumbnail' in entry and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url')
    return None

def get_local_pet_image(is_cat_article=False, used_images=None):
    if used_images is None:
        used_images = set()
    cat_folder = "immagini_gatti"
    dog_folder = "immagini_cani"
    target_folder = cat_folder if is_cat_article else dog_folder
    fallback_folder = dog_folder if is_cat_article else cat_folder
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.avif')
    
    def scan_folder(folder):
        images = []
        if os.path.exists(folder) and os.path.isdir(folder):
            for fname in os.listdir(folder):
                if fname.lower().endswith(valid_extensions):
                    images.append(f"{folder}/{fname}")
        return images

    available_images = scan_folder(target_folder)
    normalized_used = {img.replace("../", "") for img in used_images}
    unused_images = [img for img in available_images if img not in normalized_used]
    
    if unused_images:
        return random.choice(unused_images)
    fallback_available = scan_folder(fallback_folder)
    unused_fallback = [img for img in fallback_available if img not in normalized_used]
    if unused_fallback:
        return random.choice(unused_fallback)
    all_images = available_images + fallback_available
    if all_images:
        return random.choice(all_images)
    return f"{cat_folder}/default.jpg" if is_cat_article else f"{dog_folder}/default.jpg"

def send_telegram_message(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    response = requests.post(url, json=payload)
    res_data = response.json()
    if not res_data.get("ok"):
        print(f"ERRORE TELEGRAM: {res_data}")
    return res_data

def clean_html_for_telegram(html_str):
    text = re.sub(r'<h2>(.*?)</h2>', r'\n\n<b>\1</b>\n', html_str, flags=re.DOTALL)
    text = re.sub(r'<p>(.*?)</p>', r'\1\n\n', html_str, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def send_telegram_draft(image_path, title, desc, content):
    github_edit_url = "https://github.com/zampamaniaofficial-svg/zampamania/edit/main/bozza_corrente.json"
    keyboard = {
        "inline_keyboard": [
            [{"text": "✅ Approva e Pubblica", "callback_data": "approve"}],
            [{"text": "✏️ Modifica su GitHub", "url": github_edit_url}],
            [{"text": "❌ Scarta", "callback_data": "discard"}]
        ]
    }

    caption_photo = f"<b>📸 Immagine selezionata:</b> <code>{image_path}</code>\n<b>Titolo:</b> {title}"
    url_photo = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption_photo, "parse_mode": "HTML"}
            requests.post(url_photo, data=payload, files={"photo": img_file})
    else:
        send_telegram_message(caption_photo)

    clean_text = clean_html_for_telegram(content)
    full_message = (
        f"<b>📝 Nuova Bozza Generata!</b>\n\n"
        f"<b>Titolo:</b> {title}\n\n"
        f"<b>Descrizione SEO:</b>\n<i>{desc}</i>\n\n"
        f"<b>📄 Contenuto Articolo:</b>\n{clean_text}"
    )
    
    if len(full_message) > 4000:
        full_message = full_message[:3950] + "\n\n<i>...(Testo troncato per limiti di lunghezza Telegram)</i>"

    send_telegram_message(full_message, reply_markup=keyboard)

def archive_old_articles(index_content):
    cards = re.findall(r'<article class="news-card".*?</article>', index_content, re.DOTALL)
    today = datetime.date.today()

    for card in cards:
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', card)
        if not date_match:
            continue
        
        card_date_str = date_match.group(1)
        try:
            card_date = datetime.datetime.strptime(card_date_str, "%d/%m/%Y").date()
        except ValueError:
            continue

        if (today - card_date).days > 7:
            cleaned_card = card
            cleaned_card = re.sub(r'<span[^>]*>News</span>', '', cleaned_card)
            cleaned_card = re.sub(r'<span[^>]*><i class="fa-regular fa-calendar"></i>.*?</span>', '', cleaned_card)

            card_text = re.sub(r'<[^>]+>', '', cleaned_card).lower()
            if any(k in card_text for k in ['salute', 'benessere', 'veterinario', 'dieta', 'malattia', 'cura', 'alimentazione', 'sintomi']):
                target_sec = 'salute'
            elif any(k in card_text for k in ['gatto', 'gatti', 'cat', 'cats', 'micio']):
                target_sec = 'gatti'
            elif any(k in card_text for k in ['cane', 'cani', 'dog', 'dogs', 'cucciolo']):
                target_sec = 'cani'
            else:
                target_sec = 'curiosita'

            index_content = index_content.replace(card, '')

            sec_patterns = [
                f'<div class="feed-{target_sec}">',
                f'<div id="{target_sec}">',
                f'<div class="section-{target_sec}">'
            ]
            inserted = False
            for pat in sec_patterns:
                if pat in index_content:
                    index_content = index_content.replace(pat, f'{pat}\n{cleaned_card}')
                    inserted = True
                    break
            
            if not inserted:
                index_content += f'\n<!-- Section {target_sec} -->\n{cleaned_card}'

    return index_content

def publish_article(draft_data):
    slug = draft_data["slug"]
    new_title = draft_data["title"]
    new_desc = draft_data["description"]
    html_content = draft_data["content"]
    image_url = draft_data["image_url"]
    is_indicative = draft_data.get("is_indicative", False)
    original_link = draft_data["original_link"]
    current_date = datetime.date.today().strftime("%d/%m/%Y")
    
    filename = f"articoli/{slug}.html"
    
    banner_html = f'<div style="background:#0284c7; color:#fff; padding:25px; border-radius:10px; text-align:center; margin:35px 0; box-shadow:0 4px 6px rgba(0,0,0,0.1);"><h3 style="margin:0 0 10px 0; font-size:22px;">Non perderti le migliori offerte pet!</h3><p style="margin:0 0 15px 0; font-size:15px;">Unisciti al canale Telegram di zampamania.com per sconti e promozioni lampo dedicate a cani e gatti.</p><a href="https://t.me/TUOCANALE" target="_blank" style="background:#fff; color:#0284c7; padding:12px 25px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block;">Unisciti al Canale Offerte</a></div>'
    source_html = f'<div style="text-align:center; margin-top:20px;"><a href="{original_link}" target="_blank" style="color:#94a3b8; font-size:12px; text-decoration:underline;">Fonte originale della notizia</a></div>'
    
    full_html_body = html_content + banner_html + source_html
    article_image_url = image_url if image_url.startswith("http") else f"../{image_url}"
    
    indicative_caption = '<p style="text-align: center; font-size: 11px; color: #64748b; margin-top: 4px; font-style: italic;">* Immagine a scopo puramente illustrativo</p>' if is_indicative else ''
    featured_image_html = f'<div style="text-align: center; margin-bottom: 25px; aspect-ratio: 16/9; max-height: 450px; overflow: hidden; border-radius: 8px;"><img src="{article_image_url}" alt="{new_title}" style="width: 100%; height: 100%; object-fit: cover;"></div>{indicative_caption}'
    full_html_body = featured_image_html + full_html_body

    if os.path.exists("articoli/template.html"):
        with open("articoli/template.html", "r", encoding="utf-8") as f:
            template = f.read()
        article_html = template.replace("{{title}}", new_title).replace("{{description}}", new_desc).replace("{{date}}", current_date).replace("{{content}}", full_html_body)
    else:
        article_html = f"<html><head><title>{new_title}</title></head><body><h1>{new_title}</h1>{full_html_body}</body></html>"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(article_html)

    with open("index.html", "r", encoding="utf-8") as f:
        index_content = f.read()

    new_news_card = f"""
            <article class="news-card" style="background:#fff; padding:20px; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:20px;">
                <div style="margin-bottom: 12px; aspect-ratio: 16/9; overflow: hidden; border-radius: 6px;"><img src="{image_url}" alt="{new_title}" style="width: 100%; height: 100%; object-fit: cover;"></div>
                <span style="font-size: 12px; background:#e0f2fe; color:#0369a1; padding:4px 8px; border-radius:4px; font-weight:600;">News</span>
                <h3 style="margin: 10px 0;"><a href="articoli/{slug}.html" style="text-decoration:none; color:#0f172a;">{new_title}</a></h3>
                <p style="color:#475569; font-size:14px;">{new_desc}</p>
                <span style="font-size: 12px; color: #94a3b8; display:inline-block; margin-top:10px;"><i class="fa-regular fa-calendar"></i> {current_date}</span>
            </article>
    """

    if '<div class="news-feed">' in index_content:
        index_content = index_content.replace('<div class="news-feed">', f'<div class="news-feed">\n{new_news_card}')

    index_content = archive_old_articles(index_content)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_content)

    print("Articolo pubblicato e riorganizzazione sezioni completata!")

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    dispatch_payload = os.environ.get("DISPATCH_PAYLOAD")

    if dispatch_payload == "approve":
        print("Ricevuto segnale di approvazione da Telegram...")
        if os.path.exists("bozza_corrente.json"):
            with open("bozza_corrente.json", "r", encoding="utf-8") as f:
                draft_data = json.load(f)
            publish_article(draft_data)

            send_telegram_message("🎉 <b>Articolo pubblicato con successo sul sito!</b>")
            
            if os.path.exists("bozza_corrente.json"):
                os.remove("bozza_corrente.json")
        else:
            print("Errore: Nessuna bozza trovata da pubblicare.")
        return

    if not api_key:
        raise ValueError("API Key di Gemini non trovata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)
    used_images = get_existing_images()
    shuffled_sources = list(RSS_SOURCES)
    random.shuffle(shuffled_sources)

    selected_entry = None
    title, summary, original_link, slug = "", "", "", ""
    found_article = False
    rss_img_url = None

    while not found_article and shuffled_sources:
        rss_url = shuffled_sources.pop(0)
        try:
            feed = feedparser.parse(rss_url)
        except Exception:
            continue
        if not feed.entries:
            continue
        entries = list(feed.entries)
        random.shuffle(entries)
        for entry in entries:
            entry_title = entry.get('title', '')
            entry_summary = entry.get('summary', '')
            temp_slug = slugify(entry_title)
            if not temp_slug or os.path.exists(f"articoli/{temp_slug}.html"):
                continue
            
            text_to_check = (entry_title + " " + entry_summary).lower()
            
            # Filtro 1: Esclusione altri animali
            if any(animal in text_to_check for animal in EXCLUDED_ANIMALS):
                continue

            # Filtro 2: Esclusione contenuti promozionali/marchi
            if any(promo in text_to_check for promo in PROMO_KEYWORDS):
                continue

            if any(k in text_to_check for k in ['cane', 'cani', 'dog', 'dogs', 'puppy', 'gatto', 'gatti', 'cat', 'cats', 'kitten', 'pet', 'pets']):
                selected_entry = entry
                title = entry_title
                summary = entry_summary
                original_link = entry.get('link', '#')
                slug = temp_slug
                rss_img_url = get_rss_image(entry)
                found_article = True
                break

    if not found_article:
        raise RuntimeError("Nessun articolo inedito valido trovato.")

    prompt = f"""
    Sei il caporedattore senior del magazine online 'zampamania.com'. Riscrivi la notizia in un italiano giornalistico eccellente, curato e approfondito.

    REGOLE OBBLIGATORIE:
    1. Se nel testo/fonte originale sono presenti link o riferimenti a fonti esterne, siti o profili social, INCLUDILI mantenendo i link cliccabili tramite tag <a href="..." target="_blank">Nome Fonte/Profilo</a>.
    2. NON includere o promuovere marchi commerciali o sponsorizzazioni.
    3. Nella descrizione SEO fai SEMPRE riferimento esplicito a "zampamania.com" (NON usare solo "Zampamania").

    Scrivi almeno 4 o 5 paragrafi dettagliati (<p>), intervallati da almeno 2 sottotitoli (<h2>).

    Restituisci l'output rigorosamente in questo formato:
    ===TITOLO===
    [Titolo in italiano]
    ===SEO===
    [Meta description di circa 150 caratteri che cita zampamania.com]
    ===CONTENUTO===
    [Il corpo dell'articolo in HTML con tag <p>, <h2> e eventuali tag <a href="...">]

    Titolo originale: {title}
    Contenuto originale: {summary}
    Link originale: {original_link}
    """

    models_to_try = ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash"]
    response = None
    
    for model_name in models_to_try:
        try:
            print(f"Tentativo di generazione con il modello: {model_name}...")
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response and response.text:
                print(f"Generazione riuscita con successo usando {model_name}!")
                break
        except Exception as e:
            print(f"Modello {model_name} non disponibile o errore: {e}. Provo il successivo...")
            continue

    if not response or not response.text:
        raise RuntimeError("Tutti i modelli Gemini configurati hanno fallito la generazione.")

    text_response = response.text

    try:
        parts_title = text_response.split("===SEO===")
        new_title = parts_title[0].replace("===TITOLO===", "").strip()
        parts_seo = parts_title[1].split("===CONTENUTO===")
        new_desc = parts_seo[0].strip()
        html_content = parts_seo[1].strip()
    except Exception:
        new_title = title
        new_desc = f"Scopri le ultime notizie su zampamania.com: {summary[:120]}..."
        html_content = f"<p>{summary}</p>"

    is_cat = any(k in (new_title + " " + new_desc).lower() for k in ['gatto', 'gatti', 'cat', 'cats', 'kitten', 'micio'])

    if rss_img_url:
        image_url = rss_img_url
        is_indicative = False
    else:
        image_url = get_local_pet_image(is_cat_article=is_cat, used_images=used_images)
        is_indicative = True

    draft_data = {
        "slug": slug,
        "title": new_title,
        "description": new_desc,
        "content": html_content,
        "image_url": image_url,
        "is_indicative": is_indicative,
        "original_link": original_link
    }

    with open("bozza_corrente.json", "w", encoding="utf-8") as f:
        json.dump(draft_data, f, ensure_ascii=False, indent=4)

    send_telegram_draft(image_url, new_title, new_desc, html_content)
    print("Bozza inviata su Telegram in attesa di approvazione. Esecuzione terminata correttamente.")

if __name__ == "__main__":
    main()
