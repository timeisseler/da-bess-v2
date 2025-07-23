import json
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from util import calculate_da_costs, calculate_flexibilitätsband, calculate_lastgang_after_fahrplan, convert_csv_to_json, finde_konstante_soc_zeiträume, finde_flexible_arbitrage_zeiträume, berechne_strategien, implementiere_strategien, calculate_finaler_lastgang

st.title("Batteriespeicher Day-Ahead Optimierung")
st.write("Bitte geben Sie die folgenden Informationen ein und laden Sie die benötigten Dateien hoch.")

# 1. Kapazität des Batteriespeichers (kWh)
capacity = st.number_input("1. Kapazität des Batteriespeichers (kWh, Nameplate)", min_value=0.0, step=1.0, value=1000.0, format="%.2f")

# 2. Leistung des Batteriespeichers (kW)
power = st.number_input("2. Leistung des Batteriespeichers (kW, Nameplate)", min_value=0.0, step=1.0, value=1000.0, format="%.2f")

# Template Download Button
with open("template_load_profile.csv", "rb") as f:
    st.download_button(
        label="📄 Template Lastprofil CSV herunterladen",
        data=f,
        file_name="template_load_profile.csv",
        mime="text/csv"
    )

# 3. Lastgang (CSV Upload)
lastgang_file = st.file_uploader("4. Lastgang des Industriekunden im 15-Minuten Intervall in kW (CSV)", type=["csv"])

# 4. PV-Erzeugungslastgang (CSV Upload)
pv_erzeugung_file = st.file_uploader("7. PV-Erzeugungslastgang im 15-Minuten Intervall in kW (CSV)", type=["csv"])

# 5. Bisheriger Fahrplan (CSV Upload)
fahrplan_file = st.file_uploader("5. Bisheriger Fahrplan des Energiespeichers im 15-Minuten Intervall in kW (CSV)", type=["csv"])

# 6. Day-Ahead Preise (CSV Upload)
da_prices_file = st.file_uploader("6. Day-Ahead Preise für das kommende Jahr (CSV)", type=["csv"])

# 7. Durchschnittlicher Strompreis des Industriekunden aus dem letzten Jahr (ct/kWh)
avg_price = st.number_input("3. Durchschnittlicher Strompreis des Industriekunden aus dem letzten Jahr (ct/kWh)", min_value=0.0000, step=0.0001, value=0.0896,   format="%.4f")

# 8. Maximale Zyklenanzahl pro Tag
daily_cycles = st.number_input("8. Maximale Zyklenanzahl pro Tag des Batteriespeichers", min_value=1, step=1)

# Speichern-Button
if st.button("Eingaben speichern"):
    # Eingaben als Dictionary
    user_inputs = {
        "capacity_kWh": capacity,
        "power_kW": power,
        "avg_price_ct_kWh": avg_price,
        "daily_cycles": daily_cycles,
        "timestamp": datetime.now().isoformat()
    }
    # Speichern als JSON
    with open("user_inputs.json", "w", encoding="utf-8") as f:
        json.dump(user_inputs, f, ensure_ascii=False, indent=2)
    # Speichern als CSV
    pd.DataFrame([user_inputs]).to_csv("user_inputs.csv", index=False, sep=';')

    # Dateien speichern und konvertieren
    tables = {}
    if lastgang_file:
        with open("lastgang.csv", "wb") as f:
            f.write(lastgang_file.getbuffer())
        tables['Lastgang'] = convert_csv_to_json("lastgang.csv")
    if fahrplan_file:
        with open("fahrplan.csv", "wb") as f:
            f.write(fahrplan_file.getbuffer())
        tables['Fahrplan'] = convert_csv_to_json("fahrplan.csv")
    if da_prices_file:
        with open("da-prices.csv", "wb") as f:
            f.write(da_prices_file.getbuffer())
        tables['Day-Ahead Preise'] = convert_csv_to_json("da-prices.csv")
    if pv_erzeugung_file:
        with open("pv-erzeugung.csv", "wb") as f:
            f.write(pv_erzeugung_file.getbuffer())
        tables['PV-Erzeugung'] = convert_csv_to_json("pv-erzeugung.csv")

    # Validierung: Längenvergleich
    lengths = {name: len(data) for name, data in tables.items()}
    if len(set(lengths.values())) > 1:
        st.warning(f"Achtung: Unterschiedliche Längen der Tabellen! {lengths}")
    else:
        st.info(f"Alle Tabellen haben die gleiche Länge: {list(lengths.values())[0]}")

    st.success("Eingaben und Dateien wurden gespeichert und konvertiert.")

    # Vorschau der ersten 10 Zeilen je Tabelle
    for name, data in tables.items():
        st.subheader(f"Vorschau: {name}")
        df_preview = pd.DataFrame(data).head(10)
        st.dataframe(df_preview)

