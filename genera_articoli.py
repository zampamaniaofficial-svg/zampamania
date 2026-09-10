import os
import re
import datetime
import time
import random
import socket
import feedparser
from google import genai

# Timeout globale di sicurezza sulle connessioni di rete
socket.setdefaulttimeout(15)

# Elenco completo delle fonti RSS
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
            
    if os.path.exists("articoli"):
        for fname in os.listdir("articoli"):
            if fname.endswith(".html"):
                try:
                    with open(os.path.join("articoli", fname), "r", encoding="utf-8") as f:
                        content = f.read()
                        srcs = re.findall(r'<img[^>]+src="([^">]+)"', content)
                        for s in srcs:
                            used.add(s)
                except Exception:
                    pass
    return used

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

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API Key non trovata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)
    used_images = get_existing_images()

    shuffled_sources = list(RSS_SOURCES)
    random.shuffle(shuffled_sources)

    selected_entry = None
    slug = ""
    filename = ""
    original_link = ""
    title = ""
    summary = ""
    found_article = False
    sources_checked = 0

    while not found_article and shuffled_sources:
        rss_url = shuffled_sources.pop(0)
        sources_checked += 1
        print(f"[{sources_checked}] Controllo feed RSS dalla fonte: {rss_url}...")

        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"Errore nel parsing del feed {rss_url}: {e}")
            continue

        if not feed.entries:
            continue

        entries = list(feed.entries)
        random.shuffle(entries)

        for entry in entries:
            entry_title = entry.get('title', '')
            entry_summary = entry.get('summary', '')
            
            # Controllo data: scarta notizie più vecchie di 30 giorni
            pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
            if pub_date:
                article_date = datetime.datetime.fromtimestamp(time.mktime(pub_date))
                max_age_days = 30
                if (datetime.datetime.now() - article_date).days > max_age_days:
                    continue  # Salta l'articolo se risale a più di un mese fa
            
            temp_slug = slugify(entry_title)
            if not temp_slug:
                continue
                
            temp_filename = f"articoli/{temp_slug}.html"
            if os.path.exists(temp_filename):
                continue

            text_to_check = (entry_title + " " + entry_summary).lower()
            is_valid_pet = any(keyword in text_to_check for keyword in [
                'cane', 'cani', 'dog', 'dogs', 'puppy', 'puppies', 'cucciolo', 'cuccioli',
                'gatto', 'gatti', 'cat', 'cats', 'kitten', 'kittens', 'gattino', 'gattini',
                'feline', 'canine', 'pet', 'pets', 'animale', 'animali'
            ])

            if is_valid_pet:
                selected_entry = entry
                title = entry_title
                summary = entry_summary
                original_link = entry.get('link', '#')
                slug = temp_slug
                filename = temp_filename
                found_article = True
                print(f"Articolo valido trovato: {title}")
                break

    if not found_article:
        raise RuntimeError("Impossibile trovare alcun articolo inedito sulle fonti RSS.")

    prompt = f"""
    Sei il caporedattore senior del magazine online 'Zampamania', esperto di fama in cinofilia e felinologia.
    Riscrivi la seguente notizia in un italiano giornalistico eccellente, curato, molto approfondito, accattivante e professionale.
    
    REGOLE TASSATIVE:
    1. L'articolo deve trattare ESCLUSIVAMENTE di cani, gatti o animali domestici.
    2. LUNGHEZZA E APPROFONDIMENTO: L'articolo deve essere corposo e strutturato in modo esaustivo. Scrivi almeno 4 o 5 paragrafi dettagliati (<p>), intervallati da almeno 2 o 3 sottotitoli informativi (<h2>). Espandi la notizia analizzando il contesto, i consigli pratici per i proprietari di animali e l'impatto della notizia stessa.
    3. Struttura l'output in formato HTML puro (senza blocchi markdown).
    4. Fornisci MASSIMO 2 o 3 parole chiave in inglese brevi per la foto (es. "cute cat portrait").
    5. ALLA FINE DELL'ARTICOLO inserisci rigorosamente:
        - Un box banner d'impatto per Telegram: <div style="background:#0284c7; color:#fff; padding:25px; border-radius:10px; text-align:center; margin:35px 0; box-shadow:0 4px 6px rgba(0,0,0,0.1);"><h3 style="margin:0 0 10px 0; font-size:22px;">Non perderti le migliori offerte pet!</h3><p style="margin:0 0 15px 0; font-size:15px;">Unisciti al canale Telegram di Zampamania per sconti e promozioni lampo dedicate a cani e gatti.</p><a href="https://t.me/TUOCANALE" target="_blank" style="background:#fff; color:#0284c7; padding:12px 25px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block;">Unisciti al Canale Offerte</a></div>
        - Sotto al banner Telegram, posiziona in secondo piano il link alla fonte originale: <div style="text-align:center; margin-top:20px;"><a href="{original_link}" target="_blank" style="color:#94a3b8; font-size:12px; text-decoration:underline;">Fonte originale della notizia</a></div>
    
    Titolo originale: {title}
    Contenuto originale: {summary}
    
    RISPONDI RIGOROSAMENTE USANDO QUESTO FORMATO:
    ===TITOLO===
    [Titolo accattivante in italiano]
    ===SEO===
    [Meta description di circa 150 caratteri]
    ===KEYWORD===
    [2 o 3 parole chiave in inglese]
    ===CONTENUTO===
    [Il corpo esteso e dettagliato dell'articolo in HTML con i tag <p>, <h2>, il banner Telegram e la fonte in fondo]
    """

    # Modelli aggiornati e ordinati in modo inverso per la rotazione
    models_to_try = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2-flash-lite",
        "gemini-2-flash"
    ]
    max_attempts = 3
    response = None
    success_model = False

    for model_name in models_to_try:
        print(f"Tentativi con il modello: {model_name}")
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Generazione (Tentativo {attempt}/{max_attempts})...")
                response = client.models.generate_content(model=model_name, contents=prompt)
                success_model = True
                break
            except Exception as e:
                print(f"Tentativo {attempt} fallito con {model_name}: {e}")
                if attempt < max_attempts:
                    time.sleep(attempt * 3)
        if success_model:
            break

    if not response:
        raise RuntimeError("Impossibile completare la generazione: limiti giornalieri (RPD) esauriti su tutti i modelli disponibili.")
    
    text_response = response.text
    
    try:
        parts_title = text_response.split("===SEO===")
        title_part = parts_title[0].replace("===TITOLO===", "").strip()
        parts_seo = parts_title[1].split("===KEYWORD===")
        seo_part = parts_seo[0].strip()
        parts_kw = parts_seo[1].split("===CONTENUTO===")
        keyword_part = parts_kw[0].strip()
        html_content = parts_kw[1].strip()
        
        new_title = title_part if title_part else title
        new_desc = seo_part if seo_part else summary[:150]
        image_keyword = keyword_part if keyword_part else "cute pet"
    except Exception as e:
        print(f"Errore nel parsing: {e}. Uso fallback.")
        new_title = title
        new_desc = summary[:150]
        image_keyword = "cute pet"
        html_content = f"<p>{summary}</p>"

    combined_text_check = (new_title + " " + new_desc + " " + image_keyword).lower()
    is_cat = any(k in combined_text_check for k in ['gatto', 'gatti', 'cat', 'cats', 'kitten', 'felin', 'micio'])

    # Ricerca immagine dalle cartelle locali GitHub con controllo anti-duplicati e specie
    image_url = get_local_pet_image(is_cat_article=is_cat, used_images=used_images)

    # Percorso immagine adattato per la pagina di dettaglio (nella cartella /articoli)
    article_image_url = f"../{image_url}"

    featured_image_html = f'<div style="text-align: center; margin-bottom: 25px; aspect-ratio: 16/9; max-height: 450px; overflow: hidden; border-radius: 8px;"><img src="{article_image_url}" alt="{new_title}" style="width: 100%; height: 100%; object-fit: cover;"></div>'
    html_content = featured_image_html + html_content

    current_date = datetime.date.today().strftime("%d/%m/%Y")

    with open("articoli/template.html", "r", encoding="utf-8") as f:
        template = f.read()

    article_html = template.replace("{{title}}", new_title).replace("{{description}}", new_desc).replace("{{date}}", current_date).replace("{{content}}", html_content)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(article_html)

    # Inserimento nella griglia Magazine della Home
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
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(index_content)
        print("Homepage aggiornata con successo.")

if __name__ == "__main__":
    main()
