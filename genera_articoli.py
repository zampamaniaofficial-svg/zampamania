import os
import re
import datetime
import time
import feedparser
import random
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

# Estrae casualmente una fonte diversa a ogni esecuzione del workflow
RSS_URL = random.choice(RSS_SOURCES)

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

    print(f"Controllo feed RSS dalla fonte: {RSS_URL}...")
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Nessun articolo trovato nel feed.")
        return

    # Seleziona l'articolo più recente
    entry = feed.entries[0]
    title = entry.title
    summary = entry.get('summary', '')
    original_link = entry.get('link', '#')

    slug = slugify(title)
    filename = f"articoli/{slug}.html"

    # Verifica se l'articolo è già stato pubblicato
    if os.path.exists(filename):
        print(f"L'articolo '{title}' è già presente sul sito.")
        return

    print(f"Elaborazione in corso per: {title}")

    prompt = f"""
    Sei un caporedattore ed esperto giornalista specializzato nel mondo degli animali domestici ('Zampamania'), cani e gatti, e nella cura dei pet.
    Partendo dalle informazioni e dai temi trattati in questa notizia:
    
    REGOLE TASSATIVE:
    1. TRADUZIONE E ADATTAMENTO: Se la fonte di partenza è in inglese o in un'altra lingua straniera, traduci i contenuti in un eccellente italiano giornalistico, adattando i termini tecnici veterinari o comportamentali in modo naturale.
    2. RIELABORAZIONE ORIGINALE: Riscrivi la notizia in modo originale, coinvolgente e professionale, evitando qualsiasi plagio.
    3. FORMATTAZIONE HTML: Struttura l'output in formato HTML puro (senza blocchi di codice markdown), usando tag <p> per i paragrafi e <h2> per eventuali sottotitoli.
    4. LINK FONTE: Alla fine dell'articolo, inserisci un link ben visibile che rimandi alla notizia o fonte originale usando esattamente questo URL: {original_link}. Crea un bottone o un testo evidenziato con stile usando esattamente questo codice: <a href="{original_link}" target="_blank" style="display:inline-block; background:#0284c7; color:#fff; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:600; margin-top:15px;">Guarda la notizia originale / Fonte</a>.
    
    Titolo originale: {title}
    Contenuto originale: {summary}
    
    Restituisci la risposta seguendo rigorosamente questa struttura:
    TITOLO_OTTIMIZZATO: [Inserisci qui un titolo accattivante in italiano]
    DESCRIZIONE_SEO: [Una meta description in italiano di circa 150 caratteri]
    CONTENUTO_HTML: [Il corpo dell'articolo formattato con tag HTML, inclusi il link finale]
    """

    # Sistema di retry automatico in caso di errore 503 o sovraccarico temporaneo
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

        new_title = title_match.group(1).strip() if title_match else title
        new_desc = desc_match.group(1).strip() if desc_match else summary[:150]
    except Exception as e:
        print(f"Errore nel parsing della risposta IA: {e}")
        return

    current_date = datetime.date.today().strftime("%d/%m/%Y")

    with open("articoli/template.html", "r", encoding="utf-8") as f:
        template = f.read()

    article_html = template.replace("{{title}}", new_title)
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
                <p>{new_desc}</p>
                <span style="font-size: 12px; color: var(--gray); display:inline-block; margin-top:10px;"><i class="fa-regular fa-calendar"></i> {current_date}</span>
            </div>
    """

    if '<div class="grid">' in index_content:
        index_content = index_content.replace('<div class="grid">', f'<div class="grid">\n{new_card}')
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(index_content)
        print("Homepage aggiornata con il nuovo articolo.")

if __name__ == "__main__":
    main()