st.header("2. Lastgang nach Fahrplan berechnen")

if os.path.exists("lastgang.json") and os.path.exists("fahrplan.json"):
    with open("lastgang.json", "r", encoding="utf-8") as f:
        lastgang = json.load(f)
    with open("fahrplan.json", "r", encoding="utf-8") as f:
        fahrplan = json.load(f)
    with open("pv-erzeugung.json", "r", encoding="utf-8") as f:
        pv_erzeugung = json.load(f)
    try:
        lastgang_after_fahrplan, resulting_csv = calculate_lastgang_after_fahrplan(lastgang, pv_erzeugung, fahrplan)
        st.success("Lastgang nach Fahrplan berechnet und gespeichert.")

        #KPIs
        gesamtverbrauch = round(sum(lg['value'] for lg in lastgang_after_fahrplan)/4, 2)
        lastspitze = round(max(lg['value'] for lg in lastgang_after_fahrplan), 2)

        #KPIs ausgeben
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="📊 Gesamtverbrauch", 
                value=f"{gesamtverbrauch:,.2f} kWh"
            )
        with col2:
            st.metric(
                label="⚡ Lastspitze", 
                value=f"{lastspitze:,.2f} kW"
            )
        
        st.dataframe(pd.DataFrame(lastgang_after_fahrplan).head(10))
        with open(resulting_csv, "rb") as f:
            st.download_button(
                label="CSV herunterladen",
                data=f,
                file_name="lastgang_nach_fahrplan.csv",
                mime="text/csv"
            )
    except ValueError as e:
        st.error(f"Fehler beim Berechnen des Lastgangs nach Fahrplan: {e}")

st.header("3. Kostenberechnung des Lastgangs nach Fahrplan am Day-Ahead")

if os.path.exists("lastgang_nach_fahrplan.json") and os.path.exists("da-prices.json"):
    with open("lastgang_nach_fahrplan.json", "r", encoding="utf-8") as f:
        lastgang_nf = json.load(f)
    with open("da-prices.json", "r", encoding="utf-8") as f:
        da_prices = json.load(f)
    try:
        kosten_liste, kosten_liste_csv, summe_kosten, durchschnittskosten = calculate_da_costs(lastgang_nf, da_prices)
        #KPIs
        summe_kosten = round(summe_kosten, 2)
        durchschnittskosten = round(durchschnittskosten, 4)

        #KPIs ausgeben
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="💰 Summe Day-Ahead-Kosten", 
                value=f"{summe_kosten:,.2f} €"
            )
        with col2:
            st.metric(
                label="📈 Durchschnittliche DA-Kosten", 
                value=f"{durchschnittskosten:,.4f} €/kWh"
            )
        st.success("Kostenberechnung des Lastgangs nach Fahrplan am Day-Ahead berechnet und gespeichert.")
    except ValueError as e:
        st.error(f"Fehler beim Berechnen der Day-Ahead-Kosten: {e}")

    

st.header("4. Flexibilitätsband des BESS berechnen")
if os.path.exists("lastgang_nach_fahrplan.json") and os.path.exists("fahrplan.json"):
    with open("lastgang_nach_fahrplan.json", "r", encoding="utf-8") as f:
        lastgang_nach_fahrplan = json.load(f)
    with open("fahrplan.json", "r", encoding="utf-8") as f:
        fahrplan = json.load(f)
    with open("user_inputs.json", "r", encoding="utf-8") as f:
        user_inputs = json.load(f)
    try:
        flexibilitätsband_safeguarded, flexibilitätsband_csv, max_beladung, max_entladung, max_soc, min_soc, anzahl_zyklen = calculate_flexibilitätsband(0.3,"lastgang_nach_fahrplan.json", "fahrplan.json", "user_inputs.json")
        
        #KPIs
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label="🔋 Max. Beladung", 
                value=f"{max_beladung:,.2f} kW"
            )
            st.metric(
                label="🔋 Max. Entladung", 
                value=f"{max_entladung:,.2f} kW"
            )
        with col2:
            st.metric(
                label="📊 Max. SOC", 
                value=f"{max_soc:,.2f} kWh"
            )
            st.metric(
                label="📉 Min. SOC", 
                value=f"{min_soc:,.2f} kWh"
            )
        with col3:
            st.metric(
                label="🔄 Anzahl Zyklen", 
                value=f"{anzahl_zyklen}"
            )
            st.metric(
                label="🔄 Anzahl Zyklen pro Tag", 
                value=f"{round(anzahl_zyklen/365, 2)}"
            )
        st.dataframe(pd.DataFrame(flexibilitätsband_safeguarded).head(10))
        with open(flexibilitätsband_csv, "rb") as f:
            st.download_button(
                label="CSV herunterladen",
                data=f,
                file_name=flexibilitätsband_csv,
                mime="text/csv"
            )
        st.success("Flexibilitätsband des BESS berechnet und gespeichert.")
    except ValueError as e:
        st.error(f"Fehler beim Berechnen des Flexibilitätsbandes: {e}")

