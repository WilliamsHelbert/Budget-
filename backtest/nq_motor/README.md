# NQ FVG-motoren

Motoren tager Williams NQ-model (sweep, reaktion og inversion) og kører den på 15s-data. Ud kommer en CSV og en HTML-rapport med alle trades.
Den er tunet på hans oktober 2026. Den finder 23 af hans 24 trades fra 1.–19. oktober, og den sidste (13/10 11:08) er ugyldig efter reglerne.

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
- `--ingen-rapport` springer HTML-rapporten over. Over 150 trades viser rapporten kun tabel og måneder, ikke et chart pr. trade.
- Mangler `pyarrow` (og kan den ikke installeres), læser motoren selv parquet-filerne med `backtest/parquet_lite.py` (zstd via systemets libzstd, snappy, gzip). Resultatet er det samme.
- Oktober tager ca. 20 sekunder på 4 kerner. Lange perioder deles automatisk over alle kerner.

**Kontrol:** 2026-10-01 → 2026-10-19 skal give **24 trades, +13,98R, 54% vundne**. Giver den noget andet, er data eller regler ændret.

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

## Reglerne

Short er beskrevet her. Long er det samme spejlvendt. Forløbet for en short: benet går ned og sweeper et low, reaktionen går op ind i benets gaps, og der shortes på inversion af et gap i reaktionen.

1. **Liq:** Asia (20:00–02:00 NY), London (02:00–08:00 NY), PDH/PDL (forrige CME-dag), gårsdagens Asia/London og 4h-candles (offset 2h) en uge tilbage. Et niveau kan kun sweepes én gang (`CONSUME`).
2. **Benet:** Benet går ned fra et high til lowet. De to **nyeste** 5m FVG'er (bearish) i benet, lavet til og med sweep-candlen, er dem, der tæller (`GAP_RECENT`, `SWEEP_GAPS`, `LEG_MID`). Gaps har ingen minimumsstørrelse. Fyldte gaps tæller stadig.
3. **Inverseret gap er ugyldigt:** Får et 5m gap en close på den anden side, før liq bliver taget, tæller det ikke (`GAP_NOINV`). Sker det efter sweepet, er det bare reaktionen.
4. **Sweep:** Prisen tager et low (liq) og laver en 5m close tilbage over det (`RECLAIM`).
5. **Modsat session:** Tager prisen et session-high (short) eller session-low (long) på den anden side, før der er entry, er setuppet dødt (`OPP_SESS`).
6. **2 timer:** Kommer der ingen entry inden for 2 timer efter sweepet, dør setuppet, men benet lever videre, og et nyt sweep i samme ben kan give en trade (`MAX_SWEEP_RESET`, `KEEP_LEG`).
7. **Entry:** Reaktionen op skal nå ind i begge 5m gaps. Entry sker, når en candle (1–5m) **closer mindst 1 point** under det ældste bullish gap i reaktionen (`OLDEST`, `INV_MIN=1`). Den højeste timeframe vinder, så et 5m gap lavet til sidst efter sweepet bliver brugt.
8. **SL:** Toppen af reaktionen.
9. **TP**, i denne rækkefølge:
   1. Nærmeste uberørte Asia/London/PDH/PDL (i dag eller i går) mindst 1R væk.
   2. Ellers den nærmeste **gamle session** (Asia/London), der ikke er taget siden, uanset hvor langt tilbage. William gør det samme.
   3. Ellers nærmeste uberørte 4h mindst 1R væk.
   4. Ellers 4R (ATH, hvor der intet liq er).

   Bliver en ny Asia/London færdig under tradet, og ligger dens low (short) i profit og tættere end TP, bliver den ny TP.
10. **25% ud:** Lukker en 4h-candle, mens tradet er åbent, og prisen bagefter når dens low (short) eller high (long) før SL/TP, tages 25% ud der. Så er R = 0,25·R(4h) + 0,75·R(resten). CSV'en har begge tal.
11. **Lukketid:** Alt lukkes 16:55 NY = 22:55 DK.
12. Der kan være flere trades om dagen. Et nyt setup kan starte, når forrige trade er ude.

Setup-reglerne står som flag i `CFG` øverst i `motor.py` og bruges af `backtest/fvg_model.py`. Resultat-reglerne er `PARTIAL`, `OLD_SESS` og `EXIT` i `motor.py`.

## Åbne punkter (ikke kodet endnu)

- **1-times-reglen:** Et 4h-low/high eller session-liq skal være mindst 1 time gammelt, før det kan sweepes til et trade. William vil vurdere den senere. Den ville fjerne 16/10 13:35 short.
- **Gammel liq over dagsskiftet:** Gårsdagens sessions tæller som liq (fx 14/10 03:25). Hvorvidt det er en god idé, skal vurderes på september og på de lange data fra 2023.

## Filer

- `motor.py`: regler, kørsel, TP/udfald og CSV.
- `rapport.py` og `stil.html`: HTML-rapporten (nøgletal, equity-kurve, tabel, regler og et 5m-chart pr. trade).
- `../parquet_lite.py`: reserve-læser til parquet, når pyarrow mangler.
- `../fvg_model.py`: selve setup-motoren (ben, gaps, sweep og inversion).
