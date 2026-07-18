#!/usr/bin/env python3
"""
FisioEvidenceBot v2 — Protocolli riabilitativi evidence-based
Struttura sessione: Fase1-Riscaldamento | Fase2-Isometria | Fase3-Attivazione | Fase4-Esercizi | Fase5-Stretching
Libreria esercizi personalizzata + evidenze PubMed + Claude AI
"""

import os
import sys
import json
import time
import requests
import anthropic
from datetime import datetime
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Carica libreria esercizi
LIBRARY_PATH = Path(__file__).parent / "exercise_library.json"

def load_library() -> list[dict]:
    try:
        with open(LIBRARY_PATH, encoding="utf-8") as f:
            # Rimuove commenti JS-style (//) prima del parsing JSON
            lines = [l for l in f if not l.strip().startswith("//")]
            data = json.loads("".join(lines))
        return data.get("exercises", [])
    except Exception as e:
        print(f"⚠️  Libreria non trovata ({e}) — uso libreria vuota")
        return []

EXERCISES = load_library()

# ---------------------------------------------------------------------------
# PubMed helpers
# ---------------------------------------------------------------------------

def pubmed_search(query: str, max_results: int = 8, filters: str = "") -> list[str]:
    full_query = f"{query} {filters}".strip()
    params = {"db": "pubmed", "term": full_query, "retmax": max_results,
              "retmode": "json", "sort": "relevance"}
    r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def pubmed_fetch_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    import xml.etree.ElementTree as ET
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    r = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        title_el = article.find(".//ArticleTitle")
        abs_el = article.find(".//AbstractText")
        year_el = article.find(".//PubDate/Year")
        journal_el = article.find(".//Journal/Title")
        authors = article.findall(".//Author/LastName")
        abstract = "".join(abs_el.itertext()) if abs_el is not None else ""
        if not abstract:
            continue
        articles.append({
            "pmid":    pmid_el.text if pmid_el is not None else "?",
            "title":   "".join(title_el.itertext()) if title_el is not None else "N/A",
            "abstract": abstract[:1000],
            "year":    year_el.text if year_el is not None else "?",
            "journal": journal_el.text if journal_el is not None else "?",
            "author":  authors[0].text if authors else "?",
        })
    return articles


def gather_evidence(condition: str) -> dict[str, list[dict]]:
    """
    Ricerca massiva su PubMed: 15 query mirate, fino a 150+ articoli.
    Copre: systematic reviews, meta-analisi, RCT, linee guida, studi di coorte,
    struttura sessione, fasi riabilitative, isometria, neuromuscolare,
    propriocezione, pliometria, RTP/RTT/RTS, psicologia, imaging, prognosi.
    """
    print("\n🔍 Ricerca massiva PubMed in corso (15 query)...")

    searches = {
        # ── EVIDENZE DI PRIMO LIVELLO ─────────────────────────────
        "systematic_reviews": (
            f"{condition} rehabilitation",
            "(systematic review[pt] OR meta-analysis[pt])"
        ),
        "meta_analysis": (
            f"{condition} exercise treatment outcome",
            "(meta-analysis[pt])"
        ),
        "clinical_guidelines": (
            f"{condition} clinical practice guideline consensus",
            "(guideline[pt] OR practice guideline[pt] OR consensus development[pt])"
        ),
        "rct": (
            f"{condition} physiotherapy exercise randomized",
            "(randomized controlled trial[pt])"
        ),
        "rct_2": (
            f"{condition} rehabilitation protocol intervention",
            "(randomized controlled trial[pt])"
        ),

        # ── FASI E STRUTTURA RIABILITATIVA ────────────────────────
        "rehab_phases": (
            f"{condition} rehabilitation phases progression criteria timeline",
            ""
        ),
        "session_structure": (
            f"{condition} warm-up activation isometric rehabilitation session",
            ""
        ),
        "isometric_training": (
            f"{condition} isometric exercise tendon pain contraction",
            ""
        ),
        "neuromuscular": (
            f"{condition} neuromuscular training proprioception balance",
            ""
        ),

        # ── FORZA E CARICO ────────────────────────────────────────
        "strength_training": (
            f"{condition} strength training progressive overload quadriceps hamstring",
            "(randomized controlled trial[pt] OR cohort study[tw])"
        ),
        "eccentric_training": (
            f"{condition} eccentric exercise loading tendon muscle",
            ""
        ),
        "plyometric": (
            f"{condition} plyometric jump training explosive",
            ""
        ),

        # ── RETURN TO SPORT ───────────────────────────────────────
        "rtp_criteria": (
            f"{condition} return to sport play criteria functional testing",
            ""
        ),
        "rts_psychological": (
            f"{condition} return to sport psychological readiness kinesiophobia fear",
            ""
        ),

        # ── OUTCOME E PROGNOSI ────────────────────────────────────
        "functional_outcome": (
            f"{condition} functional outcome patient reported measures KOOS IKDC",
            "(cohort study[tw] OR prospective study[tw])"
        ),
        "prognosis_reinjury": (
            f"{condition} prognosis reinjury risk factors recurrence",
            ""
        ),
        "imaging_diagnosis": (
            f"{condition} MRI ultrasound diagnosis classification",
            ""
        ),
        "pain_management": (
            f"{condition} pain management analgesic cryotherapy TENS electrostimulation",
            ""
        ),
        "manual_therapy": (
            f"{condition} manual therapy mobilization massage soft tissue",
            "(randomized controlled trial[pt] OR systematic review[pt])"
        ),
    }

    evidence = {}
    total = 0
    for key, (query, filters) in searches.items():
        label = key.replace("_", " ").upper()
        print(f"  ↳ [{label}]...", end=" ", flush=True)
        try:
            pmids = pubmed_search(query, max_results=12, filters=filters)
            arts = pubmed_fetch_abstracts(pmids[:10])
            evidence[key] = arts
            total += len(arts)
            print(f"✓ {len(arts)} articoli")
        except Exception as e:
            print(f"errore ({e})")
            evidence[key] = []
        time.sleep(0.4)  # rispetta rate limit NCBI (3 req/sec)

    print(f"\n📚 Totale articoli PubMed recuperati: {total}")
    print(f"📊 Query eseguite: {len(searches)} | Copertura: SR, MA, RCT, linee guida, coorte")
    return evidence

