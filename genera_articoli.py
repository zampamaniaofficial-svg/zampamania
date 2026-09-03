import os
import re
import datetime
import time
import random
import urllib.parse
import feedparser
from google import genai

# Elenco delle 10 fonti RSS multiple (italiane e internazionali)
RSS_SOURCES = [
    "https://www.kodami.it/feed/",
    "https://www.dogster.com/feed",
    "https://www.catster.com/feed",
    "https://www.zooborns.com/zooborns/rss.xml",
    "https://www.petful.com/feed/",
    "https://iheartdogs.com/feed",
    "https://dogingtonpost.com/feed",
    "https://goodnewsforpets.com/feed",
    "https://www.sciencedaily.com/rss/plants_animals.xml",
    "https://icatcare.org/feed/"
]

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API Key non trovata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)

    # 1. Scelta casuale della fonte RSS
    rss_url = random.choice(RSS_SOURCES)
    print(f"Controllo feed RSS dalla fonte casuale: {rss_url}...")
    
    feed = feedparser.parse(rss_url)
    if not feed.entries:
        print("Nessun articolo trovato nel feed.")
        return

    # 2. Doppia casualità con controllo duplicati: mescola gli articoli del feed e scegline uno non ancora pubblicato
    entries = list(feed.entries)
    random.shuffle(entries)

    selected_entry = None
    slug = ""
    filename = ""
    
    for entry in entries:
        title = entry.title
        temp_slug = slugify(title)
        temp_filename = f"articoli/{temp_slug}.html"
        
        # Verifica se l'articolo NON esiste già
        if not os.path.exists(temp_filename):
            selected_entry = entry
            slug = temp_slug
            filename = temp_filename
            break

    if not selected_entry:
        print("Tutti gli articoli disponibili in questo feed sono già stati pubblicati.")
        return

    title = selected_entry.title
    summary = selected_entry.get('summary', '')
    original_link = selected_entry.get('link', '#')

    print(f"Elaborazione in corso per l'articolo: {title}")

    # Prompt aggiornato per includere anche la richiesta di un prompt visivo per l'immagine
    prompt = f"""
    Sei un caporedattore ed esperto giornalista specializzato nel mondo degli animali domestici ('Zampamania'), cani e gatti, e nella cura dei pet.
    Partendo dalle informazioni e dai temi trattati in questa notizia:
    
    REGOLE TASSATIVE:
    1. TRADUZIONE E ADATTAMENTO: Se la fonte di partenza è in inglese o in un'altra lingua straniera, traduci i contenuti in un eccellente italiano giornalistico, adattando i termini tecnici veterinari o comportamentali in modo naturale.
    2. RIELABORAZIONE ORIGINALE: Riscrivi la notizia in modo originale, coinvolgente e professionale, evitando qualsiasi plagio.
    3. FORMATTAZIONE HTML: Struttura l'output in formato HTML puro (senza blocchi di codice markdown), usando tag <p> per i paragrafi e <h2> per eventuali sottotitoli.
    4. IMMAGINE: Scrivi un prompt descrittivo in lingua inglese per generare un'immagine fotografica e realistica inerente all'articolo (es. "A cute cat sleeping on a sofa, professional photography, warm lighting").
    5. LINK FONTE: Alla fine dell'articolo, inserisci un link ben visibile che rimandi alla notizia o fonte originale usando esattamente questo codice: <a href="{original_link}" target="_blank" style="display:inline-block; background:#0284c7; color:#fff; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:600; margin-top:15px;">Guarda la notizia originale / Fonte</a>.
    
    Titolo originale: {title}
    Contenuto originale: {summary}
    
    Restituisci la risposta seguendo rigorosamente questa struttura:
    TITOLO_OTTIMIZZATO: [Inserisci qui un titolo accattivante in italiano]
    DESCRIZIONE_SEO: [Una meta description in italiano di circa 150 caratteri]
    IMMAGINE_PROMPT: [Prompt in inglese per la generazione dell'immagine]
    CONTENUTO_HTML: [Il corpo dell'articolo formattato con tag HTML, inclusi il link finale]
    """

    # Sistema di retry automatico per gestire eventuali picchi di traffico (errore 503)
    response = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            break
        except Exception as e:
            print(f"Tentativo {attempt + 1} fallito: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"Attendo {wait_time} secondi prima di riprovare...")
                time.sleep(wait_time)
            else:
                raise e
    
    text_response = response.text
    
    try:
        parts = text_response.split("CONTENUTO_HTML:")
        header_part = parts[0]
        html_content = parts[1].strip()

        title_match = re.search(r"TITOLO_OTTIMIZZATO:\s*(.*)", header_part)
        desc_match = re.search(r"DESCRIZIONE_SEO:\s*(.*)", header_part)
        img_match = re.search(r"IMMAGINE_PROMPT:\s*(.*)", header_part)

        new_title = title_match.group(1).strip() if title_match else title
        new_desc = desc_match.group(1).strip() if desc_match else summary[:150]
        img_prompt = img_match.group(1).strip() if img_match else f"A cute pet animal, {new_title}"
    except Exception as e:
        print(f"Errore nel parsing della risposta IA: {e}")
        return

    # Generazione dell'URL dell'immagine tramite IA (servizio stabile via URL)
    encoded_img_prompt = urllib.parse.quote(img_prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_img_prompt}?width=800&height=450&nologo=true"

    # Inserisce l'immagine in cima al corpo dell'articolo
    featured_image_html = f'<div style="text-align: center; margin-bottom: 25px;"><img src="{image_url}" alt="{new_title}" style="width: 100%; max-height: 450px; object-fit: cover; border-radius: 8px;"></div>'
    html_content = featured_image_html + html_content

    current_date = datetime.date.today().strftime("%d/%m/%Y")

    # Leggi il template HTML dell'articolo
    with open("articoli/template.html", "r", encoding="utf-8") as f:
        template = f.read()

    # Inserisci i dati dinamici nel template
    article_html = template.replace("{{title}}", new_title)
    article_html = article_html.replace("{{description}}", new_desc)
    article_html = article_html.replace("{{date}}", current_date)
    article_html = article_html.replace("{{content}}", html_content)

    # Salva il file HTML della notizia
    with open(filename, "w", encoding="utf-8") as f:
        f.write(article_html)

    print(f"Creato con successo il file: {filename}")

    # Aggiorna la homepage index.html inserendo la card con miniatura sotto al titolo/link
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
        print("Homepage aggiornata con il nuovo articolo e miniatura.")

if __name__ == "__main__":
    main()
