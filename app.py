import json
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from util import calculate_da_costs, calculate_flexibilitätsband, calculate_lastgang_after_fahrplan, convert_csv_to_json, finde_konstante_soc_zeiträume, berechne_strategien

st.title("Batteriespeicher Day-Ahead Optimierung")
st.write("Bitte geben Sie die folgenden Informationen ein und laden Sie die benötigten Dateien hoch.")

# 1. Kapazität des Batteriespeichers (kWh)
capacity = st.number_input("1. Kapazität des Batteriespeichers (kWh, Nameplate)", min_value=0.0, step=1.0, value=1000.0, format="%.2f")

# 2. Leistung des Batteriespeichers (kW)
power = st.number_input("2. Leistung des Batteriespeichers (kW, Nameplate)", min_value=0.0, step=1.0, value=1000.0, format="%.2f")

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

st.header("6. Strategien errechnen")

if (os.path.exists("konstante_soc_zeiträume.json") and 
    os.path.exists("flexband_safeguarded.json") and 
    os.path.exists("da-prices.json") and 
    os.path.exists("user_inputs.json")):
    
    try:
        strategien_liste, strategien_csv = berechne_strategien(
            "konstante_soc_zeiträume.json",
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
    st.info("⚠️ Bitte stellen Sie sicher, dass alle vorherigen Schritte abgeschlossen sind, bevor Sie Strategien berechnen können.")
