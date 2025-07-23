# 🔋 Batteriespeicher Day-Ahead Optimierung

Eine intelligente Optimierungsplattform für Batteriespeicher-Systeme zur maximalen Ausnutzung von Day-Ahead-Markt-Arbitrage-Möglichkeiten.

## 📋 Übersicht

Diese Anwendung optimiert den Betrieb von Batteriespeicher-Systemen durch:
- **Intelligente Strategiengenerierung** für profitable Be-/Entladezyklen
- **Day-Ahead-Preisarbitrage** zur Kostenminimierung
- **Lastspitzenoptimierung** zur Reduktion von Spitzenlasten
- **Kapazitätsbegrenzung** zur Schonung der Batteriesysteme

## 🚀 Workflow - 8 Schritte zur Optimierung

### 1. **Datenupload und Validierung**
- **Lastgang** des Industriekunden (15-Min-Intervall, kW)
- **PV-Erzeugungsprofil** (15-Min-Intervall, kW) 
- **Ursprünglicher Batteriefahrplan** (15-Min-Intervall, kW)
- **Day-Ahead Preise** für das kommende Jahr (ct/kWh)
- **Batteriekonfiguration** (Kapazität, Leistung, Zyklen)

### 2. **Lastgang nach Fahrplan**
Berechnung des resultierenden Lastgangs:
```
Neuer Lastgang = max(0, Ursprünglicher Lastgang + Batteriefahrplan - PV-Erzeugung)
```

### 3. **Day-Ahead Kostenberechnung**
Ermittlung der Stromkosten basierend auf Day-Ahead Preisen:
```
Kosten = Σ(Lastgang[i] × DA-Preis[i] × 0.25h)
```

### 4. **Flexibilitätsband-Analyse**
Berechnung der verfügbaren Be-/Entladepotentiale unter Berücksichtigung:
- **Charge Potential**: Maximale Beladeleistung
- **Discharge Potential**: Maximale Entladeleistung  
- **SoC-Grenzen**: 5% - 95% der Batteriekapazität
- **Lastgang-Safeguarding**: Schutz vor negativen Lastgängen

### 5. **Konstante SoC-Zeiträume**
Identifikation von Zeiträumen mit konstantem State-of-Charge:
- **Minimale Länge**: 6 × 15min = 1.5 Stunden
- **Maximale Länge**: 24 × 15min = 6 Stunden  
- **Automatische Segmentierung** längerer Zeiträume

## ⚡ Strategien-Engine

### 🎯 **Strategie 1: Einfache Lade-Entlade-Strategie**

**Prinzip**: Ausgewogene Be- und Entladung bei preisoptimierten Zeitpunkten

**Algorithmus**:
1. **Preissortierung**: Günstigste Preise für Ladung, teuerste für Entladung
2. **Phasenaufteilung**: 50% Ladephasen, 50% Entladephasen  
3. **Potentialnutzung**: 80% der verfügbaren Flexibilitätspotentiale
4. **Bilanzausgleich**: Start-SoC = End-SoC (±1 kWh Toleranz)

**Einsatzgebiet**: Stabile Preisverläufe, moderate Volatilität

**Mindestanforderung**: ≥ 1.0 Stunden (4 × 15min Intervalle)

```python
# Beispiel-Implementierung
if zeitpunkt in günstige_preise[:n]:
    aktion = charge_potential × 0.8  # Laden bei niedrigen Preisen
elif zeitpunkt in teure_preise[:n]:  
    aktion = discharge_potential × 0.8  # Entladen bei hohen Preisen
```

### ⚡ **Strategie 2: Aggressive Strategie**

**Prinzip**: Maximale Potentialausnutzung für höchste Gewinne

**Algorithmus**:
1. **Erhöhte Potentialnutzung**: 95% der Flexibilitätspotentiale
2. **Mehr Zyklen**: Bis zu 10 Be-/Entladephasen pro Zeitraum
3. **Intensive Nutzung**: Höhere Frequenz der Arbitrage-Aktivitäten
4. **Risiko-Ertrag**: Höhere Gewinne bei intensiverer Batterienutzung

**Einsatzgebiet**: Hohe Preisvolatilität, kurze Arbitrage-Fenster

**Mindestanforderung**: ≥ 1.5 Stunden (6 × 15min Intervalle)

```python
# Beispiel-Implementierung  
aktion = max_potential × 0.95  # 95% Potentialnutzung
anzahl_phasen = min(zeitraum_länge // 2, 10)  # Mehr Zyklen
```

### 🔄 **Strategie 3: Entlade-Lade-Strategie**

**Prinzip**: Sequenzielle Arbitrage - erst entladen, dann beladen

**Algorithmus**:
1. **Zeitraum-Halbierung**: Erste 50% = Entladung, zweite 50% = Beladung
2. **Peak-Shaving**: Entladung bei höchsten Preisen der ersten Hälfte
3. **Valley-Filling**: Beladung bei niedrigsten Preisen der zweiten Hälfte  
4. **Energiebilanz**: Geladene Energie ≤ Entladene Energie
5. **Potentialnutzung**: 70% für ausgewogene Strategie

**Einsatzgebiet**: Vorhersagbare Preismuster, Tageszyklus-Arbitrage

**Mindestanforderung**: ≥ 1.0 Stunden (4 × 15min Intervalle)

```python
# Beispiel-Implementierung
if zeitpunkt < zeitraum_mitte and zeitpunkt in höchste_preise:
    aktion = -discharge_potential × 0.7  # Entladen in erster Hälfte
elif zeitpunkt >= zeitraum_mitte and zeitpunkt in niedrigste_preise:
    aktion = charge_potential × 0.7  # Laden in zweiter Hälfte
```

## 🔧 Technische Constraints