st.header("5. Konstante SoC-Zeiträume finden")
if os.path.exists("flexband_safeguarded.json"):
    try:
        konstante_soc_zeiträume, konstante_soc_csv = finde_konstante_soc_zeiträume("flexband_safeguarded.json")
        st.metric(
            label="📊 Anzahl konstanter SoC-Zeiträume",
            value=len(konstante_soc_zeiträume)
        )
        st.success("Konstante SoC-Zeiträume berechnet und gespeichert.")
        st.dataframe(pd.DataFrame(konstante_soc_zeiträume).head(10))
        with open(konstante_soc_csv, "rb") as f:
            st.download_button(
                label="CSV herunterladen",
                data=f,
                file_name="konstante_soc_zeiträume.csv",
                mime="text/csv"
            )
        
    except ValueError as e:
        st.error(f"Fehler beim Finden der konstanten SoC-Zeiträume: {e}")

st.header("5. 🚀 Flexible Arbitrage-Zeiträume finden")
if os.path.exists("flexband_safeguarded.json") and os.path.exists("fahrplan.json"):
    
    # Erweiterte Konfiguration
    with st.expander("⚙️ Erweiterte Einstellungen für Arbitrage-Zeiträume"):
        col1, col2 = st.columns(2)
        with col1:
            min_länge = st.slider("Mindestlänge (Stunden)", 0.5, 6.0, 1.0, 0.25)
            max_zeitraum_länge = st.slider("Max. Zeitraum-Länge (Stunden)", 1.0, 24.0, 12.0, 1.0)
            st.caption("📝 Längere Zeiträume werden automatisch in kleinere Chunks aufgeteilt")
        with col2:
            soc_toleranz = st.slider("SoC Toleranz (%)", 5, 95, 20, 5)
            max_aktivität = st.slider("Max. Aktivität (%)", 5, 95, 20, 5)
    
    if st.button("🔍 Flexible Arbitrage-Zeiträume suchen"):
        try:
            min_len_intervalle = int(min_länge * 4)  # Stunden zu 15min-Intervallen
            
            arbitrage_zeiträume, arbitrage_csv = finde_flexible_arbitrage_zeiträume(
                "flexband_safeguarded.json",
                "fahrplan.json", 
                min_len=min_len_intervalle,
                soc_toleranz=soc_toleranz,
                max_aktivität_prozent=max_aktivität,
                max_stunden=max_zeitraum_länge
            )
            
            # Hauptstatistiken
            st.subheader("📊 Arbitrage-Potenzial Analyse")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    label="🎯 Arbitrage-Zeiträume gefunden",
                    value=len(arbitrage_zeiträume)
                )
            with col2:
                total_stunden = sum(z['länge_stunden'] for z in arbitrage_zeiträume)
                st.metric(
                    label="⏰ Gesamt-Potenzial",
                    value=f"{total_stunden:.1f} h"
                )
            with col3:
                if arbitrage_zeiträume:
                    avg_qualität = sum(z['qualität_score'] for z in arbitrage_zeiträume) / len(arbitrage_zeiträume)
                    st.metric(
                        label="⭐ Durchschnitts-Qualität", 
                        value=f"{avg_qualität:.2f}"
                    )
                else:
                    st.metric(label="⭐ Durchschnitts-Qualität", value="0.00")
            with col4:
                if arbitrage_zeiträume:
                    max_zeitraum = max(arbitrage_zeiträume, key=lambda x: x['länge_stunden'])
                    st.metric(
                        label="🏆 Längster Zeitraum",
                        value=f"{max_zeitraum['länge_stunden']:.1f} h"
                    )
                else:
                    st.metric(label="🏆 Längster Zeitraum", value="0.0 h")
            
            # Qualitätsverteilung
            if arbitrage_zeiträume:
                st.subheader("📈 Qualitätsverteilung der Arbitrage-Zeiträume")
                
                hoch_qualität = [z for z in arbitrage_zeiträume if z['qualität_score'] > 0.7]
                mittel_qualität = [z for z in arbitrage_zeiträume if 0.5 <= z['qualität_score'] <= 0.7]
                niedrig_qualität = [z for z in arbitrage_zeiträume if z['qualität_score'] < 0.5]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        label="🟢 Hoch (>0.7)",
                        value=len(hoch_qualität),
                        delta=f"{sum(z['länge_stunden'] for z in hoch_qualität):.1f}h"
                    )
                with col2:
                    st.metric(
                        label="🟡 Mittel (0.5-0.7)",
                        value=len(mittel_qualität),
                        delta=f"{sum(z['länge_stunden'] for z in mittel_qualität):.1f}h"
                    )
                with col3:
                    st.metric(
                        label="🟠 Niedrig (<0.5)",
                        value=len(niedrig_qualität),
                        delta=f"{sum(z['länge_stunden'] for z in niedrig_qualität):.1f}h"
                    )
                
                # Typ-Verteilung
                st.subheader("🔍 Zeitraum-Typen")
                soc_stabil = [z for z in arbitrage_zeiträume if z['typ'] == 'soc_stabil']
                niedrig_aktiv = [z for z in arbitrage_zeiträume if z['typ'] == 'niedrig_aktiv']
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="🔒 SoC-Stabil",
                        value=len(soc_stabil),
                        delta=f"Ø {sum(z['qualität_score'] for z in soc_stabil)/len(soc_stabil):.2f} Qualität" if soc_stabil else "0.00 Qualität"
                    )
                with col2:
                    st.metric(
                        label="😴 Niedrig-Aktiv", 
                        value=len(niedrig_aktiv),
                        delta=f"Ø {sum(z['qualität_score'] for z in niedrig_aktiv)/len(niedrig_aktiv):.2f} Qualität" if niedrig_aktiv else "0.00 Qualität"
                    )
                
                # Top Zeiträume
                st.subheader("🏆 Top 10 Arbitrage-Zeiträume (nach Qualität)")
                top_zeiträume = sorted(arbitrage_zeiträume, key=lambda x: x['qualität_score'], reverse=True)[:10]
                
                display_df = pd.DataFrame(top_zeiträume)
                display_columns = ['zeitraum_id', 'typ', 'länge_stunden', 'qualität_score', 'soc_variation', 'avg_aktivität']
                if all(col in display_df.columns for col in display_columns):
                    st.dataframe(
                        display_df[display_columns].round(3),
                        use_container_width=True,
                        column_config={
                            "zeitraum_id": "ID",
                            "typ": "Typ",
                            "länge_stunden": "Länge (h)",
                            "qualität_score": "Qualität",
                            "soc_variation": "SoC Var. (kWh)",
                            "avg_aktivität": "Ø Aktivität (kW)"
                        }
                    )
                else:
                    st.dataframe(display_df.head(10))
                
                # Downloads
                col1, col2 = st.columns(2)
                with col1:
                    if arbitrage_csv:
                        with open(arbitrage_csv, "rb") as f:
                            st.download_button(
                                label="📥 Arbitrage-Zeiträume CSV herunterladen",
                                data=f,
                                file_name="flexible_arbitrage_zeiträume.csv",
                                mime="text/csv"
                            )
                with col2:
                    with open("flexible_arbitrage_zeiträume.json", "rb") as f:
                        st.download_button(
                            label="📄 Arbitrage-Zeiträume JSON herunterladen",
                            data=f,
                            file_name="flexible_arbitrage_zeiträume.json",
                            mime="application/json"
                        )
                
                st.success(f"✅ {len(arbitrage_zeiträume)} flexible Arbitrage-Zeiträume erfolgreich identifiziert!")
                
                # Speichere auch für Kompatibilität
                konstante_soc_zeiträume = arbitrage_zeiträume
                konstante_soc_csv = arbitrage_csv
                
            else:
                st.warning("⚠️ Keine Arbitrage-Zeiträume mit den aktuellen Kriterien gefunden. Versuchen Sie lockerere Einstellungen.")
                
        except Exception as e:
            st.error(f"❌ Fehler beim Finden der Arbitrage-Zeiträume: {e}")
            
            # Fallback auf alte Methode
            st.info("🔄 Verwende Fallback-Methode...")
            try:
                konstante_soc_zeiträume, konstante_soc_csv = finde_konstante_soc_zeiträume("flexband_safeguarded.json")
                st.metric(
                    label="📊 Zeiträume (Fallback-Methode)",
                    value=len(konstante_soc_zeiträume)
                )
                if konstante_soc_zeiträume:
                    st.dataframe(pd.DataFrame(konstante_soc_zeiträume).head(10))
            except Exception as fallback_e:
                st.error(f"❌ Auch Fallback-Methode fehlgeschlagen: {fallback_e}")
