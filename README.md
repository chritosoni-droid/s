# FisioEvidenceBot

Bot per fisioterapisti che genera protocolli riabilitativi completi basati **esclusivamente su evidenze scientifiche PubMed**.

## Cosa fa

Inserisci la condizione del paziente (es. *"ginocchio crociato operato 3 mesi"*, *"lesione muscolare grado 2 classificazione Monaco"*) e il bot:

1. Cerca automaticamente su PubMed: systematic reviews, meta-analisi, RCT, studi di coorte
2. Sintetizza le evidenze più recenti e di maggiore qualità
3. Genera un protocollo completo strutturato in fasi con:
   - Valutazione iniziale
   - Fasi riabilitative (Fase 1→4)
   - **RTP** — Return to Play
   - **RTT** — Return to Training  
   - **RTS** — Return to Sport
   - Red flags e criteri di rivalutazione
   - Bibliografia con PMID e livello di evidenza

## Setup

```bash
# 1. Installa dipendenze
pip install requests anthropic

# 2. Configura API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Avvia il bot
python bot.py
```

## Utilizzo

**Modalità interattiva:**
```bash
python bot.py
```

**Modalità CLI (singola condizione):**
```bash
python bot.py "crociato anteriore operato terzo mese"
python bot.py "lesione muscolare bicipite femorale grado 2 Monaco"
python bot.py "tendinopatia rotulea"
python bot.py "distorsione caviglia grado 2"
```

## Output

Il bot genera due file:
- `output_[condizione]_[timestamp].md` — protocollo completo in Markdown
- `output_[condizione]_[timestamp]_evidence.json` — evidenze raw da PubMed

## Esempi di condizioni supportate

- Ricostruzione LCA (legamento crociato anteriore) — qualsiasi fase
- Lesioni muscolari (classificazione Monaco grado 1/2/3/4)
- Tendinopatie (rotulea, achillea, spalla)
- Distorsioni (caviglia, ginocchio)
- Lombalgia acuta/cronica
- Instabilità di spalla
- Qualsiasi condizione fisioterapica con letteratura PubMed

## Architettura

```
bot.py
├── gather_evidence()      # 6 query PubMed mirate per condizione
├── pubmed_search()        # E-utilities esearch API
├── pubmed_fetch_abstracts() # E-utilities efetch API
└── generate_protocol()    # Claude Sonnet 5 — sintesi evidence-based
```

## Requisiti

- Python 3.10+
- `requests`
- `anthropic`
- API key Anthropic (claude.ai/settings)