### **SoC-Management**
- **Minimum SoC**: 5% der Batteriekapazität  
- **Maximum SoC**: 95% der Batteriekapazität
- **Start-SoC**: 30% der Batteriekapazität
- **Bilanzierung**: End-SoC = Start-SoC pro Zeitraum

### **Leistungsgrenzen**
- **Charge Potential**: Aus Flexibilitätsband-Analyse
- **Discharge Potential**: Aus Flexibilitätsband-Analyse  
- **Lastgang-Schutz**: Keine negativen Lastgänge

### **Kapazitätsbegrenzung**
```
Maximale Jahreszyklen = Kapazität × Daily_Cycles × 365
Verbrauchte Zyklen = Σ(Positive_Aktionen) / 4 / Kapazität  
```

### **Strategien-Implementierung**
1. **Profit-Optimierung**: Strategien nach Gewinn sortiert
2. **Überlappungsschutz**: Pro Zeitraum nur eine Strategie
3. **Kapazitätsüberwachung**: Stopp bei Erreichung der Jahresgrenze

## 💰 Profit-Berechnung

**Arbitrage-Profit**:
```
Profit = Σ(Eingesparte_Kosten_Entladung) - Σ(Kosten_Beladung)

Für jeden Zeitschritt i:
- Entladung: +|Aktion[i]| × Preis[i] × 0.25h / 100  
- Beladung:  -|Aktion[i]| × Preis[i] × 0.25h / 100
```

**Kosteneinsparung**:
```
Einsparung = Ursprüngliche_DA_Kosten - Optimierte_DA_Kosten
```

## 📊 KPI-Dashboard

### **Strategien-Ergebnisse**
- 🏆 **Anzahl implementierter Strategien**
- 💰 **Gesamtprofit** (€/Jahr)  
- ⚡ **Kapazitäts-Auslastung** (%)
- 📊 **Strategietypen-Verteilung**

### **Lastgang-Optimierung**  
- 📊 **Gesamtverbrauch** (kWh/Jahr)
- ⚡ **Lastspitze** (kW)
- ⬇️ **Niedrigster Bezug** (kW)
- 🔄 **Anzahl Zyklen** pro Jahr

### **Finanzielle Optimierung**
- 💰 **Day-Ahead Kosten** (€/Jahr)
- 💸 **Kosteneinsparung** (€/Jahr)  
- 📊 **Relative Einsparung** (%)
- ⚡ **Kosten pro kWh** (€/kWh)

### **ROI-Metriken**
- 💰 **Einsparung pro kWh Kapazität** (€/(kWh·Jahr))
- 📊 **Payback-Analyse** für Investitionsentscheidungen

## 📁 Dateiformate

### **Input CSV-Format**
```csv
index;timestamp;value
1;2024-01-01 00:00:00;245.67
2;2024-01-01 00:15:00;238.42
...
```

### **Batterie-Parameter JSON**
```json
{
  "capacity_kWh": 1000.0,
  "power_kW": 1000.0, 
  "avg_price_ct_kWh": 0.0896,
  "daily_cycles": 1.5
}
```

### **Strategien-Output JSON**
```json
{
  "strategie_id": 1,
  "zeitraum_id": 15,
  "strategie_typ": "Entlade-Lade",
  "profit_euro": 45.67,
  "strategie_details": [
    {
      "timestamp": "2024-01-01 08:00:00",
      "aktion": -400.0,
      "soc": 650.0, 
      "preis_ct_kwh": 65.4321
    }
  ]
}
```

## 🚀 Installation & Verwendung

### **Voraussetzungen**
```bash
pip install streamlit pandas numpy
```

### **Anwendung starten**
```bash
streamlit run app.py
```

### **Workflow durchführen**
1. **Upload**: CSV-Dateien für Lastgang, PV, Fahrplan, DA-Preise
2. **Konfiguration**: Batteriespeicher-Parameter eingeben
3. **Berechnung**: Alle 8 Schritte der Reihe nach durchführen
4. **Ergebnisse**: KPIs analysieren und CSV-Exports herunterladen

## 🎯 Anwendungsfälle

### **Industriekunden**
- **Lastspitzenreduktion** zur Senkung der Netzentgelte
- **Eigenverbrauchsoptimierung** mit PV-Anlagen
- **Day-Ahead-Arbitrage** zur Kostensenkung

### **Energieversorger**  
- **Portfolio-Optimierung** von Batteriespeicher-Parks
- **Netzstabilisierung** durch intelligente Steuerung
- **Investitionsbewertung** für neue Speicherprojekte

### **Projektentwickler**
- **Feasibility-Studien** für Batteriespeicher-Projekte  
- **ROI-Analysen** für Investoren
- **Optimal Sizing** von Speichersystemen

## 📈 Optimierungspotentiale

Die Anwendung identifiziert systematisch:
- **Profitable Arbitrage-Fenster** im Day-Ahead-Markt
- **Lastspitzenreduktions-Potentiale** zur Netzentgelt-Einsparung  
- **Eigenverbrauchsoptimierung** mit erneuerbaren Energien
- **Kapazitätseffiziente Betriebsstrategien** zur Batterieoptimierung

## 🔮 Erweiterungsmöglichkeiten

- **Machine Learning** für verbesserte Preisprognosen
- **Intraday-Märkte** für zusätzliche Arbitrage-Möglichkeiten  
- **Regelenergie-Märkte** für Zusatzerlöse
- **Multi-Use-Strategien** für komplexe Anwendungsfälle
- **Portfolio-Optimierung** für mehrere Batteriespeicher

---

**🎉 Entwickelt für maximale Day-Ahead-Arbitrage und optimale Batteriespeicher-Wirtschaftlichkeit! 🚀** 