else:
    st.info("⚠️ Bitte stellen Sie sicher, dass Flexibilitätsband und Fahrplan berechnet wurden.")

st.header("6. Strategien errechnen")

# Prüfe welche Zeitraum-Datei verfügbar ist
zeitraum_datei = None
if os.path.exists("flexible_arbitrage_zeiträume.json"):
    zeitraum_datei = "flexible_arbitrage_zeiträume.json"
    st.info("🚀 Verwende flexible Arbitrage-Zeiträume für Strategieberechnung")
elif os.path.exists("konstante_soc_zeiträume.json"):
    zeitraum_datei = "konstante_soc_zeiträume.json"
    st.info("⚙️ Verwende konstante SoC-Zeiträume für Strategieberechnung")

if (zeitraum_datei and 
    os.path.exists("flexband_safeguarded.json") and 
    os.path.exists("da-prices.json") and 
    os.path.exists("user_inputs.json")):
    
    try:
        strategien_liste, strategien_csv = berechne_strategien(
            zeitraum_datei,
            "flexband_safeguarded.json", 
            "da-prices.json",
            "user_inputs.json"
        )
        
        if strategien_liste:
            # KPIs der besten Strategien
            beste_strategie = strategien_liste[0]
            gesamt_profit = sum([s["profit_euro"] for s in strategien_liste])
            anzahl_strategien = len(strategien_liste)
            durchschnitts_profit = gesamt_profit / anzahl_strategien if anzahl_strategien > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label="💰 Beste Strategie Profit",
                    value=f"{beste_strategie['profit_euro']:.2f} €"
                )
                st.metric(
                    label="📊 Anzahl Strategien",
                    value=f"{anzahl_strategien}"
                )
            with col2:
                st.metric(
                    label="🎯 Gesamtprofit aller Strategien",
                    value=f"{gesamt_profit:.2f} €"
                )
                st.metric(
                    label="📈 Durchschnittsprofit",
                    value=f"{durchschnitts_profit:.2f} €"
                )
            with col3:
                st.metric(
                    label="⚡ Beste Strategie Länge",
                    value=f"{beste_strategie['länge_stunden']:.2f} h"
                )
                st.metric(
                    label="🔋 Max SoC erreicht",
                    value=f"{beste_strategie['max_soc_erreicht']:.2f} kWh"
                )
            
            # Top 10 Strategien anzeigen
            st.subheader("Top 10 Strategien (nach Profit sortiert)")
            
            # DataFrame für Anzeige erstellen (ohne Details)
            strategien_display = []
            for i, strategie in enumerate(strategien_liste[:10]):
                strategien_display.append({
                    "Rang": i + 1,
                    "Strategie ID": strategie["strategie_id"],
                    "Zeitraum ID": strategie["zeitraum_id"],
                    "Typ": strategie["strategie_typ"],
                    "Länge (h)": f"{strategie['länge_stunden']:.2f}",
                    "Profit (€)": f"{strategie['profit_euro']:.2f}",
                    "Lademenge (kWh)": f"{strategie['gesamte_lademenge']:.2f}",
                    "Entlademenge (kWh)": f"{strategie['gesamte_entlademenge']:.2f}",
                    "Max SoC (kWh)": f"{strategie['max_soc_erreicht']:.2f}",
                    "Min SoC (kWh)": f"{strategie['min_soc_erreicht']:.2f}"
                })
            
            st.dataframe(pd.DataFrame(strategien_display))
            
            # Download-Button für CSV
            with open(strategien_csv, "rb") as f:
                st.download_button(
                    label="📥 Alle Strategien als CSV herunterladen",
                    data=f,
                    file_name="strategien.csv",
                    mime="text/csv"
                )
            
            # Debug-Informationen anzeigen
            if os.path.exists("strategien_debug.json"):
                with open("strategien_debug.json", "r", encoding="utf-8") as f:
                    debug_info = json.load(f)
                
                st.subheader("🔍 Debug-Informationen")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Gesamt Zeiträume", debug_info["gesamt_zeiträume"])
                    st.metric("Keine Strategien generiert", debug_info["keine_strategien_generiert"])
                with col2:
                    st.metric("Erfolgreiche Strategien", debug_info["erfolgreiche_strategien"])
                    success_rate = (debug_info["erfolgreiche_strategien"] / debug_info["gesamt_zeiträume"] * 100) if debug_info["gesamt_zeiträume"] > 0 else 0
                    st.metric("Erfolgsrate", f"{success_rate:.1f}%")
                with col3:
                    failed_rate = 100 - success_rate
                    st.metric("Verworfene Zeiträume", f"{failed_rate:.1f}%")
            
            st.success("Strategien erfolgreich berechnet und gespeichert.")
            
        else:
            st.warning("Keine gültigen Strategien gefunden. Möglicherweise sind die Zeiträume zu kurz oder die Flexibilitätspotentiale zu gering.")
            
    except Exception as e:
        st.error(f"Fehler beim Berechnen der Strategien: {e}")
        
