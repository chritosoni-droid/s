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
    """6 ricerche PubMed mirate per la condizione."""
    print("\n🔍 Ricerca PubMed in corso...")
    searches = {
        "systematic_reviews": (f"{condition} rehabilitation", "(systematic review[pt] OR meta-analysis[pt])"),
        "rct":                (f"{condition} exercise therapy treatment", "(randomized controlled trial[pt])"),
        "session_structure":  (f"{condition} warm-up isometric activation protocol", ""),
        "rtp_rts":            (f"{condition} return to sport return to play criteria", ""),
        "load_management":    (f"{condition} progressive loading neuromuscular", ""),
        "outcome_measures":   (f"{condition} functional outcome prognosis", "(cohort study[tw] OR clinical trial[pt])"),
    }
    evidence = {}
    total = 0
    for key, (query, filters) in searches.items():
        label = key.replace("_", " ").upper()
        print(f"  ↳ [{label}]...", end=" ", flush=True)
        try:
            pmids = pubmed_search(query, max_results=8, filters=filters)
            arts = pubmed_fetch_abstracts(pmids[:6])
            evidence[key] = arts
            total += len(arts)
            print(f"{len(arts)} articoli")
        except Exception as e:
            print(f"errore ({e})")
            evidence[key] = []
        time.sleep(0.35)
    print(f"\n📚 Totale: {total} articoli")
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
Sei un fisioterapista esperto con PhD in scienze riabilitative e medicina dello sport.
Generi protocolli riabilitativi per QUALSIASI patologia fisioterapica, basati ESCLUSIVAMENTE
sulle evidenze scientifiche PubMed fornite.

STRUTTURA OBBLIGATORIA DI OGNI SESSIONE (5 fasi):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 FASE 1 — RISCALDAMENTO DINAMICO (10-15 min)
   Mobilizzazione articolare, warm-up cardiovascolare leggero, esercizi dinamici.
   Scegli da: esercizi mobilità (categoria "mobilita") della libreria.

🧱 FASE 2 — ISOMETRIA (5-10 min)
   Contrazioni isometriche per riscaldare il tendine/muscolo target e attivare il sistema nervoso.
   Scegli da: esercizi con tipo "isometria" o "isometria_*" della libreria.
   (Fondamentale per tendini, post-infiammazione, fase acuta avanzata)

⚡ FASE 3 — ATTIVAZIONE SPECIFICA (10-15 min)
   Attivazione neuromuscolare dei muscoli target con esercizi a basso carico.
   Scegli da: esercizi con tipo "attivazione" o "attivazione_*" della libreria.

💪 FASE 4 — ESERCIZI SPECIFICI (20-30 min)
   Esercizi principali: forza, propriocezione, sport-specifici. Progressione evidence-based.
   Scegli da: esercizi con tipo "forza*", "propriocezione*", "sport_specifico", "pliometria*".

🧘 FASE 5 — STRETCHING / DEFATICAMENTO (10 min)
   Stretching statico dei muscoli lavorati, rilascio miofasciale.
   Scegli da: esercizi con tipo "stretching_statico" della libreria.

REGOLE FERREE:
1. OGNI esercizio prescritto deve essere preso dalla LIBRERIA FORNITA (citare l'ID).
   Se l'esercizio perfetto non è in libreria, indicarlo come [NON IN LIBRERIA].
2. Ogni raccomandazione deve citare il PMID della fonte PubMed e il livello di evidenza (A/B/C).
3. Gerarchia: systematic review/meta-analisi (A) > RCT (B) > coorte/esperto (C).
4. Criteri di progressione MISURABILI: VAS, ROM in gradi, LSI %, H:Q ratio, tempi.
5. Include SEMPRE: timeline riabilitativa + RTP + RTT + RTS con criteri.
6. Per ogni fase indica: serie × ripetizioni × recupero OPPURE durata × set.
7. Rispondi in ITALIANO tecnico-clinico. Usa tabelle e liste per la leggibilità.
8. Segnala RED FLAGS per rivalutazione medica.
9. Include bibliografia con PMID e DOI al fondo.
"""

USER_TEMPLATE = """\
CONDIZIONE PAZIENTE: {condition}

━━━ EVIDENZE SCIENTIFICHE DA PUBMED ({date}) ━━━
{evidence_text}

━━━ LIBRERIA ESERCIZI DISPONIBILI ━━━
{exercise_context}

━━━ RICHIESTA ━━━
Genera un PROTOCOLLO RIABILITATIVO COMPLETO per la condizione specificata.

STRUTTURA RICHIESTA:

## OVERVIEW CLINICO
- Diagnosi, anatomia coinvolta, classificazione (se applicabile)
- Timeline complessiva di recupero evidence-based
- Obiettivi per ogni macro-fase

## STRUTTURA DELLA SESSIONE TIPO (5 fasi)

### 🔥 FASE 1 — RISCALDAMENTO DINAMICO
Per ogni esercizio: [ID_LIBRERIA] Nome | Serie×Rip o Durata | Note tecniche

### 🧱 FASE 2 — ISOMETRIA
Per ogni esercizio: [ID_LIBRERIA] Nome | Angolo | Durata hold | Set | Note

### ⚡ FASE 3 — ATTIVAZIONE SPECIFICA
Per ogni esercizio: [ID_LIBRERIA] Nome | Serie×Rip | Note tecniche

### 💪 FASE 4 — ESERCIZI SPECIFICI
Divisi per SETTIMANE/FASI di recupero con progressione.
Per ogni esercizio: [ID_LIBRERIA] Nome | Serie×Rip×Carico | Note | Evidenza (PMID)

### 🧘 FASE 5 — STRETCHING E DEFATICAMENTO
Per ogni esercizio: [ID_LIBRERIA] Nome | Durata | Note

## PROGRESSIONE TEMPORALE
Tabella: Settimane | Fase | Obiettivi | Esercizi chiave | Criteri di avanzamento

## CRITERI RTP / RTT / RTS
- Return to Play: criteri misurabili
- Return to Training: criteri misurabili
- Return to Sport: criteri biometrici + funzionali + psicologici

## RED FLAGS ⚠️
Segnali che richiedono stop e rivalutazione medica.

## BIBLIOGRAFIA
PMID | DOI | Autori | Anno | Livello evidenza

Per ogni esercizio cita ID libreria. Per ogni raccomandazione clinica cita PMID.
"""


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

    user_msg = USER_TEMPLATE.format(
        condition=condition,
        date=datetime.now().strftime("%B %Y"),
        evidence_text=evidence_text,
        exercise_context=exercise_context,
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
