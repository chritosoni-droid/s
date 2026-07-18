# FisioEvidenceBot v2

Bot per fisioterapisti che genera protocolli riabilitativi completi basati su:
- **Evidenze scientifiche PubMed** (systematic reviews, RCT, meta-analisi)
- **Libreria esercizi personalizzata** (205 esercizi dalle tue schede)
- **Claude Sonnet 5 AI** per la sintesi e la personalizzazione

---

## Struttura della sessione (5 fasi)

Ogni protocollo generato struttura le sessioni in 5 fasi evidence-based:

| Fase | Nome | Durata | Contenuto |
|---|---|---|---|
| 🔥 **1** | Riscaldamento dinamico | 10-15 min | Mobilizzazione, warm-up cardiovascolare, esercizi dinamici |
| 🧱 **2** | Isometria | 5-10 min | Contrazioni isometriche per riscaldare tendine/muscolo target |
| ⚡ **3** | Attivazione specifica | 10-15 min | Attivazione neuromuscolare basso carico dei muscoli target |
| 💪 **4** | Esercizi specifici | 20-30 min | Forza, propriocezione, BOSU, pliometria, sport-specifici |
| 🧘 **5** | Stretching / Defaticamento | 10 min | Stretching statico, rilascio miofasciale |

---

## Libreria esercizi (205 esercizi totali)

| Categoria | N° | Esempi |
|---|---|---|
| **BOSU** | 72 | Squat monopodalico su BOSU, Nordic curl su BOSU, Bridge su BOSU... |
| **Forza** | 66 | Hip thrust, Nordic hamstring curl, Pallof press, Copenhagen plank... |
| **Pliometria** | 46 | CMJ, Drop jump, Skater jump, Medicine ball slam... |
| **Mobilità** | 21 | Hip CARs, 90/90 hip switch, Sleeper stretch, Open book... |

Ogni esercizio è classificato per:
- Distretto anatomico (quadricipiti, ischiocrurali, glutei, core, spalla, ecc.)
- Tipo (attivazione, isometria, forza, propriocezione, pliometria, sport-specifico)
- Fase di sessione (1-5)
- Attrezzatura necessaria
- Difficoltà (1-5)

---

## Patologie supportate

Il bot gestisce **qualsiasi patologia fisioterapica** con letteratura su PubMed:

**Ginocchio:** LCA post-operatorio, lesioni meniscali, tendinopatia rotulea, sindrome femoro-rotulea, osteoartrite  
**Muscolare:** Lesioni ischiocrurale/quadricipite/adduttori (classificazione Monaco), contratture  
**Caviglia/Piede:** Distorsioni laterali (gradi 1-3), tendinopatia achillea, fascite plantare  
**Anca:** Sindrome da impingement, borsiti, lesioni labrum  
**Colonna:** Lombalgia acuta/cronica, ernia del disco, cervicalgia, scoliosi  
**Spalla:** Instabilità, impingement, lesioni cuffia dei rotatori, SLAP lesion  
**Gomito:** Epicondilite laterale/mediale, tendinopatia del tricipite  
**Multisistemiche:** Protocolli post-chirurgici, recupero atletico

---

## Setup

```bash
# 1. Installa dipendenze
pip install requests anthropic

# 2. Configura API key Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Avvia il bot
python bot.py
```

## Utilizzo

**Modalità interattiva:**
```bash
python bot.py
```

**Modalità CLI:**
```bash
python bot.py "crociato anteriore operato 3 mesi"
python bot.py "lesione muscolare bicipite femorale grado 2 Monaco"
python bot.py "tendinopatia achillea corridore"
python bot.py "distorsione caviglia grado 2 calcio"
python bot.py "lombalgia acuta"
python bot.py "epicondilite laterale tennista"
python bot.py "instabilità spalla post-lussazione"
```

## Output per ogni protocollo

1. `protocollo_[condizione]_[timestamp].md` — protocollo completo Markdown
2. `protocollo_[condizione]_[timestamp]_evidence.json` — evidenze raw PubMed

Il protocollo include:
- Overview clinico + timeline di recupero
- Sessioni strutturate in 5 fasi con ID esercizi dalla libreria
- Progressione settimanale con criteri di avanzamento misurabili
- RTP → RTT → RTS con criteri biometrici + funzionali + psicologici
- Red flags per rivalutazione medica
- Bibliografia con PMID, DOI e livello di evidenza (A/B/C)

---

## Architettura

```
FisioEvidenceBot v2
├── bot.py                   # Core del bot
├── exercise_library.json    # 205 esercizi dalle schede
├── esempio_crociato_3mesi.md  # Demo protocollo LCA
└── README.md
```

```
bot.py
├── load_library()           # Carica exercise_library.json
├── gather_evidence()        # 6 ricerche PubMed mirate
├── get_exercises_for_phase()# Filtra esercizi per fase/distretto
├── build_exercise_context() # Prepara contesto esercizi per Claude
└── generate_protocol()      # Claude Sonnet 5 — sintesi finale
```

## Requisiti

- Python 3.10+
- `pip install requests anthropic`
- API key Anthropic (claude.ai/settings)
- Accesso Internet a PubMed (eutils.ncbi.nlm.nih.gov)
