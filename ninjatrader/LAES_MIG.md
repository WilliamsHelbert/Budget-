# HelbertModels i NinjaTrader 8 (SMT + Vergence)

Én strategi, der kører både SMT og Vergence på samme chart. Hver model har sine egne niveauer,
sine egne dagsregler (max 2 trades, stop efter win) og sit eget kurvefilter.
(Den gamle `HelbertSMT` er erstattet. Har du den i NinjaTrader, kan du slette den.)

## Indsæt koden
1. NinjaTrader 8 → **New → NinjaScript Editor**.
2. Højreklik på **Strategies** → **New Strategy…** → navn `HelbertModels` → Generate.
3. Markér alt i den nye fil (Ctrl+A), slet, og indsæt hele `HelbertModels.txt` (Ctrl+V).
4. Tryk **F5** (compile). Kommer der fejl nederst, så send dem.

## Strategy Analyzer (backtest i NinjaTrader)
Fejlen *"Please select an instrument to run a Backtest on"* betyder, at der ikke er valgt et instrument.
1. Vælg **MNQ 12-26** (eller NQ 12-26) i instrumentlisten til venstre. Instrumentet skal være markeret.
2. Strategy: **HelbertModels**.
3. Data series: **Type = Second, Value = 15**. Trading hours: **CME US Index Futures ETH**.
4. Sammenlign med: **MES 12-26** (eller ES 12-26 hvis du kører NQ).
5. Start- og slutdato inden for den periode, hvor du har sekunddata
   (tjek under Tools → Historical Data, at der findes 15-sekunders/tick-data for både MNQ og MES).
6. Run → Trades-fanen. Loggen ligger i `Dokumenter\NinjaTrader 8\HelbertModels_log.csv`.

## På chart / live
1. Chart: **MNQ 12-26, 15 Second**, Trading hours *CME US Index Futures ETH*, load mindst 10 dage.
2. Højreklik → **Strategies…** → tilføj **HelbertModels**:
   - Sammenlign med: `MES 12-26`
   - Koer SMT / Koer Vergence: til/fra
   - SMT: antal kontrakter = **5**, Vergence: antal kontrakter = **5** (standard)
   - Kurvefilter (30) pr. model, startkurve pr. model (seneste papir-R, kommasepareret)
   - Send rigtige ordrer: til = ordrer, fra = kun signaler i loggen
   - Ekstra dage uden trades: fx `2026-12-24`
   - Account: **Sim101** til at starte med.
3. Output-vinduet (New → NinjaScript Output) viser en statuslinje kl. 15:30 hver dag og alle signaler.

## Regler i strategien
- Vindue 15:30–16:00 dansk tid, 3-6-9-minutter for SMT, tid close, SL 10–30, TP 35–75, BE-regler som backtesten.
- EQ før open gør ikke tradet ugyldigt (kan slås til).
- Ingen trades på dage hvor New York-børsen er lukket (helligdage 2023–2028 er lagt ind),
  eller hvis NY PRE mangler data (fx CME-nedbrud 28/11-2025).
- Aabner den ene model et trade modsat et åbent rigtigt trade fra den anden model, tages det nye kun på papir.

## Testet
Hele 20/6-2023 → 11/9-2026 kørt gennem strategien (NQ/ES 15s) giver præcis de samme trades som backtesten:

| | Trades | R | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| SMT uden filter | 223 | +102,1 | +32,4 | −55,2 | +80,5 | +44,4 |
| SMT kurvefilter 30 | 158 | +132,5 | +32,4 | −11,5 | +67,3 | +44,4 |
| Vergence uden filter | 216 | +86,4 | +7,6 | +12,0 | +40,3 | +26,5 |
| Vergence kurvefilter 30 | 167 | +65,4 | +8,6 | +8,1 | +29,7 | +19,0 |

(R = 10 point. Med 5 MNQ er 1R = $100.)
