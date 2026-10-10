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
1. Vælg **NQ 12-26** i instrumentlisten til venstre (NQ, ikke MNQ – se nedenfor).
2. Strategy: **HelbertModels**.
3. Data series: **Type = Second, Value = 15**. Trading hours: **CME US Index Futures ETH**.
4. Sammenlign med: **ES 12-26**. Handel paa: **MNQ 12-26** (ordrerne og P&L kommer på MNQ).
5. Start- og slutdato inden for den periode, hvor du har sekunddata
   (tjek under Tools → Historical Data, at der findes 15-sekunders/tick-data for både MNQ og MES).
6. Run → Trades-fanen. Loggen ligger i `Dokumenter\NinjaTrader 8\HelbertModels_log.csv`.

## På chart / live
1. Chart: **NQ 12-26, 15 Second**, Trading hours *CME US Index Futures ETH*, load mindst 10 dage.
2. Højreklik → **Strategies…** → tilføj **HelbertModels**:
   - Sammenlign med: `ES 12-26`
   - Handel paa: `MNQ 12-26` (tom = handler chartets instrument, altså NQ)
   - Koer SMT / Koer Vergence: til/fra
   - SMT: antal kontrakter = **5**, Vergence: antal kontrakter = **5** (standard)
   - Kurvefilter (30) pr. model, startkurve pr. model (seneste papir-R, kommasepareret)
   - Send rigtige ordrer: til = ordrer, fra = kun signaler i loggen
   - Ekstra dage uden trades: fx `2026-12-24`
   - Account: **Sim101** til at starte med.
3. Output-vinduet (New → NinjaScript Output) viser en statuslinje kl. 15:30 hver dag og alle signaler.

## Hvorfor NQ-chart og MNQ-ordrer?
Signalerne skal laves på NQ og ES, som backtesten og dine charts. MNQ og MES har lidt andre 15s-bars
(et tick her og der), og modellen reagerer på et tick. Testet i Strategy Analyzer 2026: NQ+ES gav
næsten de samme trades som backtesten, MNQ+MES gav mange andre. Derfor: NQ-chart, ES som
sammenligning, og ordrerne på MNQ med "Handel paa".

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

## Startkurve til kurvefilteret (live)
Kurvefilteret kigger på de sidste 30 papir-trades. Loader du chartet fra 12/9-2026, så indsæt
backtestens seneste 40 R-værdier (til og med 11/9-2026) som startkurve:

- **SMT:** `7.5,-1.18,-1.3,0,0,0,0,0,7.5,7.5,0,-1,7.5,3.72,-1.75,-2.4,-1,-1,-2.33,7.3,-1.95,-1.05,-1.52,0,5.05,0,4.44,-2.02,7.5,7.5,-1.02,7.5,3.98,-1.42,0,0,-1.75,0,-2.12,-2.8`
- **Vergence:** `0,0,-1.68,0,7.5,0,-1.88,3.72,-1.58,-1.18,4.42,-2.33,-1.32,-1.95,7.5,0,0,-2.65,0,-1.25,-2.98,0,0,7.5,-2.5,7.5,6.88,7.5,-1.8,0,-1.1,-1.9,-1,0,-2.55,7.5,0,0,-2.08,-1.78`

## Strategy Analyzer 2026 (NQ DEC26 + ES 12-26, ordrer på 5 MNQ, 1/1–9/10-2026)
+6.470 $, 76 trades, profit factor 2,01, max drawdown −1.467 $. Samme trades som backtesten,
undtagen SMT 8/1 (TP) og 22/1 (SL), som NinjaTrader ikke tager (sandsynligvis forskel i dataene – ikke undersøgt endnu).
