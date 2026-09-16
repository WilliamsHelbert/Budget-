# EQ + SMT — overlevering

Skrevet 16-09-2026. Læs denne først. Den indeholder det der er afgjort,
det der er bevist forkert, og det der stadig er åbent.

---

## 1. Filerne

| Fil | Hvad |
|---|---|
| `eq_model.py` | EQ-konfluensmotoren. Rører ES og NQ samtidig. |
| `smt_model.py` | SMT (Session Sweep), port af Pine v10. **Ikke færdig.** |
| `koer_alt.py` | Kører begge og skriver `alle_trades.csv`. |
| `databento_konverter3.py` | Databento OHLCV-1s → 15s parquet, ét år pr. fil. |
| `del_op.py` | Deler en parquet i bidder under 30 MB. |

Kør:

```
python koer_alt.py sti/til/datamappe
```

Datamappen skal have `ES.parquet` og `NQ.parquet`: 15s-barer, kolonnerne
`time` (UTC), `open`, `high`, `low`, `close`. **Fuld døgndata** — mindst
02:00–22:10 dansk tid. SMT har brug for Asien og London.

---

## 2. Enheder — læs den her, den har kostet tid før

```
1 R  = 10 NQ-point = 2 ES-point = 200 USD
TP   = 75 NQ-point = 15 ES-point = 7,5 R
```

**R er en fast enhed, ikke risiko-normaliseret.** Et stop 25 point væk
giver −2,5 R. Et stop 37,5 point væk giver −3,75 R. Tabene varierer.

Journalens `r`-kolonne følger samme konvention: `r = −3.125` betyder et
stop 31,25 point væk.

---

## 3. EQ-reglerne som de er låst nu

**Setup**
- Bear-EQ fødes når et 1m-lys lukker bearish OG under sit eget (H+L)/2.
  Ankeret er lysets high. Linjen = (anker + løbende ekstrem) / 2.
- Begge aktiver skal have aktiv EQ i samme retning.
- Ét aktiv rører sin EQ-linje uden at lukke igennem → setup armet.
- Bekræftelse: et 15s-lys hvor begge aktiver lukker samme vej.

**Indgang**
- Kun 15:30–16:00 dansk tid. **Kun shorts** — longs er helt ude.
- Er der en åben position, er næste setup **ugyldigt** (ikke udskudt).

**Stop**
- På EQ-toppen (ankeret).

**Break-even**
- Nærmeste **LEVENDE** 5m-likviditet i gevinstretningen, låst ved entry.
- Et 5m-lys' low bliver et niveau når lyset lukker. Det **dør** når prisen
  handler igennem det. Døde niveauer tæller ikke.
- Niveauer fra hele døgnet tæller, ikke kun fra 15:30.

**8/40-reglen**
- Både stoppet og BE-afstanden skal være ≤ 8 point på ES og ≤ 40 på NQ.
  Ellers er handlen ugyldig.

**Take profit** — 15 ES-point / 75 NQ-point. Fast.

**Intet dagsstop.**

---

## 4. Resultater, nov 2024 – sep 2026 (341 dage Databento + 2026 NinjaTrader)

286 handler:

| Ben | R | pr. handel | maxDD | TP | SL | BE | t |
|---|---:|---:|---:|---:|---:|---:|---:|
| NQ | +30,03 | +0,10 | −39,80 | 39 | 121 | 126 | +0,56 |
| **ES** | **+99,38** | +0,35 | −29,50 | 44 | 133 | 109 | **+1,84** |

År for år, ES: 2024 nov–dec +13,25 · 2025 +74,75 · 2026 jan–sep +11,38.

**Beslutning: der handles ES.** Samme signaler, tre gange resultatet.

### Advarsel om tallet
Der blev kørt ca. 40 konfigurationer på de her data. t = 1,84 er ikke
et frit fund. Og 2026 er kun +11,38 på ni måneder mod 2025's +74,75.
**Modellen er ikke bevist.**

---

## 5. Fejl der er fundet og rettet — gentag dem ikke

**BE lå på død likviditet.** Den gamle regel tog extremet på det senest
afsluttede 5m-lys uden at tjekke om prisen allerede havde handlet igennem
det. Niveauet lå derfor næsten altid 8–12 point fra entry, og stoppet blev
flyttet med det samme. 58 % af handlerne fik flyttet stop.
Effekt: +128,21 R → +34,55 R.

**RTH-filteret i datakonverteren.** Det gamle Databento-træk indeholdt kun
barer fra 15:25 og frem. Modellen kunne derfor ikke se natteniveauer, og
85 setups blev aldrig gyldige. De 85 taber 49,67 R. Filteret var ikke en
regel — det var databeskæring der virkede som et skjult filter.
**Brug altid fuld døgndata.**

**Dagsstop på −2,5 R.** Fandtes ikke i journalen. 9. jan 2026 endte dagen
på −6,25 R, 14. jan på −5,25 R, og hver post har `afterDailyLossLimit:
false`. Dagsstoppet var tilføjet af modellen, ikke af traderen.