else:
    if not zeitraum_datei:
        st.warning("⚠️ Keine Zeitraum-Datei gefunden. Bitte führen Sie zuerst Schritt 5 (Zeiträume finden) aus.")
    else:
        st.info("⚠️ Bitte stellen Sie sicher, dass alle vorherigen Schritte abgeschlossen sind, bevor Sie Strategien berechnen können.")

st.header("7. Strategien implementieren")

if (os.path.exists("strategien.json") and 
    os.path.exists("fahrplan.json") and 
    os.path.exists("user_inputs.json")):
    
    try:
        implementierter_fahrplan, fahrplan_csv, kpis, implementierte_strategien_detail, strategien_detail_csv = implementiere_strategien(
            "strategien.json",
            "fahrplan.json", 
            "user_inputs.json"
        )
        
        # Haupt-KPIs anzeigen
        st.subheader("🎯 Implementierungs-Ergebnisse")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label="🏆 Anzahl Strategien implementiert",
                value=f"{kpis['anzahl_implementierter_strategien']}"
            )
            st.metric(
                label="💰 Gesamtprofit",
                value=f"{kpis['gesamt_profit']:.2f} €"
            )
            st.metric(
                label="📉 Min. SoC",
                value=f"{kpis['min_soc']:.2f} kWh"
            )
        with col2:
            st.metric(
                label="🔄 Anzahl Zyklen (Jahr)",
                value=f"{kpis['anzahl_zyklen']:.2f}"
            )
            durchschnitts_profit = kpis['gesamt_profit'] / kpis['anzahl_implementierter_strategien'] if kpis['anzahl_implementierter_strategien'] > 0 else 0
            st.metric(
                label="📈 Durchschnitts-Profit pro Strategie",
                value=f"{durchschnitts_profit:.2f} €"
            )
            st.metric(
                label="📈 Max. SoC",
                value=f"{kpis['max_soc']:.2f} kWh"
            )
        with col3:
            st.metric(
                label="🔋 Max. Beladung",
                value=f"{kpis['max_beladung']:.2f} kW"
            )
            st.metric(
                label="🔋 Max. Entladung", 
                value=f"{kpis['max_entladung']:.2f} kW"
            )
            
        st.success("✅ Strategien erfolgreich in den Fahrplan implementiert!")
        
        # Strategietypen-Verteilung
        if kpis['strategietypen']:
            st.subheader("📊 Strategietypen-Verteilung")
            strategietypen_df = pd.DataFrame([
                {"Strategietyp": typ, "Anzahl": anzahl, "Anteil": f"{anzahl/kpis['anzahl_implementierter_strategien']*100:.1f}%"} 
                for typ, anzahl in kpis['strategietypen'].items()
            ])
            st.dataframe(strategietypen_df, use_container_width=True)
        
        # Vorschau des implementierten Fahrplans
        st.subheader("📋 Implementierter Fahrplan (Vorschau)")
        st.dataframe(pd.DataFrame(implementierter_fahrplan).head(10))
        
        # Download-Buttons
        col1, col2 = st.columns(2)
        with col1:
            with open(fahrplan_csv, "rb") as f:
                st.download_button(
                    label="📥 Implementierten Fahrplan als CSV herunterladen",
                    data=f,
                    file_name="implementierter_fahrplan.csv",
                    mime="text/csv"
                )
        with col2:
            if strategien_detail_csv:
                with open(strategien_detail_csv, "rb") as f:
                    st.download_button(
                        label="📊 Detaillierte Strategien als CSV herunterladen",
                        data=f,
                        file_name="implementierte_strategien_detail.csv",
                        mime="text/csv"
                    )
        
        # Detaillierte Strategien-Analyse
        if implementierte_strategien_detail:
            st.subheader("🔍 Detaillierte Strategien-Implementierung")
            
            # Top 5 Strategien nach Profit anzeigen
            for i, strategie in enumerate(implementierte_strategien_detail[:5]):
                with st.expander(f"📋 Strategie {strategie['strategie_id']} - {strategie['strategie_typ']} (Profit: {strategie['profit_euro']:.2f} €)"):
                    
                    # Strategien-Info
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("💰 Profit", f"{strategie['profit_euro']:.2f} €")
                        st.metric("🏷️ Typ", strategie['strategie_typ'])
                    with col2:
                        st.metric("⏱️ Länge", f"{strategie['länge_stunden']:.2f} h")
                        st.metric("📊 Basis SoC", f"{strategie['basis_soc']:.2f} kWh")
                    with col3:
                        st.metric("🔼 Reihenfolge", f"#{strategie['implementierungs_reihenfolge']}")
                        st.metric("🎯 Zeitraum ID", strategie['zeitraum_id'])
                    
                    # Strategien-Schritte in Tabelle
                    if strategie['implementierte_schritte']:
                        st.write("**Implementierte Schritte:**")
                        schritte_df = pd.DataFrame(strategie['implementierte_schritte'])
                        
                        # Nur wichtige Spalten für Anzeige auswählen
                        display_columns = ['timestamp', 'aktion_typ', 'strategie_aktion', 'da_preis_ct_kwh', 'energie_kwh', 'kosten_erlös_euro']
                        if all(col in schritte_df.columns for col in display_columns):
                            display_df = schritte_df[display_columns].copy()
                            display_df.columns = ['Zeitpunkt', 'Aktion', 'Leistung (kW)', 'DA-Preis (ct/kWh)', 'Energie (kWh)', 'Kosten/Erlös (€)']
                            st.dataframe(display_df, use_container_width=True)
                        else:
                            st.dataframe(schritte_df, use_container_width=True)
                    
                    # Strategie-Zusammenfassung
                    total_energie = sum(step['energie_kwh'] for step in strategie['implementierte_schritte'])
                    total_kosten_erlös = sum(step['kosten_erlös_euro'] for step in strategie['implementierte_schritte'])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("⚡ Gesamte Energie", f"{total_energie:.2f} kWh")
                    with col2:
                        st.metric("💰 Gesamt Kosten/Erlös", f"{total_kosten_erlös:.2f} €")
        
    except Exception as e:
        st.error(f"❌ Fehler beim Implementieren der Strategien: {e}")
        