# ---------------------------------------------------------------------------
# Filtro esercizi dalla libreria
# ---------------------------------------------------------------------------

def get_exercises_for_phase(phase: int, distretto: list[str] = None,
                             tipo_filter: list[str] = None, max_per_cat: int = 4) -> list[dict]:
    """Filtra esercizi per fase di sessione e distretto."""
    results = []
    for ex in EXERCISES:
        if phase not in ex.get("fase_sessione", []):
            continue
        if distretto:
            ex_dist = ex.get("distretto", "")
            if not any(d in ex_dist for d in distretto):
                continue
        if tipo_filter:
            ex_tipo = ex.get("tipo", "")
            if not any(t in ex_tipo for t in tipo_filter):
                continue
        results.append(ex)
    return results[:max_per_cat * 3]


def format_exercise_list(exercises: list[dict]) -> str:
    if not exercises:
        return "  (nessun esercizio disponibile in libreria per questa fase)"
    lines = []
    for ex in exercises:
        attr = ", ".join(ex.get("attrezzatura", [])) or "corpo libero"
        diff = "⭐" * ex.get("difficolta", 1)
        lines.append(f"  • [{ex['id']}] **{ex['name']}** — {attr} {diff}")
        if ex.get("note"):
            lines.append(f"    _{ex['note']}_")
    return "\n".join(lines)


def build_exercise_context(condition_keywords: list[str]) -> str:
    """Costruisce il contesto esercizi da passare a Claude."""
    sections = []

    # Fase 1 — Riscaldamento/Mobilità
    f1 = get_exercises_for_phase(1, max_per_cat=6)
    sections.append(f"### FASE 1 — RISCALDAMENTO (disponibili in libreria)\n{format_exercise_list(f1)}")

    # Fase 2 — Isometria
    f2 = get_exercises_for_phase(2, max_per_cat=5)
    sections.append(f"### FASE 2 — ISOMETRIA (disponibili in libreria)\n{format_exercise_list(f2)}")

    # Fase 3 — Attivazione specifica
    f3 = get_exercises_for_phase(3, max_per_cat=5)
    sections.append(f"### FASE 3 — ATTIVAZIONE SPECIFICA (disponibili in libreria)\n{format_exercise_list(f3)}")

    # Fase 4 — Esercizi specifici (filtra per distretto rilevante)
    f4 = get_exercises_for_phase(4, max_per_cat=8)
    sections.append(f"### FASE 4 — ESERCIZI SPECIFICI (disponibili in libreria)\n{format_exercise_list(f4)}")

    # Fase 5 — Stretching
    f5_mob = [ex for ex in EXERCISES if "stretching" in ex.get("tipo", "") or ex.get("fase_sessione") == [5]
              or (5 in ex.get("fase_sessione", []))]
    f5_mob += [ex for ex in EXERCISES if "stretching" in ex.get("tipo", "") and ex not in f5_mob]
    sections.append(f"### FASE 5 — STRETCHING/DEFATICAMENTO (disponibili in libreria)\n{format_exercise_list(f5_mob[:10])}")

    return "\n\n".join(sections)

# ---------------------------------------------------------------------------
# Generazione protocollo con Claude
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Sei un fisioterapista esperto con PhD in scienze riabilitative e medicina dello sport,
con specializzazione in fisioterapia muscoloscheletrica e sportiva.

