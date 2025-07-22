import json
import os
import pandas as pd


def convert_csv_to_json(input_path):
    # Create csv directory if it doesn't exist
    os.makedirs('csv', exist_ok=True)
    
    # Move input file to csv directory
    filename = os.path.basename(input_path)
    new_input_path = os.path.join('csv', filename)
    if input_path != new_input_path:
        os.rename(input_path, new_input_path)
    
    base, ext = os.path.splitext(new_input_path)
    output_json = f"{os.path.splitext(input_path)[0]}.json"
    data = []
    
    with open(new_input_path, 'r', encoding='utf-8') as f:
        reader = pd.read_csv(f, delimiter=';')
        for _, row in reader.iterrows():
            value = float(str(row['value']).replace(',', '.'))
            data.append({
                'index': int(row['index']),
                'timestamp': row['timestamp'],
                'value': value
            })
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

def calculate_lastgang_after_fahrplan(lastgang, pv_erzeugung, fahrplan):
    if len(lastgang) == len(fahrplan) == len(pv_erzeugung):
        result = []
        for lg, fp, pv in zip(lastgang, fahrplan, pv_erzeugung):
            assert lg['index'] == fp['index'] and lg['timestamp'] == fp['timestamp'], "Index/Timestamp mismatch!"
            new_value = max(0, lg['value'] + fp['value'] - pv['value'])
            result.append({
                'index': lg['index'],
                'timestamp': lg['timestamp'],
                'value': round(new_value, 2)
            })
        # Speichern als JSON
        with open("lastgang_nach_fahrplan.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        # Speichern als CSV
        df_result = pd.DataFrame(result)
        df_result['value'] = df_result['value'].map(lambda x: f"{x:.2f}".replace('.', ','))
        resulting_csv_path = os.path.join("csv", "lastgang_nach_fahrplan.csv")
        df_result.to_csv(resulting_csv_path, index=False, sep=';')
        return result, resulting_csv_path
    else:
        raise ValueError("Fehler beim Errechnen des Lastgangs nach Fahrplan!")
    
def calculate_da_costs(lastgang, da_prices):
    if len(lastgang) == len(da_prices):
        kosten_liste = []
        summe_kosten = 0.0
        summe_kwh = 0.0
        for lg, price in zip(lastgang, da_prices):
            assert lg['index'] == price['index'] and lg['timestamp'] == price['timestamp'], "Index/Timestamp mismatch!"
            # Preis in ct/kWh, Lastgang in kW, Intervall = 15min = 0.25h
            # Kosten = Preis * (Leistung * 0.25)
            kosten = price['value'] * (lg['value'] / 4)
            kosten_liste.append({
                'index': lg['index'],
                'timestamp': lg['timestamp'],
                'kosten': round(kosten, 2)
            })
            summe_kosten += kosten
            summe_kwh += lg['value'] / 4
        # Speichern als JSON
        with open("kosten_lastgang_nach_fahrplan.json", "w", encoding="utf-8") as f:
            json.dump(kosten_liste, f, ensure_ascii=False, indent=2)
        # Speichern als CSV
        df_kosten = pd.DataFrame(kosten_liste)
        df_kosten_csv = df_kosten.copy()
        df_kosten_csv['kosten'] = df_kosten_csv['kosten'].map(lambda x: f"{x:.4f}".replace('.', ','))
        kosten_liste_csv = os.path.join("csv", "kosten_lastgang_nach_fahrplan.csv")
        df_kosten_csv.to_csv(kosten_liste_csv, index=False, sep=';')

        # KPIs
        durchschnittskosten = round(summe_kosten / summe_kwh if summe_kwh > 0 else 0, 4)

        return kosten_liste, kosten_liste_csv, summe_kosten, durchschnittskosten
    else:
        raise ValueError("Fehler beim Errechnen der Day-Ahead-Kosten!")
    
def calculate_flexibilitätsband(initial_soc, lastgang, fahrplan, user_inputs):
    with open(lastgang, "r", encoding="utf-8") as f:
        lastgang = json.load(f)
    with open(fahrplan, "r", encoding="utf-8") as f:
        fahrplan = json.load(f)
    with open(user_inputs, "r", encoding="utf-8") as f:
        user_inputs = json.load(f)

    capacity = user_inputs["capacity_kWh"]
    power = user_inputs["power_kW"]

    flexband = []

    soc = initial_soc * capacity

# Flexband ohne Einschränkung des Lastgangs
    for i, fp in enumerate(fahrplan):
        fp_value = fp['value']
        # soc
        if i == 0:
            soc = 0.3 * capacity
        else:
            soc = flexband[-1]['soc'] + (fahrplan[i-1]['value'] / 4)
         # charge_potential
        if fp_value < 0:
            charge_potential = 0.0
        elif fp_value == 0:
            charge_potential = 0.95 * power
        else:  # fp_value > 0
            charge_potential = 0.95 * power - fp_value
        # discharge_potential
        if fp_value > 0:
            discharge_potential = 0.0
        elif fp_value == 0:
            discharge_potential = -0.95 * power
        else:  # fp_value < 0
            discharge_potential = -0.95 * power - fp_value
        flexband.append({
            'index': fp['index'],
            'timestamp': fp['timestamp'],
            'charge_potential': round(charge_potential, 2),
            'discharge_potential': round(discharge_potential, 2),
            'soc': round(soc, 2)
        })
        # Speichern als JSON
    with open("flexband_not_safeguarded.json", "w", encoding="utf-8") as f:
        json.dump(flexband, f, ensure_ascii=False, indent=2)
    # Speichern als CSV
    df_flex = pd.DataFrame(flexband)
    df_flex['charge_potential'] = df_flex['charge_potential'].map(lambda x: f"{x:.2f}".replace('.', ','))
    df_flex['discharge_potential'] = df_flex['discharge_potential'].map(lambda x: f"{x:.2f}".replace('.', ','))
    df_flex['soc'] = df_flex['soc'].map(lambda x: f"{x:.2f}".replace('.', ','))
    df_flex.to_csv(os.path.join("csv", "flexband_not_safeguarded.csv"), index=False, sep=';')

    # Flexband mit Einschränkung des Lastgangs
    flexband_safeguarded = []
    soc = initial_soc * capacity

    for i, fp in enumerate(fahrplan):
        lg_value = lastgang[i]['value']
        fp_value = fp['value']

        # soc calculation same as before
        if i == 0:
            soc = 0.3 * capacity
        else:
            soc = flexband_safeguarded[-1]['soc'] + (fahrplan[i-1]['value'] / 4)

        # Get values from previous flexband calculation
        prev_charge = flexband[i]['charge_potential']
        prev_discharge = flexband[i]['discharge_potential']

        # New charge potential is minimum of previous and headroom to peak
        peak = max(lg['value'] for lg in lastgang)
        headroom = peak - lg_value
        charge_potential = min(prev_charge, headroom)

        # New discharge potential is maximum (least negative) of previous and negative load
        discharge_potential = max(prev_discharge, -lg_value)

        flexband_safeguarded.append({
            'index': fp['index'],
            'timestamp': fp['timestamp'], 
            'charge_potential': round(charge_potential, 2),
            'discharge_potential': round(discharge_potential, 2),
            'soc': round(soc, 2)
        })

    # Save as JSON
    with open("flexband_safeguarded.json", "w", encoding="utf-8") as f:
        json.dump(flexband_safeguarded, f, ensure_ascii=False, indent=2)

    # Save as CSV 
    df_flex_safe = pd.DataFrame(flexband_safeguarded)
    df_flex_safe['charge_potential'] = df_flex_safe['charge_potential'].map(lambda x: f"{x:.2f}".replace('.', ','))
    df_flex_safe['discharge_potential'] = df_flex_safe['discharge_potential'].map(lambda x: f"{x:.2f}".replace('.', ','))
    df_flex_safe['soc'] = df_flex_safe['soc'].map(lambda x: f"{x:.2f}".replace('.', ','))
    df_flex_safe.to_csv(os.path.join("csv", "flexband_safeguarded.csv"), index=False, sep=';')
    flexibilitätsband_csv = os.path.join("csv", "flexband_safeguarded.csv")
    # KPIs für das Flexibilitätsband
    max_beladung = max([fp['value'] for fp in fahrplan])
    max_entladung = min([fp['value'] for fp in fahrplan])
    max_soc = max([fb['soc'] for fb in flexband_safeguarded])
    min_soc = min([fb['soc'] for fb in flexband_safeguarded])
    anzahl_zyklen = round(sum([fp['value'] for fp in fahrplan if fp['value'] > 0]) / capacity/4, 2) if capacity > 0 else 0

    return flexband_safeguarded, flexibilitätsband_csv, max_beladung, max_entladung, max_soc, min_soc, anzahl_zyklen

def finde_konstante_soc_zeiträume(flexband_safeguarded, min_len=12):
    """
    Findet konstante SoC-Zeiträume.
    
    Args:
        soc_liste: Liste der SoC-Werte
        min_len: Minimale Länge eines Zeitraums
    
    Returns:
        Liste von (start, end)-Tupeln und CSV Dateipfad
    """
    with open(flexband_safeguarded, "r", encoding="utf-8") as f:
        flexband_safeguarded = json.load(f)
    soc_liste = [fb['soc'] for fb in flexband_safeguarded]

    result = []
    n = len(soc_liste)
    i = 0
    
    while i < n:
        start = i
        while i + 1 < n and soc_liste[i+1] == soc_liste[start]:
            i += 1
        
        zeitraum_laenge = i - start + 1
        if zeitraum_laenge >= min_len:
            if zeitraum_laenge <= 2 * min_len:
                # Zeitraum ist zwischen min_len und 2*min_len
                result.append({
                    "start": start+1,
                    "end": i-1,
                    "soc": soc_liste[start],
                    "länge": zeitraum_laenge
                })
            else:
                # Zeitraum ist länger als 2*min_len, in Teile aufteilen
                current_start = start
                while current_start <= i:
                    # Berechne das Ende des aktuellen Chunks (maximal 2*min_len lang)
                    current_end = min(current_start + 2 * min_len - 1, i)
                    verbleibende_laenge = i - current_end
                    
                    if verbleibende_laenge >= min_len:
                        result.append({
                            "start": current_start+1,
                            "end": current_end-1,
                            "soc": soc_liste[start],
                            "länge": current_end - current_start - 1
                        })
                        current_start = current_end + 1
                    else:
                        result.append({
                            "start": current_start+1,
                            "end": i-1,
                            "soc": soc_liste[start],
                            "länge": i - current_start - 1
                        })
                        break
        i += 1

    # Save as JSON
    with open("konstante_soc_zeiträume.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Save as CSV
    df_zeiträume = pd.DataFrame(result)
    df_zeiträume_csv = df_zeiträume.copy()
    df_zeiträume_csv['soc'] = df_zeiträume_csv['soc'].map(lambda x: f"{x:.2f}".replace('.', ','))
    csv_path = os.path.join("csv", "konstante_soc_zeiträume.csv")
    df_zeiträume_csv.to_csv(csv_path, index=False, sep=';')

    return result, csv_path

def berechne_strategien(konstante_soc_zeiträume_json, flexband_json, da_prices_json, user_inputs_json):
    """
    Berechnet lukrative Be- und Entladestrategien für konstante SoC-Zeiträume.
    
    Args:
        konstante_soc_zeiträume_json: Pfad zur JSON-Datei mit konstanten SoC-Zeiträumen
        flexband_json: Pfad zur JSON-Datei mit Flexibilitätsband
        da_prices_json: Pfad zur JSON-Datei mit Day-Ahead Preisen
        user_inputs_json: Pfad zur JSON-Datei mit Nutzereingaben
    
    Returns:
        strategien_liste, csv_path
    """
    # Daten laden
    with open(konstante_soc_zeiträume_json, "r", encoding="utf-8") as f:
        soc_zeiträume = json.load(f)
    with open(flexband_json, "r", encoding="utf-8") as f:
        flexband = json.load(f)
    with open(da_prices_json, "r", encoding="utf-8") as f:
        da_prices = json.load(f)
    with open(user_inputs_json, "r", encoding="utf-8") as f:
        user_inputs = json.load(f)
    
    # Lastgang nach Fahrplan laden
    with open("lastgang_nach_fahrplan.json", "r", encoding="utf-8") as f:
        lastgang_nach_fahrplan = json.load(f)
    
    capacity = user_inputs["capacity_kWh"]
    min_soc = 0.05 * capacity  # Mindest-SoC
    max_soc = 0.95 * capacity  # Maximal-SoC
    
    strategien_liste = []
    debug_info = {
        "gesamt_zeiträume": len(soc_zeiträume),
        "zu_kurze_zeiträume": 0,
        "keine_strategien_generiert": 0,
        "strategien_verworfen": 0,
        "erfolgreiche_strategien": 0
    }
    
    globale_strategie_id = 1  # Globale ID-Zählung
    
    for zeitraum_idx, zeitraum in enumerate(soc_zeiträume):
        start_idx = zeitraum["start"] - 1  # 0-basiert
        end_idx = zeitraum["end"] - 1      # 0-basiert
        
        # Relevante Daten für diesen Zeitraum extrahieren
        zeitraum_flexband = flexband[start_idx:end_idx+1]
        zeitraum_preise = da_prices[start_idx:end_idx+1]
        
        # Basis SoC des Zeitraums
        basis_soc = zeitraum["soc"]
        
        # Verschiedene Strategien generieren
        strategien = generiere_strategien(zeitraum_flexband, zeitraum_preise, basis_soc, min_soc, max_soc)
        
        if not strategien:
            debug_info["keine_strategien_generiert"] += 1
            continue
        
        for strategie_idx, strategie in enumerate(strategien):
            # Entsprechender Lastgang-Zeitraum
            zeitraum_lastgang = lastgang_nach_fahrplan[start_idx:end_idx+1]
            profit = berechne_profit(strategie, zeitraum_preise, zeitraum_lastgang)
            
            debug_info["erfolgreiche_strategien"] += 1
            
            # Strategie-Typ basierend auf Index bestimmen
            strategie_typen = ["Einfach", "Aggressiv", "Entlade-Lade"]
            strategie_typ = strategie_typen[strategie_idx] if strategie_idx < len(strategie_typen) else f"Typ-{strategie_idx + 1}"
            
            strategie_info = {
                "strategie_id": globale_strategie_id,
                "zeitraum_id": zeitraum_idx + 1,
                "strategie_typ": strategie_typ,
                "start_index": zeitraum["start"],
                "end_index": zeitraum["end"],
                "länge_stunden": len(strategie) * 0.25,
                "basis_soc": basis_soc,
                "max_soc_erreicht": max([s["soc"] for s in strategie]),
                "min_soc_erreicht": min([s["soc"] for s in strategie]),
                "gesamte_lademenge": sum([s["aktion"] for s in strategie if s["aktion"] > 0]) / 4,
                "gesamte_entlademenge": abs(sum([s["aktion"] for s in strategie if s["aktion"] < 0])) / 4,
                "profit_euro": round(profit, 2),
                "strategie_details": strategie
            }
            
            strategien_liste.append(strategie_info)
            globale_strategie_id += 1  # ID für nächste Strategie erhöhen
    
    # Nach Profit sortieren (höchster zuerst)
    strategien_liste.sort(key=lambda x: x["profit_euro"], reverse=True)
    
    # Debug-Info speichern
    with open("strategien_debug.json", "w", encoding="utf-8") as f:
        json.dump(debug_info, f, ensure_ascii=False, indent=2)
    
    # Als JSON speichern
    with open("strategien.json", "w", encoding="utf-8") as f:
        json.dump(strategien_liste, f, ensure_ascii=False, indent=2)
    
    # Als CSV speichern (ohne Details)
    strategien_summary = []
    for strategie in strategien_liste:
        strategien_summary.append({
            "strategie_id": strategie["strategie_id"],
            "zeitraum_id": strategie["zeitraum_id"],
            "strategie_typ": strategie["strategie_typ"],
            "start_index": strategie["start_index"],
            "end_index": strategie["end_index"],
            "länge_stunden": strategie["länge_stunden"],
            "basis_soc": strategie["basis_soc"],
            "max_soc_erreicht": strategie["max_soc_erreicht"],
            "min_soc_erreicht": strategie["min_soc_erreicht"],
            "gesamte_lademenge": strategie["gesamte_lademenge"],
            "gesamte_entlademenge": strategie["gesamte_entlademenge"],
            "profit_euro": strategie["profit_euro"]
        })
    
    df_strategien = pd.DataFrame(strategien_summary)
    os.makedirs("csv", exist_ok=True)
    csv_path = os.path.join("csv", "strategien.csv")
    df_strategien.to_csv(csv_path, index=False, sep=';')
    
    return strategien_liste, csv_path

def generiere_strategien(flexband_zeitraum, preise_zeitraum, basis_soc, min_soc, capacity):
    """
    Generiert verschiedene Be- und Entladestrategien für einen Zeitraum.
    """
    strategien = []
    n = len(flexband_zeitraum)
    
    # Prüfe ob Flexibilitätspotential vorhanden ist
    max_charge = max([fb["charge_potential"] for fb in flexband_zeitraum])
    min_discharge = min([fb["discharge_potential"] for fb in flexband_zeitraum])
    
    if max_charge <= 0 and min_discharge >= 0:
        # Kein Flexibilitätspotential vorhanden
        return strategien
    
    # Preise mit Indizes sortieren (günstigste zuerst für Laden)
    preise_mit_idx = [(i, preise_zeitraum[i]["value"]) for i in range(n)]
    preise_sortiert_laden = sorted(preise_mit_idx, key=lambda x: x[1])  # Günstigste zuerst
    preise_sortiert_entladen = sorted(preise_mit_idx, key=lambda x: x[1], reverse=True)  # Teuerste zuerst
    
    # Strategie 1: Einfache Lade-Entlade-Strategie (50% der Zeit laden, 50% entladen)
    if n >= 4:  # Mindestens 1 Stunde
        strategie1 = einfache_lade_entlade_strategie(flexband_zeitraum, preise_zeitraum, preise_sortiert_laden, preise_sortiert_entladen, basis_soc, min_soc, capacity)
        if strategie1:
            strategien.append(strategie1)
    
    # Strategie 2: Aggressive Strategie (mehr Zyklen, wenn möglich)
    if n >= 8:  # Mindestens 2 Stunden
        strategie2 = aggressive_strategie(flexband_zeitraum, preise_zeitraum, preise_sortiert_laden, preise_sortiert_entladen, basis_soc, min_soc, capacity)
        if strategie2:
            strategien.append(strategie2)
    
    # Strategie 3: Entlade-Lade-Strategie (erst entladen, dann beladen)
    if n >= 4:  # Mindestens 1 Stunde
        strategie3 = entlade_lade_strategie(flexband_zeitraum, preise_zeitraum, preise_sortiert_laden, preise_sortiert_entladen, basis_soc, min_soc, capacity)
        if strategie3:
            strategien.append(strategie3)
    
    return strategien

def einfache_lade_entlade_strategie(flexband, preise_zeitraum, preise_laden, preise_entladen, basis_soc, min_soc, capacity):
    """
    Einfache Strategie: Laden bei günstigen Preisen, Entladen bei teuren Preisen.
    """
    n = len(flexband)
    strategie = []
    aktueller_soc = basis_soc
    
    # Bestimme Anzahl der Lade- und Entladephasen
    anzahl_phasen = min(n // 2, 6)  # Maximal 6 Phasen pro Zeitraum
    
    lade_indices = [idx for idx, preis in preise_laden[:anzahl_phasen]]
    entlade_indices = [idx for idx, preis in preise_entladen[:anzahl_phasen]]
    
    for i in range(n):
        charge_pot = flexband[i]["charge_potential"]
        discharge_pot = flexband[i]["discharge_potential"]
        
        aktion = 0  # Default: keine Aktion
        
        if i in lade_indices:
            # Laden, aber SoC-Limits beachten
            max_ladung = min(charge_pot, (capacity - aktueller_soc) * 4)  # *4 wegen 15min Intervall
            aktion = max_ladung * 0.8  # 80% des Potentials nutzen
        elif i in entlade_indices:
            # Entladen, aber SoC-Limits beachten
            max_entladung = min(abs(discharge_pot), (aktueller_soc - min_soc) * 4)
            aktion = -max_entladung * 0.8  # 80% des Potentials nutzen
        
        # SoC aktualisieren
        neuer_soc = round(aktueller_soc + (aktion / 4), 2)
        
        # Sicherheitsprüfung
        if neuer_soc < min_soc or neuer_soc > capacity:
            aktion = 0
            neuer_soc = aktueller_soc
        
        strategie.append({
            "index": flexband[i]["index"],
            "timestamp": flexband[i]["timestamp"],
            "aktion": round(aktion, 2),
            "soc": round(neuer_soc, 2),
            "preis_ct_kwh": round(preise_zeitraum[i]["value"], 4)
        })
        
        aktueller_soc = neuer_soc
    
    # Prüfen ob Bilanz ausgeglichen ist (SoC am Ende = SoC am Anfang)
    soc_differenz = aktueller_soc - basis_soc
    if abs(soc_differenz) > 1.0:  # Erhöhte Toleranz von 1.0 kWh
        # Versuche Bilanz durch Anpassung der letzten Aktionen zu korrigieren
        strategie = korrigiere_soc_bilanz(strategie, soc_differenz, flexband, min_soc, capacity)
        if not strategie:
            return None  # Strategie nicht korrigierbar
    
    return strategie

def aggressive_strategie(flexband, preise_zeitraum, preise_laden, preise_entladen, basis_soc, min_soc, capacity):
    """
    Aggressive Strategie: Mehr Zyklen, höhere Nutzung der Potentiale.
    """
    n = len(flexband)
    strategie = []
    aktueller_soc = basis_soc
    
    anzahl_phasen = min(n // 2, 10)  # Mehr Phasen
    
    lade_indices = [idx for idx, preis in preise_laden[:anzahl_phasen]]
    entlade_indices = [idx for idx, preis in preise_entladen[:anzahl_phasen]]
    
    for i in range(n):
        charge_pot = flexband[i]["charge_potential"]
        discharge_pot = flexband[i]["discharge_potential"]
        
        aktion = 0
        
        if i in lade_indices:
            max_ladung = min(charge_pot, (capacity - aktueller_soc) * 4)
            aktion = max_ladung * 0.95  # 95% des Potentials nutzen
        elif i in entlade_indices:
            max_entladung = min(abs(discharge_pot), (aktueller_soc - min_soc) * 4)
            aktion = -max_entladung * 0.95
        
        neuer_soc = round(aktueller_soc + (aktion / 4), 2)
        
        if neuer_soc < min_soc or neuer_soc > capacity:
            aktion = 0
            neuer_soc = aktueller_soc
        
        strategie.append({
            "index": flexband[i]["index"],
            "timestamp": flexband[i]["timestamp"],
            "aktion": round(aktion, 2),
            "soc": round(neuer_soc, 2),
            "preis_ct_kwh": round(preise_zeitraum[i]["value"], 4)
        })
        
        aktueller_soc = neuer_soc
    
    soc_differenz = aktueller_soc - basis_soc
    if abs(soc_differenz) > 1.0:  # Erhöhte Toleranz von 1.0 kWh
        # Versuche Bilanz durch Anpassung der letzten Aktionen zu korrigieren
        strategie = korrigiere_soc_bilanz(strategie, soc_differenz, flexband, min_soc, capacity)
        if not strategie:
            return None  # Strategie nicht korrigierbar
    
        return strategie

def entlade_lade_strategie(flexband, preise_zeitraum, preise_laden, preise_entladen, basis_soc, min_soc, capacity):
    """
    Entlade-Lade-Strategie: Erst bei hohen Preisen entladen, dann bei niedrigen Preisen laden.
    """
    n = len(flexband)
    strategie = []
    aktueller_soc = basis_soc
    
    # Zeitraum in zwei Hälften teilen
    mitte = n // 2
    
    # Erste Hälfte: Entladen bei hohen Preisen
    entlade_phasen = min(mitte // 2, 4)  # Maximal 4 Entladephasen
    entlade_indices = [idx for idx, preis in preise_entladen[:entlade_phasen] if idx < mitte]
    
    # Zweite Hälfte: Laden bei niedrigen Preisen  
    lade_phasen = min((n - mitte) // 2, 4)  # Maximal 4 Ladephasen
    lade_indices = [idx for idx, preis in preise_laden[:lade_phasen] if idx >= mitte]
    
    # Gesamte entladene Energie tracking für Bilanzierung
    gesamt_entladung = 0.0
    gesamt_ladung = 0.0
    
    for i in range(n):
        charge_pot = flexband[i]["charge_potential"]
        discharge_pot = flexband[i]["discharge_potential"]
        
        aktion = 0  # Default: keine Aktion
        
        if i < mitte and i in entlade_indices:
            # Erste Hälfte: Entladen
            max_entladung = min(abs(discharge_pot), (aktueller_soc - min_soc) * 4)
            aktion = -max_entladung * 0.7  # 70% des Potentials nutzen
            gesamt_entladung += abs(aktion)
            
        elif i >= mitte and i in lade_indices:
            # Zweite Hälfte: Laden, aber nicht mehr als entladen wurde
            verblibende_ladung = gesamt_entladung - gesamt_ladung
            max_ladung = min(charge_pot, (capacity - aktueller_soc) * 4, verblibende_ladung)
            aktion = max_ladung * 0.7  # 70% des Potentials nutzen
            gesamt_ladung += aktion
        
        # SoC aktualisieren
        neuer_soc = round(aktueller_soc + (aktion / 4), 2)
        
        # Sicherheitsprüfung
        if neuer_soc < min_soc or neuer_soc > capacity:
            aktion = 0
            neuer_soc = aktueller_soc
        
        strategie.append({
            "index": flexband[i]["index"],
            "timestamp": flexband[i]["timestamp"],
            "aktion": round(aktion, 2),
            "soc": round(neuer_soc, 2),
            "preis_ct_kwh": round(preise_zeitraum[i]["value"], 4)
        })
        
        aktueller_soc = neuer_soc
    
    # Bilanz-Korrektur: Falls zu viel entladen wurde, in den letzten Ladephasen nachkorrigieren
    soc_differenz = aktueller_soc - basis_soc
    if abs(soc_differenz) > 1.0:
        # Spezielle Korrektur für Entlade-Lade-Strategie
        strategie = korrigiere_entlade_lade_bilanz(strategie, soc_differenz, flexband, min_soc, basis_soc, capacity, mitte)
        if not strategie:
            return None  # Strategie nicht korrigierbar
    
    return strategie

def korrigiere_entlade_lade_bilanz(strategie, soc_differenz, flexband, min_soc, basis_soc, capacity, mitte):
    """
    Spezielle Bilanz-Korrektur für Entlade-Lade-Strategien.
    """
    if not strategie:
        return None
    
    korrigierte_strategie = strategie.copy()
    
    # Benötigte Korrekturaktion in kW
    korrektur_kw = -soc_differenz * 4
    
    if soc_differenz > 0:
        # Zu viel geladen: Reduziere Ladung in der zweiten Hälfte
        lade_punkte = [i for i in range(mitte, len(strategie)) if strategie[i]["aktion"] > 0]
    else:
        # Zu wenig geladen: Erhöhe Ladung in der zweiten Hälfte oder reduziere Entladung
        lade_punkte = [i for i in range(mitte, len(strategie))]
    
    if not lade_punkte:
        return None
    
    korrektur_pro_punkt = korrektur_kw / len(lade_punkte)
    
    for i in lade_punkte:
        alte_aktion = korrigierte_strategie[i]["aktion"]
        neue_aktion = alte_aktion + korrektur_pro_punkt
        
        # Prüfe Flexband-Limits
        charge_pot = flexband[i]["charge_potential"]
        discharge_pot = flexband[i]["discharge_potential"]
        
        if neue_aktion < discharge_pot or neue_aktion > charge_pot:
            return None
        
        # SoC-Prüfung
        if i == 0:
            vorheriger_soc = basis_soc
        else:
            vorheriger_soc = korrigierte_strategie[i-1]["soc"]
        
        neuer_soc = vorheriger_soc + (neue_aktion / 4)
        
        if neuer_soc < min_soc or neuer_soc > capacity:
            return None
        
        # Anpassung durchführen
        korrigierte_strategie[i]["aktion"] = round(neue_aktion, 2)
        korrigierte_strategie[i]["soc"] = round(neuer_soc, 2)
        
        # SoC für nachfolgende Punkte aktualisieren
        for j in range(i+1, len(strategie)):
            korrigierte_strategie[j]["soc"] = round(korrigierte_strategie[j-1]["soc"] + (korrigierte_strategie[j]["aktion"] / 4), 2)
    
    return korrigierte_strategie

def korrigiere_soc_bilanz(strategie, soc_differenz, flexband, min_soc, capacity):
    """
    Versucht die SoC-Bilanz einer Strategie zu korrigieren.
    """
    if not strategie:
        return None
    
    # Kopie der Strategie für Korrekturen
    korrigierte_strategie = strategie.copy()
    
    # Benötigte Korrekturaktion in kW (über 15 min)
    korrektur_kw = -soc_differenz * 4  # *4 wegen 15min Intervall
    
    # Versuche Korrektur über die letzten 25% der Zeitpunkte
    anzahl_punkte = max(1, len(strategie) // 4)
    start_idx = len(strategie) - anzahl_punkte
    
    korrektur_pro_punkt = korrektur_kw / anzahl_punkte
    
    for i in range(start_idx, len(strategie)):
        alte_aktion = korrigierte_strategie[i]["aktion"]
        neue_aktion = alte_aktion + korrektur_pro_punkt
        
        # Prüfe Flexband-Limits
        charge_pot = flexband[i]["charge_potential"]
        discharge_pot = flexband[i]["discharge_potential"]
        
        if neue_aktion < discharge_pot or neue_aktion > charge_pot:
            # Korrektur nicht möglich ohne Limits zu verletzen
            return None
        
        # Prüfe SoC-Limits für diesen Punkt
        if i == 0:
            vorheriger_soc = strategie[0]["soc"] - (strategie[0]["aktion"] / 4)
        else:
            vorheriger_soc = korrigierte_strategie[i-1]["soc"]
        
        neuer_soc = vorheriger_soc + (neue_aktion / 4)
        
        if neuer_soc < min_soc or neuer_soc > capacity:
            # SoC-Limits verletzt
            return None
        
        # Anpassung durchführen
        korrigierte_strategie[i]["aktion"] = round(neue_aktion, 2)
        korrigierte_strategie[i]["soc"] = round(neuer_soc, 2)
        
        # SoC für nachfolgende Punkte aktualisieren
        for j in range(i+1, len(strategie)):
            korrigierte_strategie[j]["soc"] = round(korrigierte_strategie[j-1]["soc"] + (korrigierte_strategie[j]["aktion"] / 4), 2)
    
    return korrigierte_strategie

def berechne_profit(strategie, preise_zeitraum, lastgang_zeitraum):
    """
    Berechnet den Profit einer Strategie basierend auf Day-Ahead Preisen.
    Profit = Eingesparte Kosten beim Entladen - Kosten des Beladens
    """
    profit = 0.0
    
    for i, schritt in enumerate(strategie):
        aktion_kw = schritt["aktion"]
        preis_kwh = preise_zeitraum[i]["value"]
        
        # Energiemenge in kWh (15min = 0.25h)
        energie_kwh = abs(aktion_kw) * 0.25
        
        if aktion_kw > 0:  # Beladen
            # Kosten für das Beladen (negativer Profit-Beitrag)
            kosten_beladen = energie_kwh * preis_kwh  # ct -> Euro
            profit -= kosten_beladen
            
        elif aktion_kw < 0:  # Entladen
            # Eingesparte Kosten beim Entladen (positiver Profit-Beitrag)
            # Wir "sparen" die Kosten, die wir sonst für diese Energie bezahlt hätten
            eingesparte_kosten = energie_kwh * preis_kwh  # ct -> Euro
            profit += eingesparte_kosten
    
    return profit

def implementiere_strategien(strategien_json, fahrplan_json, user_inputs_json):
    """
    Implementiert die Strategien in den Batteriespeicher-Fahrplan.
    
    Args:
        strategien_json: Pfad zur JSON-Datei mit Strategien
        fahrplan_json: Pfad zur JSON-Datei mit ursprünglichem Fahrplan
        user_inputs_json: Pfad zur JSON-Datei mit Nutzereingaben
    
    Returns:
        neuer_fahrplan, csv_path, kpis
    """
    # Daten laden
    with open(strategien_json, "r", encoding="utf-8") as f:
        strategien = json.load(f)
    with open(fahrplan_json, "r", encoding="utf-8") as f:
        fahrplan = json.load(f)
    with open(user_inputs_json, "r", encoding="utf-8") as f:
        user_inputs = json.load(f)
    
    capacity = user_inputs["capacity_kWh"]
    daily_cycles = user_inputs["daily_cycles"]
    # Bisherige Zyklen aus dem Fahrplan berechnen
    bisherige_belademenge = 0.0
    for eintrag in fahrplan:
        if eintrag["value"] > 0:  # Nur positive Werte (Beladen) zählen
            bisherige_belademenge += eintrag["value"] * 0.25  # kW * 0.25h = kWh
    
    bisherige_zyklen = bisherige_belademenge / capacity
    max_belademenge = (daily_cycles * 365 - bisherige_zyklen) * capacity  # Verbleibende Jahresgrenze
    if max_belademenge < 0:
        max_belademenge = 0  # Keine weiteren Zyklen erlaubt
    # Neuen Fahrplan als Kopie des ursprünglichen erstellen
    neuer_fahrplan = [{"index": fp["index"], 
                      "timestamp": fp["timestamp"], 
                      "value": fp["value"]} for fp in fahrplan]
    
    # Tracking-Variablen
    gesamt_belademenge = 0.0
    implementierte_strategien = []
    verwendete_zeiträume = set()
    
    # Strategien nach Profit sortiert durchgehen (höchster zuerst)
    for strategie in strategien:
        start_idx = strategie["start_index"] - 1  # 0-basiert
        end_idx = strategie["end_index"] - 1      # 0-basiert
        
        # Prüfen ob Zeitraum bereits belegt ist
        zeitraum_range = set(range(start_idx, end_idx + 1))
        if zeitraum_range.intersection(verwendete_zeiträume):
            continue  # Zeitraum überschneidet sich, Strategie überspringen
        
        # Belademenge dieser Strategie berechnen
        strategie_belademenge = strategie["gesamte_lademenge"]
        
        # Prüfen ob Kapazitätsgrenze überschritten würde
        if gesamt_belademenge + strategie_belademenge > max_belademenge:
            break  # Stoppen, da Kapazitätsgrenze erreicht
        
        # Strategie implementieren
        for detail in strategie["strategie_details"]:
            idx = detail["index"] 
            if 0 <= idx < len(neuer_fahrplan):
                neuer_fahrplan[idx]["value"] += detail["aktion"]
                neuer_fahrplan[idx]["value"] = round(neuer_fahrplan[idx]["value"], 2)
        
        # Tracking aktualisieren
        gesamt_belademenge += strategie_belademenge
        implementierte_strategien.append(strategie)
        verwendete_zeiträume.update(zeitraum_range)
    
    # SoC für neuen Fahrplan berechnen
    neuer_fahrplan_mit_soc = berechne_soc_fahrplan(neuer_fahrplan, capacity)
    
    # KPIs berechnen
    kpis = berechne_fahrplan_kpis(neuer_fahrplan_mit_soc, implementierte_strategien, gesamt_belademenge, max_belademenge, capacity)
    
    # Als JSON speichern
    with open("implementierter_fahrplan.json", "w", encoding="utf-8") as f:
        json.dump(neuer_fahrplan_mit_soc, f, ensure_ascii=False, indent=2)
    
    # Als CSV speichern
    df_fahrplan = pd.DataFrame(neuer_fahrplan_mit_soc)
    df_fahrplan_csv = df_fahrplan.copy()
    df_fahrplan_csv['value'] = df_fahrplan_csv['value'].map(lambda x: f"{x:.2f}".replace('.', ','))
    df_fahrplan_csv['soc'] = df_fahrplan_csv['soc'].map(lambda x: f"{x:.2f}".replace('.', ','))
    os.makedirs("csv", exist_ok=True)
    csv_path = os.path.join("csv", "implementierter_fahrplan.csv")
    df_fahrplan_csv.to_csv(csv_path, index=False, sep=';')
    
    return neuer_fahrplan_mit_soc, csv_path, kpis

def berechne_soc_fahrplan(fahrplan, capacity):
    """
    Berechnet den SoC-Verlauf für einen Fahrplan.
    """
    fahrplan_mit_soc = []
    soc = 0.3 * capacity  # Startwert: 30% der Kapazität
    
    for i, fp in enumerate(fahrplan):
        # SoC aktualisieren basierend auf vorheriger Aktion
        if i > 0:
            soc += fahrplan[i-1]["value"] / 4  # 15min Intervall = /4
            soc = max(0.05 * capacity, min(capacity, soc))  # Grenzen einhalten
        
        fahrplan_mit_soc.append({
            "index": fp["index"],
            "timestamp": fp["timestamp"],
            "value": fp["value"],
            "soc": round(soc, 2)
        })
    
    return fahrplan_mit_soc

def berechne_fahrplan_kpis(fahrplan_mit_soc, implementierte_strategien, gesamt_belademenge, max_belademenge, capacity):
    """
    Berechnet KPIs für den implementierten Fahrplan.
    """
    # Basis-KPIs
    max_beladung = max([fp["value"] for fp in fahrplan_mit_soc])
    max_entladung = min([fp["value"] for fp in fahrplan_mit_soc])
    max_soc = max([fp["soc"] for fp in fahrplan_mit_soc])
    min_soc = min([fp["soc"] for fp in fahrplan_mit_soc])
    
    # Zyklen berechnen
    positive_aktionen = [fp["value"] for fp in fahrplan_mit_soc if fp["value"] > 0]
    anzahl_zyklen = sum(positive_aktionen) / 4 / capacity  # kWh pro Jahr

    
    # Strategien-KPIs
    anzahl_implementierter_strategien = len(implementierte_strategien)
    gesamt_profit = sum([s["profit_euro"] for s in implementierte_strategien])
    
    # Auslastung
    kapazitäts_auslastung = (gesamt_belademenge / max_belademenge * 100) if max_belademenge > 0 else 0
    
    # Strategietypen-Verteilung
    strategietypen = {}
    for strategie in implementierte_strategien:
        typ = strategie["strategie_typ"]
        strategietypen[typ] = strategietypen.get(typ, 0) + 1
    
    kpis = {
        "max_beladung": round(max_beladung, 2),
        "max_entladung": round(max_entladung, 2),
        "max_soc": round(max_soc, 2),
        "min_soc": round(min_soc, 2),
        "anzahl_zyklen": round(anzahl_zyklen, 2),
        "anzahl_implementierter_strategien": anzahl_implementierter_strategien,
        "gesamt_profit": round(gesamt_profit, 2),
        "gesamt_belademenge": round(gesamt_belademenge, 2),
        "max_belademenge": round(max_belademenge, 2),
        "kapazitäts_auslastung": round(kapazitäts_auslastung, 1),
        "strategietypen": strategietypen
    }
    
    return kpis

def calculate_finaler_lastgang(lastgang, pv_erzeugung, fahrplan):
    """
    Berechnet den finalen Lastgang nach optimiertem Fahrplan.
    Speichert in separate Datei um Überschreibung zu vermeiden.
    """
    if len(lastgang) == len(fahrplan) == len(pv_erzeugung):
        result = []
        for lg, fp, pv in zip(lastgang, fahrplan, pv_erzeugung):
            assert lg['index'] == fp['index'] and lg['timestamp'] == fp['timestamp'], "Index/Timestamp mismatch!"
            new_value = max(0, lg['value'] + fp['value'] - pv['value'])
            result.append({
                'index': lg['index'],
                'timestamp': lg['timestamp'],
                'value': round(new_value, 2)
            })
        # Speichern als JSON (andere Datei!)
        with open("finaler_optimierter_lastgang.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        # Speichern als CSV
        df_result = pd.DataFrame(result)
        df_result_csv = df_result.copy()
        df_result_csv['value'] = df_result_csv['value'].map(lambda x: f"{x:.2f}".replace('.', ','))
        os.makedirs("csv", exist_ok=True)
        resulting_csv_path = os.path.join("csv", "finaler_optimierter_lastgang.csv")
        df_result_csv.to_csv(resulting_csv_path, index=False, sep=';')
        return result, resulting_csv_path
    else:
        raise ValueError("Fehler beim Errechnen des finalen Lastgangs!")


