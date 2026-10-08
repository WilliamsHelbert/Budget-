# HelbertSMT i NinjaTrader 8

1. Åbn NinjaTrader 8 → **New → NinjaScript Editor**.
2. Højreklik på **Strategies** → **New Strategy…** → giv den navnet `HelbertSMT` → Finish (eller Generate).
3. Markér ALT i den nye fil (Ctrl+A) og slet det. Indsæt hele indholdet af `HelbertSMT.txt` (Ctrl+V).
4. Tryk **F5** (compile). Står der fejl nederst, så send dem.
5. Åbn et chart: **NQ 12-26, 15 Second**, Trading hours *CME US Index Futures ETH*, load mindst 10 dage.
6. Højreklik i chartet → **Strategies…** → tilføj **HelbertSMT**:
   - Sammenlign med (ES): `ES 12-26`
   - Antal kontrakter / risiko i $
   - Kurvefilter til/fra, Startkurve (dine seneste papir-R, kommasepareret)
   - Send rigtige ordrer: til = ordrer, fra = kun signaler i loggen
   - Account: **Sim101** til at starte med.
7. Alle signaler logges i `Dokumenter\NinjaTrader 8\HelbertSMT_log.csv`.

## Test
- **Strategy Analyzer**: NQ 12-26 (eller NQ 03-26 osv.), Second 15, 2026 → kør → eksportér trades + send `HelbertSMT_log.csv`.
- **Market Replay**: 24/2, 30/3, 9/4 (intet trade) og 6/1 (short 15:30:30).
- **Sim101** live i 2–4 uger før rigtige penge.

Testet her: samme 2026-data kørt gennem strategien giver præcis samme 29 trades og +54,71R som backtesten.