Generi protocolli riabilitativi per QUALSIASI patologia fisioterapica, basati
ESCLUSIVAMENTE sulle evidenze scientifiche PubMed fornite (systematic reviews,
meta-analisi, RCT, linee guida, studi di coorte).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRUTTURA OBBLIGATORIA DI OGNI SESSIONE (5 fasi):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 FASE 1 — RISCALDAMENTO DINAMICO (10-15 min)
   Obiettivo: aumentare temperatura muscolare, perfusione, ROM articolare.
   Contenuto: mobilizzazione articolare dinamica, esercizi di attivazione generale.
   Scegli da: categoria "mobilita" della libreria.
   Evidenza: cita PMID che supporta il warm-up pre-riabilitazione.

🧱 FASE 2 — ISOMETRIA (5-10 min)
   Obiettivo: riscaldare il tendine/muscolo target, ridurre il dolore, attivare il SNC.
   Contenuto: contrazioni isometriche a medio-alta intensità (60-80% MVC), 5×45s.
   Scegli da: tipo "isometria" nella libreria (wall sit, Spanish squat, BOSU isometrico).
   Evidenza scientifica chiave: l'isometria riduce il dolore tendineo (Rio et al.) —
   cita PMID specifico se presente nella lista fornita.

⚡ FASE 3 — ATTIVAZIONE SPECIFICA (10-15 min)
   Obiettivo: attivazione neuromuscolare selettiva dei muscoli target a basso carico.
   Contenuto: esercizi di attivazione con elastici, corpo libero, BOSU a bassa intensità.
   Scegli da: tipo "attivazione" o "attivazione_*" nella libreria.
   Evidenza: cita PMID che supporta l'attivazione pre-esercizio.

💪 FASE 4 — ESERCIZI SPECIFICI (20-30 min)
   Obiettivo: rinforzo muscolare, propriocezione, controllo motorio, sport-specificità.
   Contenuto: forza progressiva (CKC e OKC), BOSU, pliometria (solo nelle fasi avanzate).
   Progressione evidence-based: da bassa a alta intensità, da bilaterale a monolaterale,
   da stabile a instabile, da controllato a reattivo.
   Scegli da: tipo "forza*", "propriocezione*", "sport_specifico", "pliometria*".
   Per OGNI esercizio: cita PMID di supporto e livello di evidenza.

🧘 FASE 5 — STRETCHING E DEFATICAMENTO (10 min)
   Obiettivo: riduzione DOMS, ripristino lunghezza muscolare, recupero.
   Contenuto: stretching statico 30-60s per gruppo muscolare lavorato.
   Scegli da: tipo "stretching_statico" nella libreria.
   Evidenza: indica se lo stretching post-esercizio è supportato (cita PMID).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGOLE FERREE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. USA TUTTE LE EVIDENZE FORNITE — non ignorare nessun articolo, sintetizzali tutti.
2. Ogni raccomandazione DEVE citare PMID + livello evidenza (A/B/C).
   A = systematic review / meta-analisi
   B = RCT / studio prospettico
   C = coorte retrospettiva / case series / consenso esperto
3. Gerarchia evidenze: privilegia sempre A > B > C.
4. Evidenze CONTRADDITTORIE: segnalale esplicitamente e spiega quale prevale e perché.
5. OGNI esercizio prescritto deve avere ID dalla libreria fornita.
   Se non disponibile in libreria: [NON IN LIBRERIA — aggiungi alle schede].
6. Criteri di progressione MISURABILI obbligatori:
   - Dolore: VAS (es. VAS ≤2/10 per avanzare)
   - ROM: in gradi (es. flessione ≥120°)
   - Forza: LSI % (es. LSI ≥85% per RTP)
   - Forza relativa: H:Q ratio (es. ≥0.60 per RTS)
   - Funzionale: hop test LSI (es. ≥90% per RTS)
   - Psicologico: ACL-RSI (es. ≥65 per RTS), TSK (es. <37)
7. Timeline: indica settimane/mesi con obiettivi SPECIFICI per ogni fase.
8. Include SEMPRE sezioni: RTP → RTT → RTS con criteri completi.
9. RED FLAGS: segnali che richiedono stop e rivalutazione medico-chirurgica.
10. Segnala gap nelle evidenze e raccomandazioni basate su consenso clinico.
11. LINGUA: italiano tecnico-clinico. Usa tabelle per parametri e progressioni.
12. BIBLIOGRAFIA COMPLETA al fondo: PMID | DOI | Autori | Anno | Tipo studio | Livello.
"""

USER_TEMPLATE = """\
CONDIZIONE PAZIENTE: {condition}
DATA RICERCA: {date}