**Tidszone.** Motoren SKAL køre i `America/New_York`. Amerikansk sommertid
starter ~3 uger før europæisk (2026: 8. marts mod 29. marts). Kører man i
Europe/Copenhagen, handler man 10:30–11:30 NY i 15 dage i marts.

**ms mod ns i parquet.** `dbfull`-filerne har `datetime64[ms]`.
`astype('int64') // 10**9` giver da vrøvl. Brug
`.astype('datetime64[s]').astype('int64')`. Har allerede ramt to scripts.

---

## 6. Hvad journalen viste

18 MEQ-handler, 8.–16. januar 2026, −15,125 R i alt.

**Motoren armer 17 af de 18 inden for ét minut. 14 med samme retning.**
Entry-logikken er altså rigtig. De blev kasseret af 8/40-loftet, fordi
modellens stop på EQ-anchoren i snit er 2,1× bredere end journalens
(median 37,25 mod 26,25 point).

Journalens stop lå mellem 16,25 og 37,50 point. Aldrig over.

**Åbent spørgsmål:** hvorfor er modellens anker bredere end det traderen
bruger? SL-reglen er bekræftet som "toppen af EQ", men tallene stemmer
ikke på halvdelen af setupsene. Det er det vigtigste uløste punkt.

---

## 7. Ting der er testet og IKKE virker

Pålidelige, fordi de ikke er udvalgte fund — de blev testet og fejlede.

| Idé | ES-resultat (basis +99,38) |
|---|---:|
| Stop efter første tab på dagen | +71,00 |
| Kun én handel per dag | +52,38 |
| Fjern BE helt | +98,38 |
| Tættere TP (1,5–6,0 R) | Monotont dårligere |
| Longs med | Longs giver +30,22, men kun hvis de deler kø med shorts. Får de lov at køre samtidig: −10,08 |

Handel nr. 2 på dagen er den **bedste** (+0,70 pr. handel mod +0,24 for nr. 1).

---

## 8. Åbne idéer — ingen af dem er validerede

**Stoploft på 3 R (6 ES-point).** Den bedst begrundede. Ingen af de 44
vindere gik mere end 2,75 R imod entry. Taberne gik 2,00 R i median og op
til 6,25. Et loft på 3,0 R dræber ingen kendt vinder og skærer 25 % af
taberne. Mekanismen: ankeret er en strukturel top, ikke en risikobeslutning.

**Efterhåndsfund — brug dem IKKE uden nye data:**
- 15:40–15:50 alene står for +84,62 af de +99,38 (t = 2,56)
- Setups med NQ-stop 32–41 point taber penge (t = −0,23)
- Dage med tre handler: 7 dage, −25,38 R på NQ

Begge de første er 3- og 4-vejs opdelinger fundet bagefter på 286 handler.
Med 40 forsøg bag sig er t = 2,5 cirka hvad ren støj producerer.

---

## 9. Hvad der skal ske nu

Hent **2022 og 2023** fra Databento med `databento_konverter3.py`. Det er
data ingen har rørt.

Lås opsætningen først, skriftligt. Så kør den **én gang**. Det tal er det
første ærlige tal.

Justerer man efter at have set det, er det ikke længere et out-of-sample-tal.

---

## 10. SMT — status

**Ikke færdig.** Bedste kørsel: 40 handler mod journalens 41 for jan–feb
2026. +35,08 R mod journalens +86,60 R. 16 har samme dag og tidspunkt,
8 har identisk R.

Kendte fejl der er rettet undervejs:
- Død-niveau-tjekket testede kun NQ
- Korrelations-gaten blev aldrig anvendt (stille fejl)
- Blokering talte 5m-niveauer med (R: −11,22 → +1,33)
- Stop blev målt på løbende 1-minuts-ekstrem i stedet for 15s-lysets
  ekstrem (R: +1,33 → +21,48, snit-tab −2,92 → −1,92)

**Kørt på fuld døgndata nov 2024 – feb 2026 (341 dage):**
86 handler, **−34,15 R**, t = −1,88. SL 42 · BE 37 · TP 7.
Den taber altså penge som den står. Den skal ikke handles.

**Uløst:** 27. april 2026 skulle fjernes af regel C, men bliver det ikke.

Regel C: prisen må ikke sweepe BE'erne session-liq og EQ. Men bliver 25 %
af EQ eller 15m/5m-liq taget, og det skulle have været brugt til BE, så
springer man videre til næste BE-kandidat.

Journalen har 142 SMT-handler. Der har kun været data til 41 af dem,
fordi de gamle filer var RTH-klippede. Med fuld døgndata kan resten testes.

---

## 11. Data

Motoren forventer `ES.parquet` + `NQ.parquet` pr. mappe:
`time` (UTC), `open`, `high`, `low`, `close`, 15s-barer, frontkontrakt
volumenrullet, spreads og micros fjernet.

`databento_konverter3.py` laver dem. Ca. 11 MB pr. år pr. symbol.

Verificeret mod hinanden: Databento mod NinjaTrader matcher high/low
99,7 %. To Databento-træk matcher 99,66 %, og hele afvigelsen ligger på
rulledagen 15. september 2025.
