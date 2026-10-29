# NQ FVG-motoren

Motoren tager Williams NQ-model (sweep, reaktion og inversion) og kører den på 15s-data. Ud kommer en CSV og en HTML-rapport med alle trades.
Setup-reglerne er tunet på hans oktober 2026. Med entry på signalet finder de 23 af hans 24 trades fra 1.–19. oktober, og den sidste (13/10 11:08) er ugyldig efter reglerne.
Siden 26/10-2026 tager motoren entry med en limit i 0,705 (golden pocket) og fuld TP på session-liq. Det er den kombination af entry, SL og TP, der klarede sig bedst over 2022–2026 uden ekstra filtre.

## Kør den

```bash
cd <repo>                      # roden af williamshelbert/budget-
python3 -m pip install pandas pyarrow numpy   # hvis de mangler
python3 backtest/nq_motor/motor.py 2026-10-01 2026-10-19 \
    --ud /mnt/project-files/backtest/nq_motor/okt2026 --titel "NQ oktober 2026"
```

- `fra` og `til` er datoer (YYYY-MM-DD). Hver hverdag i perioden bliver kørt.
- `--ud` er mappen, hvor `trades.csv` og `rapport.html` havner.
- `--data` bruges til andre parquet-filer. De skal have kolonnerne `time` (UTC), `open`, `high`, `low` og `close` med 15s-bars. Står der flere filer, erstatter en senere fil perioden, den dækker.
- `--tf 5` lader kun 5m FVG'er give entry (standard er `--tf 5 4 3 2 1`). 5m bruges altid til benet og sweepet.
- `--range 10 0.25 0.75`: ingen short, når entry ligger under 0,25, og ingen long over 0,75 i rangen (high/low) af de seneste 10 afsluttede CME-dage. Setuppet springes over som ved for lav RR. Testet 25/10-26: gør resultatet dårligere (−33,8R på al data).
- `--trend 10`: kun long, når NQ er steget over de seneste 10 afsluttede CME-dage, og kun short, når den er faldet.
- `--gp 0` slår limit-entry fra, `--partial` slår 25% ud på 4h til, og `--h4tp` bruger 4h som TP uden session-liq.
- CSV og rapport har `rr`: afstand til TP **ved entry** (`tp_start`) delt med risiko.
- `--ingen-rapport` springer HTML-rapporten over. Over 150 trades viser rapporten kun tabel og måneder, ikke et chart pr. trade.
- Mangler `pyarrow` (og kan den ikke installeres), læser motoren selv parquet-filerne med `backtest/parquet_lite.py` (zstd via systemets libzstd, snappy, gzip). Resultatet er det samme.
- Oktober tager ca. 20 sekunder på 4 kerner. Lange perioder deles automatisk over alle kerner.

**Kontrol:** 2026-10-01 → 2026-10-19 skal give **16 trades, +28,71R, 31% vundne**. Med `ENTRY_GP = None`, `PARTIAL = True` og `H4_TP = True` (den gamle motor) giver den 24 trades og +13,98R. Giver den noget andet, er data eller regler ændret.

### Data

| Fil | Indhold |
|---|---|
| `/mnt/project-files/data/NQ_samlet_15s.parquet` | NQ 15s fra 14/9-2022 til 19/10-2026 kl. 15:08 NY. Der mangler bars i sep/okt 2026. |
| `/mnt/project-files/data/NQ_2026-09-01_2026-10-09_15s.parquet` | Lapper hullet fra 1/9 til 9/10-2026. |

Begge filer bliver læst som standard. Data slutter 19/10-2026, så nyere dage kræver ny data via `--data`.

## Tider

Data og kode bruger New York-tid. **DK = NY + 6 timer** (i de få uger om året, hvor sommertid skifter forskelligt, er det 5 timer).
Entry-tiden i CSV og rapport er DK-tid for **closen** på inversions-candlen.
William noterer candlens **åbning**, så hans journal-tid ligger en candle tidligere (fx 15:55 hos ham og 16:00 i motoren for en 5m-candle).

## Standard fra 28/10-2026

Valgt for mindst drawdown over 2022–2026 (597 trades, +140,6R, max drawdown −15,9R; 2026: 140 trades, +24,6R):

- **Kun sweeps af ét liq-niveau** (`KUN_1_LIQ`). Et sweep, der tager flere på én gang (fx "Asia + 4h"), giver ingen trade.
- **Kun dagens første trade** (`FOERSTE_TRADE`, DK-dag).
- **Entry på signalet** (`ENTRY_GP = None`), ikke limit i 0,705.
- **Fast TP** (`FAST_TP`): TP sættes ved entry og flyttes ikke af en session lavet i tradet.
- **SL til +1R ved +2R** (`TRAIL = (2.0, 1.0)`). Ingen partial.

De gamle regler køres med `--alle-liq --alle-trades --flyt-tp --ingen-trail` (oktober giver så igen 24 trades, +13,65R).

Standard er `--rr 1.5 99` (fra 28/10-2026). `--rr MIN MAX` tager kun trades, hvor RR til start-TP ligger mellem MIN og MAX. Et setup udenfor springes over, og dagens næste setup kan tages. Over 2022–2026 gav `--rr 2 99` +155,0R (DD −15,3R) og `--rr 1.5 99` +147,6R (DD −14,4R); et loft (max 6/10) smider de store vindere væk og gør det værre.

## Standard fra 29/10-2026

Oven i reglerne ovenfor:

