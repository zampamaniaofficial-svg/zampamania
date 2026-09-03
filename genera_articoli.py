import os
import re
import datetime
import time
import random
import urllib.parse
import urllib.request
import json
import socket
import feedparser
from google import genai

# Timeout globale di sicurezza sulle connessioni di rete
socket.setdefaulttimeout(15)

# Elenco completo ed espanso di fonti RSS (Internazionali di settore + Italiane)
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

def get_wikimedia_image(query_str, is_cat_article=False):
    # Fallback sicuri e diretti nel caso la ricerca API non trovi riscontro
    fallback_image = "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg" if is_cat_article else "https://upload.wikimedia.org/wikipedia/commons/4/47/American_Eskimo_Dog.jpg"
    
    clean_query = re.sub(r'[^a-zA-Z0-9\s]', '', query_str)
    if not clean_query.strip():
        clean_query = "domestic cat" if is_cat_article else "dog"
        
    encoded_query = urllib.parse.quote(clean_query)
    url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={encoded_query}&gsrnamespace=6&gsrlimit=10&prop=imageinfo&iiprop=url&format=json"
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'ZampamaniaNewsBot/2.0 (Professional Pet Journal)'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    img_url = imageinfo[0].get("url")
                    if img_url and any(img_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                        img_lower = img_url.lower()
                        if is_cat_article and 'dog' in img_lower and 'cat' not in img_lower:
                            continue
                        return img_url
    except Exception as e:
        print(f"Errore o timeout nella ricerca immagine Wikimedia: {e}")
    
    return fallback_image

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API Key non trovata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)

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
            print(f"Errore nel parsing del feed RSS {rss_url}: {e}")
            continue

        if not feed.entries:
            print("Feed vuoto o non raggiungibile. Passo alla prossima fonte...")
            continue

        entries = list(feed.entries)
        random.shuffle(entries)

        for entry in entries:
            entry_title = entry.get('title', '')
            entry_summary = entry.get('summary', '')
            
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
            print("Nessun articolo idoneo/inedito in questo feed. Continuo la ricerca su un'altra fonte...")

    if not found_article:
        raise RuntimeError("Impossibile trovare alcun articolo inedito su tutte le fonti RSS analizzate.")

    prompt = f"""
    Sei il caporedattore del magazine online 'Zampamania', esperto in cinofilia e felinologia.
    Riscrivi la seguente notizia in un italiano giornalistico eccellente, curato, accattivante e professionale.
    
    REGOLE TASSATIVE:
    1. L'articolo deve trattare ESCLUSIVAMENTE di cani, gatti o animali domestici.
    2. Struttura l'output in formato HTML puro (senza blocchi di codice markdown), usando tag <p> per i paragrafi e <h2> per eventuali sottotitoli.
    3. Fornisci MASSIMO 2 o 3 parole chiave in inglese brevi e semplici per la foto (es. "cute cat" oppure "happy dog"). NON inserire titoli o frasi lunghe.
    4. Alla fine dell'articolo, inserisci il link alla fonte originale usando esattamente questo codice HTML: <a href="{original_link}" target="_blank" style="display:inline-block; background:#0284c7; color:#fff; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:600; margin-top:15px;">Guarda la notizia originale / Fonte</a>.
    
    Titolo originale: {title}
    Contenuto originale: {summary}
    
    RISPONDI RIGOROSAMENTE USANDO QUESTO FORMATO ESATTO (inclusi i prefissi in maiuscolo):
    ===TITOLO===
    [Titolo accattivante in italiano]
    ===SEO===
    [Meta description di circa 150 caratteri in italiano]
    ===KEYWORD===
    [2 o 3 parole chiave in inglese brevi, es. cute cat]
    ===CONTENUTO===
    [Il corpo dell'articolo in HTML con i tag <p> e <h2> e il link finale]
    """

    models_to_try = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.7-flash']
    max_attempts = 5
    response = None
    success_model = False

    for model_name in models_to_try:
        print(f"Inizio tentativi con il modello Gemini: {model_name}")
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Generazione con {model_name} (Tentativo {attempt}/{max_attempts})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                success_model = True
                print(f"Successo con il modello {model_name} al tentativo {attempt}!")
                break
            except Exception as e:
                print(f"Tentativo {attempt} fallito su {model_name}: {e}")
                if attempt < max_attempts:
                    wait_time = attempt * 10
                    print(f"Attendo {wait_time} secondi prima di riprovare...")
                    time.sleep(wait_time)
        
        if success_model:
            break

    if not response:
        raise RuntimeError("Impossibile completare la generazione: modelli non disponibili o chiave non valida.")
    
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
        image_keyword = keyword_part if keyword_part else "cute cat"
    except Exception as e:
        print(f"Errore nel parsing della risposta IA: {e}. Uso valori di fallback.")
        new_title = title
        new_desc = summary[:150] if summary else "Notizia dal mondo dei pet."
        image_keyword = "cute cat"
        html_content = f"<p>{summary}</p><a href='{original_link}' target='_blank' style='display:inline-block; background:#0284c7; color:#fff; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:600; margin-top:15px;'>Fonte originale</a>"

    # Verifica se l'articolo parla di gatti
    combined_text_check = (new_title + " " + new_desc + " " + image_keyword).lower()
    is_cat = any(k in combined_text_check for k in ['gatto', 'gatti', 'cat', 'cats', 'kitten', 'felin', 'micio'])

    # SICUREZZA: se la keyword restituita è una frase lunga o contiene parole italiane, la normalizziamo
    if len(image_keyword.split()) > 4 or any(w in image_keyword.lower() for w in ['il', 'la', 'di', 'che', 'e', 'un', 'le', 'del', 'sette', 'storie']):
        image_keyword = "cute cat" if is_cat else "dog"

    print(f"Ricerca foto reale con chiave sanificata: '{image_keyword}' (Target gatto: {is_cat})...")
    image_url = get_wikimedia_image(image_keyword, is_cat_article=is_cat)

    featured_image_html = f'<div style="text-align: center; margin-bottom: 25px;"><img src="{image_url}" alt="{new_title}" style="width: 100%; max-height: 450px; object-fit: cover; border-radius: 8px;"></div>'
    html_content = featured_image_html + html_content

    current_date = datetime.date.today().strftime("%d/%m/%Y")

    with open("articoli/template.html", "r", encoding="utf-8") as f:
        template = f.read()

    article_html = template
    article_html = article_html.replace("{{title}}", new_title)
    article_html = article_html.replace("{{description}}", new_desc)
    article_html = article_html.replace("{{date}}", current_date)
    article_html = article_html.replace("{{content}}", html_content)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(article_html)

    print(f"Creato con successo il file: {filename}")

    with open("index.html", "r", encoding="utf-8") as f:
        index_content = f.read()

    new_card = f"""
            <div class="card">
                <div class="card-icon"><i class="fa-solid fa-newspaper"></i></div>
                <h3><a href="articoli/{slug}.html" style="text-decoration:none; color:inherit;">{new_title}</a></h3>
                <div style="margin: 12px 0;"><img src="{image_url}" alt="{new_title}" style="width: 100%; height: 160px; object-fit: cover; border-radius: 6px;"></div>
                <p>{new_desc}</p>
                <span style="font-size: 12px; color: var(--gray); display:inline-block; margin-top:10px;"><i class="fa-regular fa-calendar"></i> {current_date}</span>
            </div>
    """

    if '<div class="grid">' in index_content:
        index_content = index_content.replace('<div class="grid">', f'<div class="grid">\n{new_card}')
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(index_content)
        print("Homepage aggiornata con successo.")

if __name__ == "__main__":
    main()
