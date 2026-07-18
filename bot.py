#!/usr/bin/env python3
"""
FisioEvidenceBot — Protocolli riabilitativi evidence-based da PubMed + Claude AI
"""

import os
import sys
import json
import time
import requests
import anthropic
from datetime import datetime

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# PubMed helpers (richiedono accesso Internet diretto a eutils.ncbi.nlm.nih.gov)
# ---------------------------------------------------------------------------

def pubmed_search(query: str, max_results: int = 10, filters: str = "") -> list[str]:
    full_query = f"{query} {filters}".strip()
    params = {
        "db": "pubmed",
        "term": full_query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def pubmed_fetch_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    import xml.etree.ElementTree as ET

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    r = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    articles = []

    for article in root.findall(".//PubmedArticle"):
        pmid_el   = article.find(".//PMID")
        title_el  = article.find(".//ArticleTitle")
        abs_el    = article.find(".//AbstractText")
        year_el   = article.find(".//PubDate/Year")
        journal_el = article.find(".//Journal/Title")
        authors   = article.findall(".//Author/LastName")

        abstract = "".join(abs_el.itertext()) if abs_el is not None else ""
        if not abstract:
            continue

        articles.append({
            "pmid":    pmid_el.text if pmid_el is not None else "?",
            "title":   "".join(title_el.itertext()) if title_el is not None else "N/A",
            "abstract": abstract[:1200],
            "year":    year_el.text if year_el is not None else "?",
            "journal": journal_el.text if journal_el is not None else "?",
            "author":  authors[0].text if authors else "?",
        })
    return articles


def gather_evidence_pubmed(condition: str) -> dict[str, list[dict]]:
    """Raccoglie evidenze via NCBI E-utilities (richiede Internet diretto)."""
    print("\n🔍 Ricerca evidenze su PubMed (E-utilities)...")

    searches = {
        "systematic_reviews": (f"{condition} rehabilitation", "(systematic review[pt] OR meta-analysis[pt])"),
        "rct":                (f"{condition} physiotherapy exercise protocol", "(randomized controlled trial[pt])"),
        "rtp_rts":            (f"{condition} return to sport return to play criteria", ""),
        "phases":             (f"{condition} rehabilitation phases progression criteria", ""),
        "load_management":    (f"{condition} load management neuromuscular training", ""),
        "prognosis":          (f"{condition} prognosis outcome functional recovery", "(clinical trial[pt] OR cohort study[tw])"),
    }

    evidence = {}
    total = 0
    for key, (query, filters) in searches.items():
        label = key.replace("_", " ").upper()
        print(f"  ↳ [{label}] ...", end=" ", flush=True)
        try:
            pmids = pubmed_search(query, max_results=10, filters=filters)
            articles = pubmed_fetch_abstracts(pmids[:8])
            evidence[key] = articles
            total += len(articles)
            print(f"{len(articles)} articoli")
        except Exception as e:
            print(f"errore ({e})")
            evidence[key] = []
        time.sleep(0.35)

    print(f"\n📚 Totale: {total} articoli recuperati")
    return evidence


# ---------------------------------------------------------------------------
# Sintesi protocollo via Claude
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Sei un fisioterapista esperto con PhD in scienze riabilitative e sportiva.
Generi protocolli riabilitativi basati ESCLUSIVAMENTE su evidenze scientifiche PubMed.

Regole ferree:
1. Ogni raccomandazione deve citare PMID o DOI della fonte.
2. Gerarchia evidenze: systematic review/meta-analisi > RCT > coorte prospettica.
3. Indica livello di evidenza: (A) forte • (B) moderata • (C) limitata/esperto.
4. Struttura sempre in fasi con criteri di avanzamento MISURABILI (es. LSI ≥90%, KOOS ≥80).
5. Include SEMPRE: Valutazione → Fase 1→4 → RTP → RTT → RTS → Red Flags → Bibliografia.
6. Per RTS: criteri biometrici + funzionali + psicologici (ACL-RSI, TSK, ACL-RSI ≥65).
7. Rispondi in italiano tecnico-clinico, usa tabelle e liste per leggibilità.
8. Segnala gap nelle evidenze dove esistono.
"""

USER_TEMPLATE = """\
CONDIZIONE PAZIENTE: {condition}

━━━ EVIDENZE SCIENTIFICHE DA PUBMED ({date}) ━━━
{evidence_text}

━━━ RICHIESTA ━━━
Crea un protocollo riabilitativo COMPLETO basato SOLO sulle evidenze sopra.
Struttura obbligatoria:

## 1. VALUTAZIONE INIZIALE
- Parametri, strumenti validati (KOOS, IKDC, ACL-RSI, TSK, Lysholm)

## 2. FASE 1 — PROTEZIONE / FASE ACUTA
- Obiettivi, trattamenti, parametri di carico, criteri di uscita

## 3. FASE 2 — RECUPERO FUNZIONALE
- Obiettivi, esercizi progressivi, criteri di uscita

## 4. FASE 3 — RINFORZO MUSCOLARE E NEUROMUSCOLARE
- Rinforzo quadricipiti/ischiocrurali, propriocettività, criteri di uscita

## 5. FASE 4 — PRE-SPORT / SPORT-SPECIFICO
- Gesti tecnici sport-specifici, plyometria, criteri di uscita

## 6. RTP — RETURN TO PLAY
- Criteri, test funzionali (hop test, forza, ROM), tempistiche

## 7. RTT — RETURN TO TRAINING
- Progressione carichi, sessioni di allenamento, monitoraggio

## 8. RTS — RETURN TO SPORT (FULL)
- Criteri biometrici: LSI ≥90%, H:Q ratio ≥0.6
- Criteri funzionali: hop test battery
- Criteri psicologici: ACL-RSI, TSK
- Tempistiche minime evidence-based

## 9. RED FLAGS
- Segnali di allarme per rivalutazione medico-chirurgica

## 10. BIBLIOGRAFIA
- Lista con PMID, DOI e livello di evidenza usato

Per ogni punto cita fonte (PMID) e livello evidenza (A/B/C).
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
                f"  {a['abstract'][:700]}"
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
    evidence_text = build_evidence_text(evidence)

    user_msg = USER_TEMPLATE.format(
        condition=condition,
        date=datetime.now().strftime("%B %Y"),
        evidence_text=evidence_text,
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
    base = f"output_{safe}_{timestamp}"

    md_path = f"{base}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Protocollo Riabilitativo — {condition}\n")
        f.write(f"*Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')} — FisioEvidenceBot*\n\n")
        f.write(protocol)

    json_path = f"{base}_evidence.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"condition": condition, "evidence": evidence}, f, ensure_ascii=False, indent=2)

    return md_path


def banner():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       FisioEvidenceBot — Riabilitazione 100% Evidence-Based      ║
║           PubMed E-utilities  +  Claude Sonnet 5 AI              ║
╚══════════════════════════════════════════════════════════════════╝
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(condition: str):
    banner()
    print(f"📋 Condizione: {condition}")

    evidence = gather_evidence_pubmed(condition)
    protocol = generate_protocol(condition, evidence)

    print("\n" + "═" * 70)
    print(protocol)
    print("═" * 70)

    path = save_output(condition, protocol, evidence)
    print(f"\n✅ Protocollo salvato: {path}")


def interactive():
    banner()
    print("Modalità interattiva — 'exit' per uscire\n")
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