- **Min 1,5R til start-TP** (`RR_GR = (1.5, 99)`). Under 1,5R (eller over 99R, hvor SL kun er få punkter) springes setuppet over, og dagens næste setup kan tages.
- **Spring dagen over 08–14 DK** (`SKIP_TID = (8, 14)`). Ligger dagens første setup fra 08:00 til 14:00 DK, tages der intet den dag. Slås fra med `--skip-tid 0 0`.

Over 2022–2026: 379 trades, +144,6R, max drawdown −10,5R (2025–26: +71,7R, DD −10,0R).

Test-flag (standard slået fra): `--liq-alder MIN` (liq skal være mindst MIN min gammelt), `--ingen-tid FRA TIL` (ingen entries i tidsrummet, men dagens næste setup kan tages), `--max-sl PCT` (loft på SL i % af prisen). Ingen af dem hjalp.

## Reglerne

Short er beskrevet her. Long er det samme spejlvendt. Forløbet for en short: benet går ned og sweeper et low, reaktionen går op ind i benets gaps, og der shortes på inversion af et gap i reaktionen.

1. **Liq:** Asia (20:00–02:00 NY), London (02:00–08:00 NY), PDH/PDL (forrige CME-dag), gårsdagens Asia/London og 4h-candles (offset 2h) en uge tilbage. Et niveau kan kun sweepes én gang (`CONSUME`).
2. **Benet:** Benet går ned fra et high til lowet. De to **nyeste** 5m FVG'er (bearish) i benet, lavet til og med sweep-candlen, er dem, der tæller (`GAP_RECENT`, `SWEEP_GAPS`, `LEG_MID`). Gaps har ingen minimumsstørrelse. Fyldte gaps tæller stadig.
3. **Inverseret gap er ugyldigt:** Får et 5m gap en close på den anden side, før liq bliver taget, tæller det ikke (`GAP_NOINV`). Sker det efter sweepet, er det bare reaktionen.
4. **Sweep:** Prisen tager et low (liq) og laver en 5m close tilbage over det (`RECLAIM`).
5. **Modsat session:** Tager prisen et session-high (short) eller session-low (long) på den anden side, før der er entry, er setuppet dødt (`OPP_SESS`).
6. **2 timer:** Kommer der ingen entry inden for 2 timer efter sweepet, dør setuppet, men benet lever videre, og et nyt sweep i samme ben kan give en trade (`MAX_SWEEP_RESET`, `KEEP_LEG`).
7. **Signal:** Reaktionen op skal nå ind i begge 5m gaps. Signalet kommer, når en candle (1–5m) **closer mindst 1 point** under det ældste bullish gap i reaktionen (`OLDEST`, `INV_MIN=1`). Den højeste timeframe vinder, så et 5m gap lavet til sidst efter sweepet bliver brugt.
   **Entry:** En limit 0,705 af vejen fra signalets close op mod SL (`ENTRY_GP = 0.705`). Bliver den ikke fyldt inden 22:55 DK, eller når prisen TP først, er der intet trade. Risikoen er derfor kun ca. 30% af afstanden fra signalet til SL.
8. **SL:** Toppen af reaktionen.
9. **TP**, i denne rækkefølge:
   1. Nærmeste uberørte Asia/London/PDH/PDL (i dag eller i går) mindst 1R væk.
   2. Ellers den nærmeste **gamle session** (Asia/London), der ikke er taget siden, uanset hvor langt tilbage. William gør det samme.
   3. Ellers 4R (ATH, hvor der intet liq er). 4h-niveauer bruges ikke som TP (`H4_TP = False`).

   TP vælges ud fra signalet, så 1R betyder afstanden fra signalet til SL. R i resultatet regnes fra den rigtige entry.

   Bliver en ny Asia/London færdig under tradet, og ligger dens low (short) i profit og tættere end TP, bliver den ny TP.
10. **Ingen partial:** Hele positionen går til TP (`PARTIAL = False`). Med `PARTIAL = True` tages 25% ud på high/low af en 4h-candle, der lukker under tradet.
11. **Lukketid:** Alt lukkes 16:55 NY = 22:55 DK.
12. Der kan være flere trades om dagen. Et nyt setup kan starte, når forrige trade er ude.

Setup-reglerne står som flag i `CFG` øverst i `motor.py` og bruges af `backtest/fvg_model.py`. Resultat-reglerne er `ENTRY_GP`, `PARTIAL`, `H4_TP`, `OLD_SESS` og `EXIT` i `motor.py`. CSV'en har både signalets tid og pris (`signal_dk`, `signal_entry`) og den rigtige entry.

## Åbne punkter (ikke kodet endnu)

- **1-times-reglen:** Et 4h-low/high eller session-liq skal være mindst 1 time gammelt, før det kan sweepes til et trade. William vil vurdere den senere. Den ville fjerne 16/10 13:35 short.
- **Gammel liq over dagsskiftet:** Gårsdagens sessions tæller som liq (fx 14/10 03:25). Hvorvidt det er en god idé, skal vurderes på september og på de lange data fra 2023.

## Filer

- `motor.py`: regler, kørsel, TP/udfald og CSV.
- `rapport.py` og `stil.html`: HTML-rapporten (nøgletal, equity-kurve, tabel, regler og et 5m-chart pr. trade).
- `../parquet_lite.py`: reserve-læser til parquet, når pyarrow mangler.
- `../fvg_model.py`: selve setup-motoren (ben, gaps, sweep og inversion).
