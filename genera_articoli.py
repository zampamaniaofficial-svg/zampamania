import os
import re
import datetime
import time
import random
import urllib.parse
import urllib.request
import json
import feedparser
from google import genai

# Elenco di 10 fonti RSS ESCLUSIVAMENTE focalizzate su cani, gatti e pet domestici
RSS_SOURCES = [
    "https://www.kodami.it/feed/",
    "https://www.dogster.com/feed",
    "https://www.catster.com/feed",
    "https://www.petful.com/feed/",
    "https://iheartdogs.com/feed",
    "https://dogingtonpost.com/feed",
    "https://goodnewsforpets.com/feed",
    "https://icatcare.org/feed/",
    "https://www.thelabradorsite.com/feed/",
    "https://www.catsofaustralia.com/blog/rss"
]

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def get_wikimedia_image(query_str):
    """Cerca una vera foto professionale su Wikimedia Commons con fallback sicuro."""
    clean_query = re.sub(r'[^a-zA-Z0-9\s]', '', query_str)
    if not clean_query.strip():
        clean_query = "dog and cat"
        
    encoded_query = urllib.parse.quote(clean_query)
    url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={encoded_query}&gsrnamespace=6&gsrlimit=5&prop=imageinfo&iiprop=url&format=json"
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'ZampamaniaNewsBot/2.0 (Professional Pet Journal)'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    img_url = imageinfo[0].get("url")
                    if img_url and any(img_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                        return img_url
    except Exception as e:
        print(f"Errore ricerca immagine Wikimedia: {e}")
    
    return "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Golde33443.jpg/800px-Golde33443.jpg"

def generate_with_fallback(client, prompt):
    """Tenta la generazione con il modello principale e, in caso di errore 503, passa ai modelli di fallback."""
    models_to_try = ['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-1.5-flash']
    
    for model_name in models_to_try:
        for attempt in range(2): # 2 tentativi per modello
            try:
                print(f"Tentativo con il modello {model_name} (Tentativo {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response
            except Exception as e:
                print(f"Modello {model_name} fallito: {e}")
                time.sleep(5)
                
    raise RuntimeError("Tutti i modelli Gemini disponibili sono attualmente sovraccarichi. Riprova più tardi.")

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API Key non trovata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)

    # 1. Scelta casuale della fonte RSS
    rss_url = random.choice(RSS_SOURCES)
    print(f"Controllo feed RSS dalla fonte: {rss_url}...")
    
    feed = feedparser.parse(rss_url)
    if not feed.entries:
        print("Nessun articolo trovato nel feed.")
        return

    entries = list(feed.entries)
    random.shuffle(entries)

    selected_entry = None
    slug = ""
    filename = ""
    
    for entry in entries:
        title = entry.title
        summary = entry.get('summary', '')
        
        temp_slug = slugify(title)
        temp_filename = f"articoli/{temp_slug}.html"
        
        text_to_check = (title + " " + summary).lower()
        is_dog_or_cat = any(keyword in text_to_check for keyword in [
            'cane', 'cani', 'dog', 'dogs', 'puppy', 'puppies', 'cucciolo', 'cuccioli',
            'gatto', 'gatti', 'cat', 'cats', 'kitten', 'kittens', 'gattino', 'gattini',
            'feline', 'canine', 'pet', 'pets'
        ])
        
        if not os.path.exists(temp_filename) and is_dog_or_cat:
            selected_entry = entry
            slug = temp_slug
            filename = temp_filename
            break

    if not selected_entry:
        print("Nessun nuovo articolo idoneo su cani/gatti trovato in questo feed.")
        return

    title = selected_entry.title
    summary = selected_entry.get('summary', '')
    original_link = selected_entry.get('link', '#')

    print(f"Trovato articolo valido: {title}")

    prompt = f"""
    Sei il caporedattore del magazine online 'Zampamania', esperto in cinofilia e felinologia.
    Riscrivi la seguente notizia in un italiano giornalistico eccellente, curato, accattivante e professionale.
    
    REGOLE TASSATIVE:
    1. L'articolo deve trattare ESCLUSIVAMENTE di cani e/o gatti.
    2. Struttura l'output in formato HTML puro (senza blocchi di codice markdown), usando tag <p> per i paragrafi e <h2> per eventuali sottotitoli.
    3. Fornisci 2 o 3 parole chiave in inglese focalizzate sul cane o gatto protagonista per trovare una foto reale (es. "cute golden retriever dog" o "sleeping kitten cat").
    4. Alla fine dell'articolo, inserisci il link alla fonte originale usando esattamente questo codice HTML: <a href="{original_link}" target="_blank" style="display:inline-block; background:#0284c7; color:#fff; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:600; margin-top:15px;">Guarda la notizia originale / Fonte</a>.
    
    Titolo originale: {title}
    Contenuto originale: {summary}
    
    RISPONDI RIGOROSAMENTE USANDO QUESTO FORMATO ESATTO (inclusi i prefissi in maiuscolo):
    ===TITOLO===
    [Titolo accattivante in italiano]
    ===SEO===
    [Meta description di circa 150 caratteri in italiano]
    ===KEYWORD===
    [Parole chiave in inglese per la foto, es. happy dog park]
    ===CONTENUTO===
    [Il corpo dell'articolo in HTML con i tag <p> e <h2> e il link finale]
    """

    # Generazione con sistema di fallback integrato
    response = generate_with_fallback(client, prompt)
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
        image_keyword = keyword_part if keyword_part else "cute dog cat"
    except Exception as e:
        print(f"Errore nel parsing della risposta IA: {e}. Uso valori di fallback.")
        new_title = title
        new_desc = summary[:150] if summary else "Notizia dal mondo dei pet."
        image_keyword = "cute dog and cat"
        html_content = f"<p>{summary}</p><a href='{original_link}' target='_blank' style='display:inline-block; background:#0284c7; color:#fff; padding:10px 20px; border-radius:5px; text-decoration:none; font-weight:600; margin-top:15px;'>Fonte originale</a>"

    print(f"Ricerca foto reale con chiave: '{image_keyword}'...")
    image_url = get_wikimedia_image(image_keyword)

    featured_image_html = f'<div style="text-align: center; margin-bottom: 25px;"><img src="{image_url}" alt="{new_title}" style="width: 100%; max-height: 450px; object-fit: cover; border-radius: 8px;"></div>'
    html_content = featured_image_html + html_content

    current_date = datetime.date.today().strftime("%d/%m/%Y")

    with open("articoli/template.html", "r", encoding="utf-8") as f:
        template = f.read()

    article_html = template.replace("{{title}}", new_title)
    article_html = template.replace("{{description}}", new_desc)
    article_html = template.replace("{{date}}", current_date)
    article_html = template.replace("{{content}}", html_content)

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