else:
    st.info("⚠️ Bitte stellen Sie sicher, dass alle vorherigen Schritte (Strategien berechnen) abgeschlossen sind.")

st.header("8. Finaler optimierter Lastgang")

if (os.path.exists("implementierter_fahrplan.json") and 
    os.path.exists("lastgang.json") and 
    os.path.exists("pv-erzeugung.json")):
    
    # Daten für Berechnung vorbereiten
    with open("implementierter_fahrplan.json", "r", encoding="utf-8") as f:
        implementierter_fahrplan = json.load(f)
    with open("lastgang.json", "r", encoding="utf-8") as f:
        lastgang = json.load(f)
    with open("pv-erzeugung.json", "r", encoding="utf-8") as f:
        pv_erzeugung = json.load(f)
    
    # Implementierten Fahrplan in das richtige Format für die Funktion bringen
    fahrplan_für_berechnung = [{"index": fp["index"], "timestamp": fp["timestamp"], "value": fp["value"]} for fp in implementierter_fahrplan]
    
    try:
        # Finalen Lastgang berechnen (mit separater Datei!)
        finaler_lastgang, finaler_csv = calculate_finaler_lastgang(lastgang, pv_erzeugung, fahrplan_für_berechnung)
        
        # KPIs des finalen Lastgangs berechnen
        gesamtverbrauch_final = round(sum(lg['value'] for lg in finaler_lastgang)/4, 2)
        lastspitze_final = round(max(lg['value'] for lg in finaler_lastgang), 2)
        
        # Vergleich mit ursprünglichem Lastgang nach Fahrplan
        if os.path.exists("lastgang_nach_fahrplan.json"):
            with open("lastgang_nach_fahrplan.json", "r", encoding="utf-8") as f:
                ursprünglicher_lastgang = json.load(f)
            
            gesamtverbrauch_ursprünglich = round(sum(lg['value'] for lg in ursprünglicher_lastgang)/4, 2)
            lastspitze_ursprünglich = round(max(lg['value'] for lg in ursprünglicher_lastgang), 2)
            
            # Kosten berechnen wenn DA-Preise verfügbar sind
            kosten_ursprünglich = 0.0
            kosten_final = 0.0
            kosten_ersparnis = 0.0
            kosten_ersparnis_prozent = 0.0
            
            if os.path.exists("da-prices.json"):
                with open("da-prices.json", "r", encoding="utf-8") as f:
                    da_prices = json.load(f)
                
                try:
                    # Kosten des ursprünglichen Lastgangs berechnen
                    _, _, kosten_ursprünglich, _ = calculate_da_costs(ursprünglicher_lastgang, da_prices)
                    # Kosten des finalen optimierten Lastgangs berechnen
                    _, _, kosten_final, _ = calculate_da_costs(finaler_lastgang, da_prices)
                    # Ersparnis berechnen
                    kosten_ersparnis = kosten_ursprünglich - kosten_final
                    kosten_ersparnis_prozent = (kosten_ersparnis / kosten_ursprünglich * 100) if kosten_ursprünglich > 0 else 0
                    
                except Exception as e:
                    st.warning(f"Kostenberechnung nicht möglich: {e}")
            
            # Verbesserungen berechnen
            verbrauch_differenz = gesamtverbrauch_ursprünglich - gesamtverbrauch_final
            lastspitze_differenz = lastspitze_ursprünglich - lastspitze_final
            
            # Erste Zeile: Verbrauch und Lastspitze
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label="📊 Gesamtverbrauch optimiert", 
                    value=f"{gesamtverbrauch_final:,.2f} kWh",
                    delta=f"{-verbrauch_differenz:,.2f} kWh", delta_color="inverse"
                )
            with col2:
                st.metric(
                    label="⚡ Lastspitze optimiert", 
                    value=f"{lastspitze_final:,.2f} kW",
                    delta=f"{-lastspitze_differenz:,.2f} kW", delta_color="inverse"
                )
            with col3:
                min_bezug = round(min(lg['value'] for lg in finaler_lastgang), 2)
                st.metric(
                    label="⬇️ Niedrigster Bezug",
                    value=f"{min_bezug:,.2f} kW"
                )
            # Zweite Zeile: Kosten (wenn verfügbar)
            if os.path.exists("da-prices.json") and kosten_ursprünglich > 0:
                col1, col2, col3= st.columns(3)
                with col1:
                    st.metric(
                        label="💰 DA-Kosten optimiert",
                        value=f"{kosten_final:,.2f} €",
                        delta=f"{-kosten_ersparnis:,.2f} €", delta_color="inverse"
                    )
                with col2:
                    st.metric(
                        label="💸 Kosteneinsparung",
                        value=f"{kosten_ersparnis:,.2f} €"
                    )
                with col3:
                    st.metric(
                        label="📊 Einsparung (%)",
                        value=f"{kosten_ersparnis_prozent:,.2f}%"
                    )
            
            # Detailvergleich
            st.subheader("🔍 Detailvergleich")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Ursprünglicher Lastgang:**")
                st.metric("Gesamtverbrauch", f"{gesamtverbrauch_ursprünglich:,.2f} kWh")
                st.metric("Lastspitze", f"{lastspitze_ursprünglich:,.2f} kW")
                if os.path.exists("da-prices.json") and kosten_ursprünglich > 0:
                    st.metric("Day-Ahead Kosten", f"{kosten_ursprünglich:,.2f} €")
                    st.metric("Kosten pro kWh", f"{kosten_ursprünglich/gesamtverbrauch_ursprünglich:,.4f} €/kWh")
            with col2:
                st.markdown("**Optimierter Lastgang:**")
                st.metric("Gesamtverbrauch", f"{gesamtverbrauch_final:,.2f} kWh")
                st.metric("Lastspitze", f"{lastspitze_final:,.2f} kW")
                if os.path.exists("da-prices.json") and kosten_final > 0:
                    st.metric("Day-Ahead Kosten", f"{kosten_final:,.2f} €")
                    st.metric("Kosten pro kWh", f"{kosten_final/gesamtverbrauch_final:,.4f} €/kWh")
        else:
            # Nur finale KPIs ohne Vergleich
            st.subheader("🎯 Finaler optimierter Lastgang")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="📊 Gesamtverbrauch optimiert", 
                    value=f"{gesamtverbrauch_final:,.2f} kWh"
                )
            with col2:
                st.metric(
                    label="⚡ Lastspitze optimiert", 
                    value=f"{lastspitze_final:,.2f} kW"
                )
        
        # Vorschau des finalen Lastgangs
        st.subheader("📋 Finaler optimierter Lastgang (Vorschau)")
        st.success("✅ Finaler optimierter Lastgang erfolgreich berechnet!")
        st.dataframe(pd.DataFrame(finaler_lastgang).head(10))
        
        # Download-Button für finalen Lastgang
        with open(finaler_csv, "rb") as f:
            st.download_button(
                label="📥 Finalen optimierten Lastgang als CSV herunterladen",
                data=f,
                file_name="finaler_optimierter_lastgang.csv",
                mime="text/csv"
            )
        
        # Gesamtoptimierungsergebnis anzeigen
        if os.path.exists("lastgang_nach_fahrplan.json") and os.path.exists("da-prices.json") and 'kosten_ersparnis' in locals() and kosten_ersparnis > 0:
            st.subheader("🏆 Gesamtoptimierungsergebnis")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="💰 Gesamte Kosteneinsparung",
                    value=f"{kosten_ersparnis:,.2f} €/Jahr"
                )
                # Capacity aus den user_inputs holen
                if os.path.exists("user_inputs.json"):
                    with open("user_inputs.json", "r", encoding="utf-8") as f:
                        user_inputs = json.load(f)
                    capacity = user_inputs.get("capacity_kWh", 1000)
                    st.metric(
                        label="⚡ Einsparung pro kWh verschoben",
                        value=f"{(kosten_ersparnis / capacity):,.2f} €/(kWh·Jahr)"
                    )
            with col2:
                st.metric(
                    label="📊 Relative Einsparung", 
                    value=f"{kosten_ersparnis_prozent:,.2f}%"
                )

        

        
    except ValueError as e:
        st.error(f"❌ Fehler beim Berechnen des finalen Lastgangs: {e}")
        
else:
    st.info("⚠️ Bitte stellen Sie sicher, dass alle vorherigen Schritte (Strategien implementieren) abgeschlossen sind.")