{phase_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVIDENZE SCIENTIFICHE DA PUBMED — {n_articles} ARTICOLI TOTALI
(systematic reviews, meta-analisi, RCT, linee guida, coorti)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{evidence_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LIBRERIA ESERCIZI PERSONALIZZATA (205 esercizi disponibili)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{exercise_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RICHIESTA: PROTOCOLLO RIABILITATIVO COMPLETO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usa TUTTE le evidenze sopra per costruire il protocollo più completo possibile.
Non ignorare nessun articolo: ogni PMID deve contribuire a una raccomandazione.

STRUTTURA OBBLIGATORIA:

---

## 0. FASE ATTUALE DEL PAZIENTE ⏱️

> **Questa sezione va compilata PRIMA di tutto il resto. È il punto di partenza del protocollo.**

### Dove siamo ora
- **Fase riabilitativa attuale:** [nome fase con settimane/mesi]
- **Timing dall'inizio:** [settimane/mesi]
- **Obiettivi SPECIFICI di questa fase:** lista puntata con valori misurabili
- **Test/misure attesi in questa fase:** VAS, ROM, LSI, hop test — con soglie numericheì

### Cosa è già stato fatto (fasi precedenti)
Breve sintesi evidence-based di ciò che dovrebbe essere stato completato prima di questa fase.

### Sessione tipo QUESTA SETTIMANA (5 fasi)
La sessione dettagliata nella Sezione 3 deve rispecchiare ESATTAMENTE questa fase.

### Tabella timeline globale — con indicazione "◀ SIAMO QUI"

| Settimane | Fase | Obiettivi | Criteri avanzamento | Stato |
|---|---|---|---|---|
| 0-2 | Fase 1 — Precoce | ... | ... | ✅ Completata / 🔴 FASE ATTUALE / ⬜ Futura |
| 3-6 | Fase 2 — Sub-Acuta | ... | ... | ... |
| 7-12 | Fase 3 — Rinforzo | ... | ... | ... |
| 13-20 | Fase 4 — Avanzata | ... | ... | ... |
| 20+ | Fase 5 — RTS | ... | ... | ... |

### Obiettivi settimana per settimana (FASE ATTUALE + prossime 4 settimane)

| Settimana | Obiettivi specifici | Esercizi chiave (ID) | Parametri di carico | Criteri go/no-go |
|---|---|---|---|---|

---

## 1. PANORAMICA CLINICA

### Diagnosi e anatomia
- Strutture coinvolte, meccanismo lesionale, classificazione evidence-based
- Citare la classificazione più accreditata (PMID)

### Epidemiologia e fattori di rischio
- Incidenza, prevalenza, fattori predittivi (citare PMID)

### Timeline globale di recupero
- Tabella: Settimane | Fase | Obiettivi principali | Outcome attesi

---

## 2. VALUTAZIONE INIZIALE E RIVALUTAZIONI

### Strumenti di valutazione validati
| Strumento | Misura | Valore baseline | Soglia per avanzamento | PMID |
|---|---|---|---|---|

### Test funzionali
- Lista test con soglie numeriche evidence-based (citare PMID per ogni soglia)

---

## 3. SESSIONE TIPO — 5 FASI (con esercizi dalla libreria)

### 🔥 FASE 1 — RISCALDAMENTO DINAMICO (10-15 min)
Razionale scientifico: [cita PMID]
| ID Libreria | Esercizio | Durata/Serie | Note tecniche |
|---|---|---|---|

### 🧱 FASE 2 — ISOMETRIA (5-10 min)
Razionale scientifico: [cita PMID — soprattutto per tendinopatie]
| ID Libreria | Esercizio | Angolo | Durata×Set | Intensità | Note |
|---|---|---|---|---|---|

### ⚡ FASE 3 — ATTIVAZIONE SPECIFICA (10-15 min)
Razionale scientifico: [cita PMID]
| ID Libreria | Esercizio | Serie×Rip | Recupero | Note |
|---|---|---|---|---|

### 💪 FASE 4 — ESERCIZI SPECIFICI
Divisi per macro-fase riabilitativa:

#### FASE PRECOCE (settimane specifiche da evidenza)
| ID Libreria | Esercizio | Serie×Rip | Carico | Evidenza PMID | Livello |
|---|---|---|---|---|---|

#### FASE INTERMEDIA
| ID Libreria | Esercizio | Serie×Rip | Carico | Evidenza PMID | Livello |
|---|---|---|---|---|---|

#### FASE AVANZATA / PRE-SPORT
| ID Libreria | Esercizio | Serie×Rip | Carico | Evidenza PMID | Livello |
|---|---|---|---|---|---|

### 🧘 FASE 5 — STRETCHING E DEFATICAMENTO (10 min)
| ID Libreria | Esercizio | Durata | Muscolo target | Note |
|---|---|---|---|---|

---

## 4. PROGRESSIONE SETTIMANA PER SETTIMANA

| Settimane | Fase | Obiettivi | Esercizi chiave (ID) | Criteri di avanzamento | Frequenza |
|---|---|---|---|---|---|

---

## 5. TERAPIA FISICA ADIUVANTE
(electrostimolazione, crioterapia, terapia manuale, taping — solo se supportata da PMID)
| Trattamento | Parametri | Evidenza PMID | Livello |
|---|---|---|---|

---

## 6. GESTIONE DEL DOLORE
(farmaci OTC, RICE/PEACE&LOVE, scarico) — citare linee guida (PMID)

---

## 7. RTP — RETURN TO PLAY
Criteri con soglie numeriche evidence-based:
| Dominio | Test | Soglia minima | PMID |
|---|---|---|---|

---

## 8. RTT — RETURN TO TRAINING
- Progressione allenamento: % intensità per settimana
- Monitoraggio carico (ACWR raccomandata <1.5)

---

## 9. RTS — RETURN TO SPORT (clearance definitiva)
| Dominio | Test | Soglia | PMID |
|---|---|---|---|
| Biometrico | LSI quad / ischio | ≥90% | |
| Forza relativa | H:Q ratio | ≥0.60 | |
| Hop test | Single/Triple/Crossover/6m | LSI ≥90% | |
| Psicologico | ACL-RSI / TSK | ≥65 / <37 | |
| Tempo minimo | — | da evidenza | |

---

## 10. RED FLAGS ⚠️
| Segnale | Possibile causa | Azione |
|---|---|---|

---

## 11. GAP NELLE EVIDENZE
Aree dove le evidenze sono limitate o contraddittorie.

---

## 12. BIBLIOGRAFIA COMPLETA

| # | PMID | DOI | Primo autore | Anno | Rivista | Tipo studio | Livello evidenza | Raccomandazione |
|---|---|---|---|---|---|---|---|---|

---

IMPORTANTE: ogni cella "Evidenza PMID" nella tabella DEVE contenere un PMID reale
dalla lista fornita. Non inventare PMID. Se non c'è evidenza diretta, scrivi
"Consenso clinico (C)" e spiega il razionale.
"""


def parse_phase_context(condition: str) -> dict:
    """
    Estrae il contesto di fase/timing dalla stringa condizione.
    Ritorna: {weeks, months, phase_name, phase_number, post_op, acute, notes}
    """
    import re
    c = condition.lower()

    weeks = None
    months = None
    days = None
    phase_number = None
    post_op = any(w in c for w in ["operato", "intervento", "chirurgi", "post-op", "postop", "artroscopia"])
    acute = any(w in c for w in ["acuta", "acuto", "recente", "fresca", "immediata"])

    # Estrai giorni — supporta "14 giorni" E "giorno 14"
    # Rimuove temporaneamente il pattern del grado per evitare false catture
    c_no_grade = re.sub(r'[1234]\s*(?:°\s*)?grado|(?:grado|grade)\s*[1234]', '', c)
    m = re.search(r'(\d{1,3})\s*(?:giorn[oi]|day)', c_no_grade)
    if not m:
        m = re.search(r'(?:giorn[oi]|day)\s*(\d{1,3})', c_no_grade)
    if m:
        days = int(m.group(1))
        weeks = days / 7  # float per confronti

    # Estrai settimane
    m = re.search(r'(\d+)\s*(?:settiman[ae]|week)', c)
    if m:
        weeks = int(m.group(1))

    # Estrai mesi
    m = re.search(r'(\d+)\s*(?:mes[ie]|month)', c)
    if m:
        months = int(m.group(1))

    # Converti mesi → settimane se noto
    if months and not weeks:
        weeks = months * 4

    # Rileva lesione muscolare (Monaco / gradi) — estrai PRIMA di analizzare giorni
    muscular_injury = any(w in c for w in ["lesione", "strappo", "distrazione", "rottura muscol"])
    monaco_grade = None
    # "grado 2", "grade 2"
    m = re.search(r'(?:grado|grade|gr\.?)\s*([1234])', c)
    if m:
        monaco_grade = int(m.group(1))
    if not monaco_grade:
        # "2grado", "2° grado" (numero PRIMA di grado)
        m = re.search(r'([1234])\s*(?:°\s*)?grado', c)
        if m:
            monaco_grade = int(m.group(1))
    if not monaco_grade:
        if "1a" in c or "1b" in c:
            monaco_grade = 1
        elif "2a" in c or "2b" in c or "2c" in c:
            monaco_grade = 2
        elif "3a" in c or "3b" in c:
            monaco_grade = 3

    if muscular_injury and monaco_grade:
        # Timeline Monaco: G1~1-2sett, G2~3-6sett, G3~6-12sett, G4→chirurgia
        day = days if days else (weeks * 7 if weeks else None)
        if monaco_grade == 1:
            total_days = 10
            if day is None or day <= 3:
                phase_number = 1
                phase_name = "Lesione Monaco G1 — Fase Acuta (giorni 1-3)"
                objectives_now = "PEACE&LOVE: protezione 24-48h, controllo edema/ematoma, ROM dolore-libero, deambulazione normale. Crioterapia 15 min × 4-6/die."
                objectives_next = "Corsa leggera (>giorni 5), forza piena (>giorno 7-10), RTP (giorno 10-14)"
            else:
                phase_number = 2
                phase_name = "Lesione Monaco G1 — Fase Sub-Acuta/Rientro (giorni 4-10)"
                objectives_now = "Rinforzo muscolare progressivo, corsa in linea, elastici, ritorno alle sessioni parziali"
                objectives_next = "RTP: assenza dolore, LSI forza ≥90%, corsa e cambi direzione senza dolore"
        elif monaco_grade == 2:
            total_days = 35
            if day is None or day <= 7:
                phase_number = 1
                phase_name = "Lesione Monaco G2 — Fase Acuta (giorni 1-7)"
                objectives_now = "PEACE&LOVE, protezione relativa 48-72h, mobilità ROM dolore-guidata, scarico parziale se necessario. VAS ≤4/10 a riposo. Crioterapia, compressione, elevazione."
                objectives_next = "Deambulazione normale senza dolore, ROM completo, inizio attivazione muscolare attiva (>giorno 7)"
            elif day <= 14:
                phase_number = 2
                phase_name = "Lesione Monaco G2 — Fase Sub-Acuta (giorni 7-14)"
                objectives_now = "Attivazione muscolare attiva progressiva, isometria a bassa intensità, ROM completo senza dolore, corsa leggera in linea (se VAS ≤2). Recupero ciclo del passo normale."
                objectives_next = "Corsa progressiva senza dolore, inizio escentrico (giorno 14-21), rinforzo funzionale"
            elif day <= 21:
                phase_number = 3
                phase_name = "Lesione Monaco G2 — Fase Rinforzo Iniziale (giorni 14-21)"
                objectives_now = "Esercizi eccentrici progressivi (Nordic curl, RDL), corsa in linea e progressiva, BOSU e propriocezione, carico sport-specifico iniziale. Obiettivo: forza LSI ≥70%."
                objectives_next = "Cambio direzione, gesti sport-specifici, VAS 0/10 durante tutti gli esercizi, LSI ≥80%"
            else:
                phase_number = 4
                phase_name = "Lesione Monaco G2 — Fase Avanzata/Pre-RTP (giorni 21-35)"
                objectives_now = "Rinforzo avanzato eccentrico/concentrico, sprint, cambi direzione, gesti sport-specifici. LSI forza ≥85%. Test funzionali senza dolore."
                objectives_next = "RTP: assenza dolore, LSI ≥90%, sprint massimale, Askling H-test negativo, Athletic Body Test"
        elif monaco_grade == 3:
            total_days = 75
            if day is None or day <= 7:
                phase_number = 1
                phase_name = "Lesione Monaco G3 — Fase Acuta (giorni 1-7)"
                objectives_now = "PEACE&LOVE rigoroso, scarico completo se necessario, immobilizzazione parziale (ortesi), controllo ecografico a 48-72h, valutare consulto chirurgico. Crioterapia, FANS solo se necessario."
                objectives_next = "Deambulazione senza dolore, ROM passivo completo, decisione conservativa vs chirurgica"
            elif day <= 21:
                phase_number = 2
                phase_name = "Lesione Monaco G3 — Fase Sub-Acuta (giorni 7-21)"
                objectives_now = "ROM progressivo attivo, isometria submassimale, idroterapia (se disponibile), attivazione muscolare protetta. Ecografia di controllo settimana 2."
                objectives_next = "Corsa leggera (giorno 21-28), forza funzionale CKC, inizio eccentrico (giorno 28+)"
            elif day <= 42:
                phase_number = 3
                phase_name = "Lesione Monaco G3 — Fase Rinforzo (giorni 21-42)"
                objectives_now = "Escentrico progressivo, nordic curl, BOSU, propriocezione, corsa progressiva (linea → curve → sprint al 70%). LSI forza target ≥70%."
                objectives_next = "Sprint, cambi direzione, gesti sport-specifici, LSI ≥80-85%"
            else:
                phase_number = 4
                phase_name = "Lesione Monaco G3 — Fase Avanzata/Pre-RTP (giorni 42-75)"
                objectives_now = "Rinforzo massimale, plyometria, gesti sport-specifici, sprint massimale. Target: LSI ≥90%, Askling H-test, test sport-specifici."
                objectives_next = "RTP con clearance completa: LSI ≥90%, assenza dolore, fiducia psicologica (ACSI-28)"
        else:
            phase_number = None
            phase_name = "Lesione Monaco G4 — Valutazione Chirurgica"
            objectives_now = "Consulto chirurgico urgente. Protocollo riabilitativo post-chirurgico da definire dopo l'intervento."
            objectives_next = "Post-op: protocollo riabilitativo specifico per tipo di intervento"

        return {
            "weeks": weeks,
            "months": months,
            "days": days,
            "phase_number": phase_number,
            "phase_name": phase_name,
            "post_op": post_op,
            "acute": acute,
            "monaco_grade": monaco_grade,
            "objectives_now": objectives_now,
            "objectives_next": objectives_next,
        }

    # Determina fase riabilitativa in base a timing e contesto
    if post_op:
        if weeks is None:
            phase_number = 1
            phase_name = "Fase Precoce Post-Operatoria (sett. 0-2)"
            objectives_now = "Controllo dell'edema, recupero ROM passivo, attivazione muscolare precoce, protezione dell'innesto/struttura"
            objectives_next = "Deambulazione autonoma, ROM attivo 0-90°, contrazione quadricipite attiva"
        elif weeks <= 2:
            phase_number = 1
            phase_name = "Fase 1 — Precoce Post-Operatoria (sett. 0-2)"
            objectives_now = "Controllo edema/dolore, recupero ROM passivo 0-90°, attivazione VMO e glutei, deambulazione con ausili"
            objectives_next = "ROM attivo 0-120°, estensione completa, forza quad >50% controlaterale, deambulazione autonoma"
        elif weeks <= 6:
            phase_number = 2
            phase_name = "Fase 2 — Sub-Acuta / Recupero ROM (sett. 3-6)"
            objectives_now = "Recupero ROM completo, rinforzo progressivo quadricipiti/ischio/glutei in CKC, propriocezione di base, ciclo del passo normale"
            objectives_next = "ROM completo, LSI forza ≥60%, single leg balance >30s, inizio corsa in linea"
        elif weeks <= 12:
            phase_number = 3
            phase_name = "Fase 3 — Rinforzo Muscolare (sett. 7-12)"
            objectives_now = "Rinforzo bilaterale e monolaterale progressivo, BOSU e propriocezione avanzata, inizio corsa progressiva, controllo motorio"
            objectives_next = "LSI forza ≥70-75%, single-leg squat con buon controllo, corsa continua 20 min"
        elif weeks <= 20:
            phase_number = 4
            phase_name = "Fase 4 — Forza Avanzata e Reintroduzione Sport (sett. 13-20)"
            objectives_now = "Rinforzo pesistico progressivo, pliometria bilaterale e monolaterale, gesti sport-specifici, RTP training"
            objectives_next = "LSI ≥85%, hop test LSI ≥85%, corsa con cambi direzione, ACL-RSI ≥65"
        else:
            phase_number = 5
            phase_name = "Fase 5 — Pre-Sport / RTS (sett. 20+)"
            objectives_now = "Test di clearance per RTS: hop test LSI ≥90%, LSI forza ≥90%, H:Q ≥0.60, ACL-RSI ≥65, TSK <37"
            objectives_next = "Ritorno al gioco con piena fiducia e prestazione atletica pre-lesione"
    elif acute:
        phase_number = 1
        phase_name = "Fase Acuta (0-72h) / Sub-Acuta (settimana 1-2)"
        objectives_now = "Controllo infiammazione (PEACE&LOVE), riduzione dolore e gonfiore, protezione, recupero ROM passivo"
        objectives_next = "Carico progressivo tollerato, deambulazione normale, VAS ≤3/10 a riposo"
    elif weeks and weeks <= 4:
        phase_number = 1
        phase_name = f"Fase Precoce (sett. {weeks})"
        objectives_now = "Riduzione dolore e infiammazione, recupero ROM, attivazione muscolare protetta, scarico progressivo"
        objectives_next = "Carico completo tollerato, ROM funzionale, forza >60% controlaterale"
    elif weeks and weeks <= 8:
        phase_number = 2
        phase_name = f"Fase Sub-Acuta / Rinforzo Iniziale (sett. {weeks})"
        objectives_now = "Rinforzo muscolare progressivo, propriocezione, riduzione kinesiofobia, ritorno alle ADL complete"
        objectives_next = "Forza LSI ≥70%, equilibrio monolaterale stabile, inizio sport-specifico"
    elif weeks and weeks <= 16:
        phase_number = 3
        phase_name = f"Fase Avanzata (sett. {weeks})"
        objectives_now = "Forza avanzata (eccentric/plyometric loading), sport-specificity, RTP progressivo"
        objectives_next = "LSI ≥85%, test funzionali superati, clearance RTS"
    else:
        phase_number = None
        phase_name = "Fase non specificata — protocollo progressivo completo"
        objectives_now = "Valutazione baseline → obiettivi progressivi per ogni fase"
        objectives_next = "Ritorno sport con piena funzione"

    return {
        "weeks": weeks,
        "months": months,
        "days": days if 'days' in dir() else None,
        "phase_number": phase_number,
        "phase_name": phase_name,
        "post_op": post_op,
        "acute": acute,
        "monaco_grade": None,
        "objectives_now": objectives_now,
        "objectives_next": objectives_next,
    }


def build_evidence_text(evidence: dict) -> str:
    sections = []
    for section, articles in evidence.items():
        if not articles:
            continue
        header = section.replace("_", " ").upper()
        lines = [f"### {header}"]
        for a in articles:
            lines.append(
                f"- [{a['year']}] {a['author']} et al. — {a.get('journal','?')}\n"
                f"  PMID:{a['pmid']} | {a['title']}\n"
                f"  {a['abstract'][:600]}"
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def generate_protocol(condition: str, evidence: dict) -> str:
    if not ANTHROPIC_API_KEY:
        return (
            "❌ ANTHROPIC_API_KEY non configurata.\n"
            "Esegui: export ANTHROPIC_API_KEY='sk-ant-...'\n"
            "Poi rilancia il bot."
        )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Estrai keywords dalla condizione per filtrare esercizi rilevanti
    keywords = condition.lower().split()
    exercise_context = build_exercise_context(keywords)
    evidence_text = build_evidence_text(evidence)
    phase_ctx = parse_phase_context(condition)

    # Costruisce il blocco fase-attuale da iniettare nel prompt
    phase_block = f"""\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️  FASE ATTUALE DEL PAZIENTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Timing indicato: {f"settimana {phase_ctx['weeks']}" if phase_ctx['weeks'] else f"{phase_ctx['months']} mesi" if phase_ctx['months'] else "non specificato"}
Fase riabilitativa rilevata: {phase_ctx['phase_name']}
Post-operatorio: {"SÌ" if phase_ctx['post_op'] else "NO"}
Fase acuta: {"SÌ" if phase_ctx['acute'] else "NO"}

🎯 OBIETTIVI SPECIFICI PER QUESTA FASE:
{phase_ctx['objectives_now']}

⏭️ OBIETTIVI FASE SUCCESSIVA (criteri di avanzamento):
{phase_ctx['objectives_next']}

ISTRUZIONE CRITICA: il protocollo deve essere centrato sulla fase attuale indicata sopra.
- Indica con precisione cosa si FA in questa settimana/fase specifica
- Indica cosa è già stato fatto nelle fasi precedenti (non riprescriverlo come attivo)
- Indica cosa viene dopo con timeline precisa (settimane) e criteri misurabili
- La sessione tipo deve essere quella appropriata ALLA FASE ATTUALE
- La tabella progressione deve evidenziare chiaramente DOVE siamo ADESSO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    n_articles = sum(len(v) for v in evidence.values())
    user_msg = USER_TEMPLATE.format(
        condition=condition,
        phase_block=phase_block,
        date=datetime.now().strftime("%B %Y"),
        evidence_text=evidence_text,
        exercise_context=exercise_context,
        n_articles=n_articles,
    )

    print("\n🧠 Generazione protocollo con Claude (claude-sonnet-5)...")

    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return msg.content[0].text

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_output(condition: str, protocol: str, evidence: dict) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe = "".join(c if c.isalnum() else "_" for c in condition)[:40]
    base = f"protocollo_{safe}_{timestamp}"

    md_path = f"{base}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Protocollo Riabilitativo — {condition}\n")
        f.write(f"*Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')} — FisioEvidenceBot v2*\n\n")
        f.write(protocol)

    json_path = f"{base}_evidence.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"condition": condition, "evidence": evidence}, f, ensure_ascii=False, indent=2)

    return md_path


def banner():
    n_ex = len(EXERCISES)
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║       FisioEvidenceBot v2 — Riabilitazione Evidence-Based        ║
║    PubMed + Claude Sonnet 5 + Libreria {n_ex} esercizi personali    ║
╠══════════════════════════════════════════════════════════════════╣
║  Struttura sessione: Riscaldamento → Isometria → Attivazione     ║
║                      → Esercizi Specifici → Stretching           ║
╚══════════════════════════════════════════════════════════════════╝
""")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(condition: str):
    banner()
    print(f"📋 Condizione: {condition}")

    ctx = parse_phase_context(condition)
    print(f"⏱️  Fase rilevata: {ctx['phase_name']}")
    if ctx['weeks']:
        print(f"   Timing: settimana {ctx['weeks']}")
    print(f"   Obiettivi attuali: {ctx['objectives_now'][:100]}...")

    evidence = gather_evidence(condition)
    protocol = generate_protocol(condition, evidence)

    print("\n" + "═" * 70)
    print(protocol)
    print("═" * 70)

    path = save_output(condition, protocol, evidence)
    print(f"\n✅ Salvato: {path}")


def interactive():
    banner()
    print("Modalità interattiva — 'exit' per uscire\n")
    print("Esempi di condizioni:")
    print("  • crociato anteriore operato 3 mesi")
    print("  • lesione muscolare bicipite femorale grado 2 Monaco")
    print("  • tendinopatia rotulea")
    print("  • distorsione caviglia grado 2")
    print("  • lombalgia acuta")
    print("  • instabilità di spalla post-lussazione\n")

    while True:
        try:
            condition = input("🏥 Condizione paziente: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nUscita.")
            break
        if not condition:
            continue
        if condition.lower() in ("exit", "quit", "esci"):
            break
        run(condition)
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(" ".join(sys.argv[1:]))
    else:
        interactive()
