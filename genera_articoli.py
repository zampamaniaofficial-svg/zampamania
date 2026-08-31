import os
import re
import datetime
import feedparser
from google import genai

# Fonte RSS di settore (puoi sostituirla con qualsiasi feed di notizie sugli animali)
RSS_URL = "https://www.kodami.it/feed/"

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

    print("Controllo feed RSS...")
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Nessun articolo trovato nel feed.")
        return

    # Seleziona l'articolo più recente
    entry = feed.entries[0]
    title = entry.title
    summary = entry.get('summary', '')

    slug = slugify(title)
    filename = f"articoli/{slug}.html"

    # Verifica se l'articolo è già stato pubblicato
    if os.path.exists(filename):
        print(f"L'articolo '{title}' è già presente sul sito.")
        return

    print(f"Elaborazione in corso per: {title}")

    # Prompt ottimizzato per l'IA
    prompt = f"""
    Sei un redattore esperto per 'Zampamania', un portale italiano dedicato agli animali domestici, cani e gatti, e al risparmio per i proprietari.
    Riscrivi la seguente notizia in modo originale, coinvolgente e professionale in lingua italiana, evitando qualsiasi plagio.
    Struttura l'output in formato HTML puro (senza blocchi di codice markdown), usando tag <p> per i paragrafi e <h2> per eventuali sottotitoli.
    
    Titolo originale: {title}
    Contenuto originale: {summary}
    
    Restituisci la risposta seguendo rigorosamente questa struttura:
    TITOLO_OTTIMIZZATO: [Inserisci qui un titolo accattivante]
    DESCRIZIONE_SEO: [Una meta description di circa 150 caratteri]
    CONTENUTO_HTML: [Il corpo dell'articolo formattato con tag HTML]
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
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

    # Leggi il template HTML
    with open("articoli/template.html", "r", encoding="utf-8") as f:
        template = f.read()

    # Inserisci i dati dinamici nel template
    article_html = template.replace("{{title}}", new_title)
    article_html = article_html.replace("{{description}}", new_desc)
    article_html = article_html.replace("{{date}}", current_date)
    article_html = article_html.replace("{{content}}", html_content)

    # Salva il file della notizia
    with open(filename, "w", encoding="utf-8") as f:
        f.write(article_html)

    print(f"Creato con successo il file: {filename}")

    # Aggiorna la homepage index.html inserendo la card dell'articolo in cima alla griglia
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
