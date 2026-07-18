#!/usr/bin/env python3
"""
FisioEvidenceBot — App Desktop macOS
GUI per generazione protocolli riabilitativi evidence-based
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from bot import (gather_evidence, generate_protocol_full, read_medical_report,
                  parse_phase_context, EXERCISES, ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────
# Stile
# ─────────────────────────────────────────────
IS_MAC = sys.platform == "darwin"

C = {
    "bg":          "#F0F2F5",
    "sidebar":     "#FFFFFF",
    "primary":     "#1565C0",
    "prim_dark":   "#0D47A1",
    "success":     "#2E7D32",
    "warning":     "#E65100",
    "error":       "#B71C1C",
    "text":        "#212121",
    "text_lt":     "#757575",
    "border":      "#E0E0E0",
    "out_bg":      "#FAFAFA",
    "hdr_bg":      "#1565C0",
    "hdr_fg":      "#FFFFFF",
    "hdr_sub":     "#90CAF9",
    "phase_bg":    "#E3F2FD",
    "table_bg":    "#F5F5F5",
    "warn_bg":     "#FFF8E1",
    "ok_bg":       "#E8F5E9",
}

def _font(size=12, weight="normal", mono=False):
    if IS_MAC:
        family = "Menlo" if mono else ("SF Pro Display" if weight == "bold" else "SF Pro Text")
    else:
        family = "Courier" if mono else "Helvetica"
    return (family, size, weight)


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────

class FisioApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("FisioEvidenceBot — Protocolli Riabilitativi Evidence-Based")
        self.geometry("1320x860")
        self.minsize(1060, 700)
        self.configure(bg=C["bg"])
        if IS_MAC:
            self.createcommand("tk::mac::Quit", self.destroy)

        self._generating = False
        self._protocol_text = ""
        self._evidence_cache = None
        self._condition_last = ""
        self._referto_path = ""
        self._referto_text = ""

        self._setup_styles()
        self._build_ui()
        self._check_api()

    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TEntry", font=_font(12), padding=6)
        s.configure("TCombobox", font=_font(12), padding=4)
        s.configure("Vertical.TScrollbar", width=10)
        s.configure("TProgressbar", thickness=4)

    # ─── UI ──────────────────────────────────

    def _build_ui(self):
        self._build_header()
        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True)
        self._build_sidebar(main)
        tk.Frame(main, bg=C["border"], width=1).pack(fill="y", side="left")
        self._build_output(main)
        self._build_statusbar()

    def _build_header(self):
        h = tk.Frame(self, bg=C["hdr_bg"], height=58)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Label(h, text="🏥  FisioEvidenceBot",
                 bg=C["hdr_bg"], fg=C["hdr_fg"], font=_font(17, "bold")).pack(side="left", padx=22, pady=10)
        tk.Label(h, text=f"📚 {len(EXERCISES)} esercizi  |  PubMed + Claude AI  |  Evidence-Based Rehabilitation",
                 bg=C["hdr_bg"], fg=C["hdr_sub"], font=_font(10)).pack(side="right", padx=22)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=C["sidebar"], width=370)
        sidebar.pack(fill="y", side="left")
        sidebar.pack_propagate(False)

        canvas = tk.Canvas(sidebar, bg=C["sidebar"], highlightthickness=0)
        sb = ttk.Scrollbar(sidebar, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=C["sidebar"])
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Bind scroll width
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        for widget in (canvas, frame):
            widget.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
            widget.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        self._fill_form(frame)

    def _fill_form(self, f):
        P = dict(padx=16, pady=3)
        PB = dict(padx=16, pady=6)

        # ── Patologia ──
        self._sec(f, "👤  PAZIENTE")

        self._lbl(f, "Patologia / Condizione  ★")
        self.v_patologia = tk.StringVar()
        self._entry(f, self.v_patologia, "es. lesione ischiocrurale grado 2 Monaco, LCA operato, tendinopatia rotulea...")

        self._lbl(f, "Fase riabilitativa")
        self.v_fase = tk.StringVar(value="Sub-Acuta (1-2 sett.)")
        ttk.Combobox(f, textvariable=self.v_fase, font=_font(12), state="readonly",
                     values=["Acuta (0-72h / giorni 1-3)",
                             "Sub-Acuta (1-2 sett.)",
                             "Rinforzo iniziale (sett. 3-6)",
                             "Rinforzo avanzato (sett. 7-12)",
                             "Pre-Sport / RTS (sett. 13+)",
                             "Post-op precoce (sett. 0-2)",
                             "Post-op intermedia (sett. 3-8)",
                             "Post-op avanzata (sett. 8+)",
                             "Fase cronica / mantenimento",
                             ]).pack(fill="x", **PB, ipady=4)

        row = tk.Frame(f, bg=C["sidebar"])
        row.pack(fill="x", padx=16, pady=3)
        tk.Label(row, text="Settimane dall'evento", bg=C["sidebar"],
                 fg=C["text"], font=_font(12)).pack(side="left")
        self.v_weeks = tk.StringVar()
        ttk.Entry(row, textvariable=self.v_weeks, font=_font(12), width=5).pack(side="right", ipady=5)

        self._lbl(f, "Dolore attuale  VAS 0 – 10")
        vas_row = tk.Frame(f, bg=C["sidebar"])
        vas_row.pack(fill="x", **P)
        self.v_vas = tk.IntVar(value=3)
        self.vas_lbl = tk.Label(vas_row, text="3 / 10", width=7, anchor="e",
                                bg=C["sidebar"], fg=C["primary"], font=_font(13, "bold"))
        self.vas_lbl.pack(side="right")
        ttk.Scale(vas_row, from_=0, to=10, orient="horizontal", variable=self.v_vas,
                  command=lambda v: self.vas_lbl.config(text=f"{int(float(v))} / 10")
                  ).pack(side="left", fill="x", expand=True, pady=6)

        self._lbl(f, "Sport praticato")
        self.v_sport = tk.StringVar()
        self._entry(f, self.v_sport, "es. calcio, corsa, tennis, nuoto, pallavolo...")

        # ── Obiettivi ──
        self._sec(f, "🎯  OBIETTIVI E CLINICA")

        self._lbl(f, "Obiettivi del paziente")
        self.t_obiettivi = self._textarea(f, 3,
            "es. tornare a giocare a calcio entro 3 mesi, eliminare il dolore salendo le scale...")

        self._lbl(f, "Limitazioni / Comorbidità")
        self.t_limitazioni = self._textarea(f, 2,
            "es. diabete, ipertensione, precedenti interventi al ginocchio, sovrappeso...")

        self._lbl(f, "Note cliniche aggiuntive")
        self.t_note = self._textarea(f, 2,
            "es. paziente ansiosa, lavoro in piedi tutto il giorno, bassa compliance...")

        # ── Referto ──
        self._sec(f, "📄  REFERTO MEDICO")

        tk.Button(f, text="📂  Carica Referto (PDF / TXT / MD)",
                  command=self._load_referto,
                  bg=C["primary"], fg="white", font=_font(12), relief="flat",
                  cursor="hand2", padx=10, pady=8
                  ).pack(fill="x", **PB)

        self.referto_lbl = tk.Label(f, text="Nessun referto allegato",
                                    bg=C["sidebar"], fg=C["text_lt"],
                                    font=_font(10), wraplength=320, anchor="w", justify="left")
        self.referto_lbl.pack(fill="x", padx=16, pady=(0, 4))

        # ── Buttons ──
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", padx=16, pady=14)

        self.btn_genera = tk.Button(
            f, text="⚡  GENERA PROGRAMMA",
            command=self._genera,
            bg=C["primary"], fg="white",
            font=_font(14, "bold"),
            relief="flat", cursor="hand2", padx=14, pady=13)
        self.btn_genera.pack(fill="x", padx=16, pady=4)

        tk.Button(f, text="💾  Salva Protocollo",
                  command=self._save,
                  bg="#455A64", fg="white", font=_font(12),
                  relief="flat", cursor="hand2", pady=8
                  ).pack(fill="x", padx=16, pady=3)

        tk.Button(f, text="🗑  Pulisci Form",
                  command=self._clear,
                  bg="#78909C", fg="white", font=_font(11),
                  relief="flat", cursor="hand2", pady=6
                  ).pack(fill="x", padx=16, pady=(3, 24))

    def _build_output(self, parent):
        right = tk.Frame(parent, bg=C["bg"])
        right.pack(fill="both", expand=True)

        # Toolbar
        tb = tk.Frame(right, bg=C["bg"], height=46)
        tb.pack(fill="x", padx=16, pady=(10, 0))
        tb.pack_propagate(False)
        tk.Label(tb, text="PROTOCOLLO RIABILITATIVO",
                 bg=C["bg"], fg=C["text"], font=_font(13, "bold")).pack(side="left", pady=8)
        self.prog = ttk.Progressbar(tb, mode="indeterminate", length=180)

        # Output area
        out_frame = tk.Frame(right, bg=C["border"], bd=1, relief="solid")
        out_frame.pack(fill="both", expand=True, padx=16, pady=(6, 14))

        self.out = scrolledtext.ScrolledText(
            out_frame, font=_font(12), bg=C["out_bg"], fg=C["text"],
            wrap="word", relief="flat", padx=22, pady=18, spacing1=2, spacing2=1)
        self.out.pack(fill="both", expand=True)

        self.out.tag_configure("h1",    font=_font(16,"bold"), foreground=C["primary"],    spacing1=12, spacing3=4)
        self.out.tag_configure("h2",    font=_font(13,"bold"), foreground=C["prim_dark"],  spacing1=8,  spacing3=3)
        self.out.tag_configure("h3",    font=_font(12,"bold"), foreground="#37474F",       spacing1=6,  spacing3=2)
        self.out.tag_configure("phase", font=_font(12,"bold"), foreground=C["primary"],
                                background=C["phase_bg"], spacing1=5, spacing3=5, lmargin1=8, lmargin2=8)
        self.out.tag_configure("table", font=_font(11, mono=True), background=C["table_bg"],
                                lmargin1=6, lmargin2=6)
        self.out.tag_configure("warn",  foreground=C["warning"], background=C["warn_bg"])
        self.out.tag_configure("ok",    foreground=C["success"], background=C["ok_bg"])
        self.out.tag_configure("dim",   foreground=C["text_lt"], font=_font(11,"normal","italic" if not IS_MAC else "normal"))
        self.out.tag_configure("bold",  font=_font(12,"bold"))
        self.out.tag_configure("sep",   foreground=C["border"])
        self.out.tag_configure("ph",    foreground=C["text_lt"], font=_font(13))

        self._show_placeholder()

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=C["border"], height=28)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self.v_status = tk.StringVar(value="● Pronto")
        self.status_lbl = tk.Label(sb, textvariable=self.v_status, bg=C["border"],
                                    fg=C["text_lt"], font=_font(10), anchor="w")
        self.status_lbl.pack(fill="x", padx=12, pady=5)

    # ─── Widget helpers ───────────────────────

    def _sec(self, p, text):
        f = tk.Frame(p, bg="#EEF2F7")
        f.pack(fill="x", padx=0, pady=(12, 2))
        tk.Label(f, text=text, bg="#EEF2F7", fg=C["prim_dark"],
                 font=_font(11, "bold")).pack(side="left", padx=16, pady=5)

    def _lbl(self, p, text):
        tk.Label(p, text=text, bg=C["sidebar"], fg=C["text"],
                 font=_font(12), anchor="w").pack(fill="x", padx=16, pady=(7, 1))

    def _entry(self, p, var, ph=""):
        e = ttk.Entry(p, textvariable=var, font=_font(12))
        e.pack(fill="x", padx=16, pady=2, ipady=6)
        if ph:
            e.insert(0, ph)
            e.config(foreground="gray")
            def on_focus_in(ev, _e=e, _ph=ph):
                if _e.get() == _ph:
                    _e.delete(0, "end")
                    _e.config(foreground="black")
            def on_focus_out(ev, _e=e, _ph=ph):
                if not _e.get():
                    _e.insert(0, _ph)
                    _e.config(foreground="gray")
            e.bind("<FocusIn>", on_focus_in)
            e.bind("<FocusOut>", on_focus_out)
        return e

    def _textarea(self, p, h, ph=""):
        t = tk.Text(p, height=h, font=_font(12), bg="white", fg="black",
                    relief="solid", bd=1, wrap="word", padx=8, pady=6)
        t.pack(fill="x", padx=16, pady=2)
        if ph:
            t.insert("1.0", ph)
            t.config(fg="gray")
            def on_fi(ev, _t=t, _ph=ph):
                if _t.get("1.0", "end-1c") == _ph:
                    _t.delete("1.0", "end")
                    _t.config(fg="black")
            def on_fo(ev, _t=t, _ph=ph):
                if not _t.get("1.0", "end-1c").strip():
                    _t.insert("1.0", _ph)
                    _t.config(fg="gray")
            t.bind("<FocusIn>", on_fi)
            t.bind("<FocusOut>", on_fo)
        return t

    def _tv(self, widget, ph=""):
        """Legge valore da Text widget, esclude placeholder."""
        val = widget.get("1.0", "end-1c").strip()
        return "" if val == ph else val

    def _ev(self, var, ph=""):
        """Legge valore da Entry var, esclude placeholder."""
        val = var.get().strip()
        return "" if val.startswith("es.") or val == ph else val

    # ─── Actions ─────────────────────────────

    def _check_api(self):
        if not ANTHROPIC_API_KEY:
            self._status("⚠️  ANTHROPIC_API_KEY non impostata — configura prima di generare", "warn")

    def _load_referto(self):
        path = filedialog.askopenfilename(
            title="Seleziona Referto Medico",
            filetypes=[("Documenti medici", "*.pdf *.txt *.md"),
                       ("PDF", "*.pdf"), ("Testo", "*.txt *.md"), ("Tutti i file", "*.*")])
        if not path:
            return
        self._referto_path = path
        name = Path(path).name
        self.referto_lbl.config(text=f"✓ {name}", fg=C["success"])
        self._status(f"📄 Referto caricato: {name}", "ok")

    def _genera(self):
        if self._generating:
            return

        patologia = self._ev(self.v_patologia)
        if not patologia:
            messagebox.showwarning("Campo obbligatorio",
                                   "Inserisci la patologia / condizione del paziente.")
            return
        if not ANTHROPIC_API_KEY:
            messagebox.showerror("API Key mancante",
                                 "Configura ANTHROPIC_API_KEY nel terminale prima di avviare l'app:\n\n"
                                 "export ANTHROPIC_API_KEY='sk-ant-...'")
            return

        self._generating = True
        self.btn_genera.config(state="disabled", text="⏳  Generazione in corso...")
        self.prog.pack(side="right", pady=8)
        self.prog.start(10)

        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        self.out.config(state="disabled")

        params = dict(
            patologia=patologia,
            fase=self.v_fase.get(),
            weeks=self._ev(self.v_weeks),
            pain_vas=self.v_vas.get(),
            sport=self._ev(self.v_sport),
            obiettivi=self._tv(self.t_obiettivi, "es. tornare a giocare a calcio entro 3 mesi, eliminare il dolore salendo le scale..."),
            limitazioni=self._tv(self.t_limitazioni, "es. diabete, ipertensione, precedenti interventi al ginocchio, sovrappeso..."),
            note=self._tv(self.t_note, "es. paziente ansiosa, lavoro in piedi tutto il giorno, bassa compliance..."),
            referto_path=self._referto_path,
        )
        threading.Thread(target=self._run, args=(params,), daemon=True).start()

    def _run(self, p):
        try:
            patologia = p["patologia"]
            weeks_str = p["weeks"]
            condition = f"{patologia} {weeks_str} settimane".strip() if weeks_str else patologia

            # Read referto
            medical_report = ""
            if p["referto_path"]:
                self._status("📄 Lettura referto medico...", "info")
                medical_report = read_medical_report(p["referto_path"])
                chars = len(medical_report)
                self._append(f"📄 Referto medico letto: {chars} caratteri\n\n")

            # PubMed
            self._status("🔍 Ricerca PubMed (19 query in corso)...", "info")
            self._append(f"🔍 Ricerca evidenze per: {condition}\n")
            self._append("    → systematic reviews, meta-analisi, RCT, linee guida...\n\n")

            evidence = gather_evidence(condition)
            n = sum(len(v) for v in evidence.values())
            self._evidence_cache = evidence
            self._append(f"📚 {n} articoli PubMed recuperati\n\n")

            # Generate
            self._status("🧠 Sintesi con Claude AI...", "info")
            self._append("🧠 Generazione protocollo con Claude (claude-sonnet-5)...\n")
            self._append("─" * 68 + "\n\n")

            weeks_int = int(weeks_str) if weeks_str.isdigit() else None

            protocol = generate_protocol_full(
                condition=condition,
                evidence=evidence,
                pain_vas=p["pain_vas"],
                sport=p["sport"],
                objectives=p["obiettivi"],
                limitations=p["limitazioni"],
                notes=p["note"],
                medical_report=medical_report,
                fase_input=p["fase"],
                weeks=weeks_int,
            )

            self._protocol_text = protocol
            self._condition_last = condition
            self.after(0, self._display, protocol)
            self._status(f"✅ Protocollo generato — {n} articoli PubMed analizzati", "ok")

        except Exception as e:
            self._status(f"❌ Errore: {e}", "err")
            self._append(f"\n❌ Errore:\n{e}\n")
        finally:
            self.after(0, self._done)

    def _done(self):
        self._generating = False
        self.btn_genera.config(state="normal", text="⚡  GENERA PROGRAMMA")
        self.prog.stop()
        self.prog.pack_forget()

    def _display(self, text):
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        for line in text.split("\n"):
            stripped = line.lstrip()
            if stripped.startswith("## "):
                self.out.insert("end", stripped[3:] + "\n", "h1")
            elif stripped.startswith("### "):
                self.out.insert("end", stripped[4:] + "\n", "h2")
            elif stripped.startswith("#### "):
                self.out.insert("end", stripped[5:] + "\n", "h3")
            elif line.startswith("🔥") or line.startswith("🧱") or line.startswith("⚡") or \
                 line.startswith("💪") or line.startswith("🧘"):
                self.out.insert("end", line + "\n", "phase")
            elif line.startswith("|"):
                self.out.insert("end", line + "\n", "table")
            elif line.startswith("⚠️") or "RED FLAG" in line.upper():
                self.out.insert("end", line + "\n", "warn")
            elif line.startswith("✅") or line.startswith("✓"):
                self.out.insert("end", line + "\n", "ok")
            elif line.startswith("---"):
                self.out.insert("end", "─" * 72 + "\n", "sep")
            else:
                self.out.insert("end", line + "\n")
        self.out.config(state="disabled")
        self.out.see("1.0")

    def _append(self, text):
        def _do():
            self.out.config(state="normal")
            self.out.insert("end", text)
            self.out.see("end")
            self.out.config(state="disabled")
        self.after(0, _do)

    def _status(self, msg, level="info"):
        fg = {"info": C["text_lt"], "ok": C["success"],
              "warn": C["warning"], "err": C["error"]}.get(level, C["text_lt"])
        def _do():
            self.v_status.set(msg)
            self.status_lbl.config(fg=fg)
        self.after(0, _do)

    def _save(self):
        if not self._protocol_text:
            messagebox.showinfo("Nessun output", "Genera prima un protocollo.")
            return
        cond = "".join(c if c.isalnum() else "_" for c in self._condition_last)[:30]
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        init = f"protocollo_{cond}_{ts}.md"
        path = filedialog.asksaveasfilename(
            defaultextension=".md", initialfile=init,
            filetypes=[("Markdown", "*.md"), ("Testo", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"# Protocollo Riabilitativo — {self._condition_last}\n")
                fh.write(f"*Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')} — FisioEvidenceBot*\n\n")
                fh.write(self._protocol_text)
            self._status(f"✅ Salvato: {path}", "ok")

    def _clear(self):
        self.v_patologia.set("")
        self.v_weeks.set("")
        self.v_sport.set("")
        self.v_vas.set(3)
        self.vas_lbl.config(text="3 / 10")
        for t in (self.t_obiettivi, self.t_limitazioni, self.t_note):
            t.delete("1.0", "end")
        self._referto_path = ""
        self.referto_lbl.config(text="Nessun referto allegato", fg=C["text_lt"])
        self._protocol_text = ""
        self._evidence_cache = None
        self._show_placeholder()
        self._status("● Pronto", "info")

    def _show_placeholder(self):
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("1.0",
            "\n\n"
            "   Compila il form e premi  ⚡ GENERA PROGRAMMA\n\n"
            "   Il bot eseguirà:\n"
            "   • Lettura referto medico (se allegato)\n"
            "   • 19 ricerche PubMed: systematic reviews, RCT, meta-analisi,\n"
            "     linee guida, isometria, eccentric loading, RTP/RTS...\n"
            "   • Analisi fase attuale e obiettivi settimana per settimana\n"
            "   • Sintesi con Claude AI (claude-sonnet-5)\n"
            "   • Selezione esercizi dalla libreria personalizzata\n\n"
            "   ⏱️  Tempo stimato: 60 – 90 secondi\n",
            "ph")
        self.out.config(state="disabled")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = FisioApp()
    app.mainloop()
