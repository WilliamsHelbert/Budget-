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
6. **Til backtest: tøm de to startkurver og "Startkurverne gaar til og med"** (ellers står kurvefilteret stille
   på 9/10-2026-kurven og tager ikke de trades med, der ligger før den dato).
7. Run → Trades-fanen. Loggen ligger i `Dokumenter\NinjaTrader 8\HelbertModels_log.csv`.

## På chart / live (uge 42, fra mandag 12/10-2026)
1. Chart: **NQ 12-26, 15 Second**, Trading hours *CME US Index Futures ETH*.
   Højreklik → Data Series → **Days to load: 20** (skal mindst gå tilbage til 12/10-2026, se startkurven nedenfor).
2. Højreklik → **Strategies…** → tilføj **HelbertModels**. Standardindstillingerne er de rigtige:
   - Sammenlign med: `ES 12-26`, Handel paa: `MNQ 12-26`
   - Koer SMT og Koer Vergence: til
   - SMT og Vergence: **5** kontrakter hver
   - Kurvefilter (30): til på begge
   - Startkurver: allerede udfyldt (til og med 9/10-2026), "Startkurverne gaar til og med" = `2026-10-09`
   - EQ foer open ramt = ugyldigt: fra. TP ved liquidity 35-75: til
   - Send rigtige ordrer: til
   - Account: **Sim101** i den første uge
   - Under *Properties*: **Start behavior = Wait until flat**, og sæt **Enabled** ✓
3. Strategien skal være tændt fra før 15:30 dansk tid. Kl. 15:30 skriver den en statuslinje i
   Output-vinduet (New → NinjaScript Output) og i `Dokumenter\NinjaTrader 8\HelbertModels_status.txt`.
   Alle signaler (også papir-trades) står i `HelbertModels_log.csv` i samme mappe. Send de to filer efter hver dag.
4. Rollover: NQ/ES/MNQ 12-26 udløber 18/12-2026. Skift til **03-27** på alle tre omkring **10/12-2026**.

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
Kurvefilteret kigger på de sidste 30 papir-trades pr. model. Startkurverne er lagt ind i koden:
backtestens sidste 40 R pr. model til og med fredag 9/10-2026. Trades på chartet til og med den dato
tæller ikke med igen, så det er ligegyldigt, hvor mange dage du loader – bare chartet går mindst tilbage til 12/10-2026.
Begge modeller står over snittet efter 9/10, så det næste SMT- og Vergence-trade er **rigtigt**.

Testet i C#-strategien: startkurve til og med 28/6-2024 og data fra 20/5-2024 giver præcis samme
rigtig/papir-markering som backtesten i resten af 2024 (60 trades, heraf 41 papir).

- **SMT:** `0,0,0,0,7.5,7.5,0,-1,7.5,3.72,-1.75,-2.4,-1,-1,-2.33,7.3,-1.95,-1.05,-1.52,0,5.05,0,4.44,-2.02,7.5,7.5,-1.02,7.5,3.98,-1.42,0,0,-1.75,0,-2.12,-2.8,0,6.31,-1.3,-1.72`
- **Vergence:** `0,-1.68,0,7.5,0,-1.88,3.72,-1.58,-1.18,4.42,-2.33,-1.32,-1.95,7.5,0,0,-2.65,0,-1.25,-2.98,0,0,7.5,-2.5,7.5,6.88,7.5,-1.8,0,-1.1,-1.9,-1,0,-2.55,7.5,0,0,-2.08,-1.78,-1.72`

Startes strategien senere (fx efter en uge), kan du lade startkurverne og datoen stå,
så længe chartet loader alle dage siden 12/10-2026.

## Strategy Analyzer 2026 (NQ DEC26 + ES 12-26, ordrer på 5 MNQ, 1/1–9/10-2026)
+6.470 $, 76 trades, profit factor 2,01, max drawdown −1.467 $. Samme trades som backtesten,
undtagen SMT 8/1 (TP) og 22/1 (SL), som NinjaTrader ikke tager (sandsynligvis forskel i dataene – ikke undersøgt endnu).
