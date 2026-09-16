# EQ + SMT — overlevering

Skrevet 16-09-2026. Opdateret 16-09-2026 efter partner-EQ-rettelsen.
Læs denne først. Den indeholder det der er afgjort, det der er bevist
forkert, og det der stadig er åbent.

---

## 1. Filerne

| Fil | Hvad |
|---|---|
| `eq_model.py` | EQ-konfluensmotoren. Rører ES og NQ samtidig. |
| `smt_model.py` | SMT (Session Sweep), port af Pine v10. **PARKERET.** |
| `koer_alt.py` | Kører begge og skriver `alle_trades.csv`. |
| `databento_konverter3.py` | Databento OHLCV-1s → 15s parquet, ét år pr. fil. |
| `del_op.py` | Deler en parquet i bidder under 30 MB. |

Kør:

```
python koer_alt.py sti/til/datamappe
```

### Dataformat — vigtigt, konverteren og motoren taler ikke samme sprog

`databento_konverter3.py` skriver **ikke** det format motoren læser. Den
skriver `ES_2025.parquet` med:

- kolonnen `ts` — epoch-sekunder som `int32`
- priser som **heltal i ticks** (`pris / 0.25`), ikke i point

Motoren (`_prep`) forventer `ES.parquet` med kolonnen `time` som UTC-
datetime og priser i **rigtige point**. Der mangler altså et mellemtrin:
slå årene sammen, omdøb `ts` → `time`, og gang priserne med 0,25.

Sker det ikke, er ES-priser 4× for høje, og 8/40-reglen måler i ticks
i stedet for point. Alt bliver forkert uden at fejle.

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

### Den faste enhed er ikke din RR

TP er 7,5 R **i den faste enhed**, men risikoen pr. handel svinger med
stoppet. Den faktiske reward:risk er TP divideret med stoppet:

| ES-benet | Median | Snit | Min | Max |
|---|---:|---:|---:|---:|
| Stopafstand | 3,50 pt | 3,90 pt | 0,75 | 8,00 |
| Risiko i R-enheder | 1,75 | 1,95 | — | 4,00 |
| **Sand RR** | **4,29** | **4,80** | 1,88 | 20,00 |

Du handler altså i snit **4,8:1**, ikke 7,5:1.

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

**EQ'ernes levetid**
- Når en EQ bliver raidet, ankrer den sig selv.
- **Begge aktivers EQ'er er ude af drift fra det øjeblik en handel
  udløses, og indtil handlen er ude i SL, BE eller TP.** Derefter
  starter de forfra.

**Break-even**
- Nærmeste **LEVENDE** 5m-likviditet i gevinstretningen, låst ved entry.
- Et 5m-lys' low bliver et niveau når lyset lukker. Det **dør** når prisen
  handler igennem det. Døde niveauer tæller ikke.
- Niveauer fra hele døgnet tæller, ikke kun fra 15:30.

**8/40-reglen**
- Både stoppet og BE-afstanden skal være ≤ 8 point på ES og ≤ 40 på NQ.
  Ellers er handlen **ugyldig** (ikke udskudt, ikke beskåret).

**Take profit** — 15 ES-point / 75 NQ-point. Fast.

**Intet dagsstop.**

---

## 4. Resultater — rettet model, nov 2024 – feb 2026

341 dage Databento, 249 handler.

| Ben | R | pr. handel | maxDD | TP | SL | BE | profitfaktor | t |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NQ | +11,08 | +0,04 | −39,80 | 31 | 105 | 113 | 1,05 | +0,23 |
| **ES** | **+98,50** | +0,40 | −22,00 | 39 | 113 | 97 | 1,51 | **+1,94** |

År for år, ES: 2024 nov–dec +13,25 · 2025 +73,75 · 2026 jan–feb +11,50.

**Beslutning: der handles ES.** Samme signaler, ni gange resultatet.

### Drawdown-profilen — det her er den vigtige tabel

| Nedture fra en top | Antal | I USD |
|---|---:|---:|
| Under −5 R | 9 | −1.000 |
| **Under −10 R** | **5** | −2.000 |
| Under −15 R | 2 | −3.000 |
| Under −20 R | 2 | −4.000 |

De fem episoder under −10 R:

| Start | Bund | Dybde | Handler | Kom sig |
|---|---|---:|---:|---|
| 2024-11-29 | 2024-12-17 | −14,75 R | 14 | 2025-02-25 |
| 2025-02-28 | 2025-05-06 | **−22,00 R** | 19 | 2025-05-29 |
| 2025-06-03 | 2025-07-09 | −21,50 R | 25 | 2025-08-15 |
| 2025-09-01 | 2025-09-17 | −14,62 R | 15 | 2025-09-18 |
| 2025-11-10 | 2025-12-09 | −13,25 R | 9 | 2025-12-15 |

**85 % af alle handler foregår i drawdown.** Kun 15 % sker på en ny top.
Længste periode under vand: 50 handler.

### Drawdownen er strukturel, ikke uheld

Ved 15,7 % TP-rate er sandsynligheden for højst 1 TP i 19 handler
**17,8 %**, og der er 231 overlappende 19-vinduer i datasættet. En tørke
som den værste er ikke usædvanlig — den er garanteret. Værste enkelttab
er kun −4,00 R. Drawdownen kommer fra tørke i træfprocenten, ikke fra
halerisiko, og den kan ikke fjernes uden at ændre udbetalingsstrukturen.

### Advarsel om tallet
Der er nu kørt ca. 55 konfigurationer på de samme data. t = 1,94 er ikke
et frit fund. **Modellen er ikke bevist.**

---

## 5. Fejl der er fundet og rettet — gentag dem ikke

**Partnerens EQ blev aldrig brugt op.** `eq_model.py:253` dræbte EQ'en når
et aktiv raidede sin *egen* linje, men når aktivet var konfluens-partner
blev dets EQ kun aflæst, aldrig nulstillet. Partnerens anker blev derfor
genbrugt hele dagen mens ekstremet løb videre, så stoppet voksede uden
loft. 8. januar 2026 gav samme NQ-anker (25803,00) tre setups med stop på
98,00 → 129,50 → **167,00** point. Værste tilfælde i datasættet: 659 point.
Bivirkning: den forældede EQ blokerede også for at nye EQ'er kunne fødes
(`:269`, `:277` kræver `bear[k] is None`).
Rettelse: begge EQ'er bruges op ved entry og er ude af drift til handlen
er færdig. Median-afvigelse mod journalen: +21,00 → **+1,25 point**.

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
`eq_model.py:21` har stadig `TZ = "Europe/Copenhagen"` som modulstandard —
den overskrives af `koer_alt.py:44`. **Kør altid gennem `koer_alt.py`.**

**ms mod ns i parquet.** `dbfull`-filerne har `datetime64[ms]`.
`astype('int64') // 10**9` giver da vrøvl. Brug
`.astype('datetime64[s]').astype('int64')`. Har allerede ramt to scripts.

---

## 6. Hvad journalen viste

18 MEQ-handler, 8.–16. januar 2026, −15,125 R i alt. 12 shorts, 6 longs.

Motoren armer 15 af de 18 inden for ét minut, 13 med samme retning.
Entry-logikken er rigtig.

**Ankerreglen er bekræftet korrekt.** Før rettelsen delte de matchede
setups sig i to rene grupper efter hvem der udløste:

| Dato | Udløser | Journal | Model før | Model efter |
|---|---|---:|---:|---:|
| 01-08 15:50 | ES | 31,25 | 167,00 | **30,75** |
| 01-09 15:49 | ES | 37,50 | 59,50 | 59,50 |
| 01-13 15:32 | NQ | 27,50 | 28,75 | 28,75 |
| 01-14 15:40 | NQ | 25,00 | 25,25 | 25,25 |
| 01-14 15:47 | NQ | 27,50 | 23,50 | 23,50 |
| 01-15 15:58 | — | 17,50 | 41,00 | 44,75 |
| 01-16 15:33 | ES | 16,25 | 37,25 | 37,25 |

Hver gang NQ raidede sin egen EQ, ramte modellen journalen inden for 4
point — også før rettelsen. Afvigelserne lå udelukkende på partner-benet.

**Åbent:** tre ES-udløste setups afviger stadig 21–27 point. Restfejlen er
ikke fundet.

---

## 7. Ting der er testet og IKKE virker

Pålidelige, fordi de ikke er udvalgte fund — de blev testet og fejlede.

| Idé | ES-resultat (basis +98,50) |
|---|---:|
| Stop efter første tab på dagen | +71,00 |
| Kun én handel per dag | +52,38 |
| Fjern BE helt | +98,00 R, men maxDD **−22,00 → −36,38** |
| Tættere TP (1,5–6,0 R) | Monotont dårligere |
| Konstant risiko (skalér efter stopbredde) | R uændret, maxDD **−11,29 → −15,74** |
| **Stoploft på 3 R** | Forkert præmis — se nedenfor |
| Longs med | +30,22, men kun hvis de deler kø med shorts. Samtidigt: −10,08 |

**BE-reglen er dit drawdown-værktøj, ikke et profit-værktøj.** Den koster
0,50 R i total og halverer drawdownen. Rør den ikke.

**3R-stoploftet er afvist.** Præmissen var at brede ankre er dårlige
risikobeslutninger. Data siger det modsatte, monotont:

| Stopbredde (ES) | n | R pr. handel | SL-andel |
|---|---:|---:|---:|
| 0,75–2,75 pt | 75 | +0,185 | 63 % |
| 2,75–3,50 pt | 56 | +0,373 | 43 % |
| 3,50–5,25 pt | 61 | +0,498 | 39 % |
| 5,25–8,00 pt | 57 | **+0,586** | **32 %** |

Et bredt anker betyder at EQ'en har strakt sig — det er et stærkt
strukturelt signal. Skærer man toppen af, skærer man i de bedste handler.

Handel nr. 2 på dagen er den **bedste** (+0,70 pr. handel mod +0,24 for nr. 1).

---

## 8. Åbne idéer — ingen af dem er validerede

### Delgevinst + mindstestop (den bedst begrundede)

MFE-måling viser en ren adskillelse: BE-handlerne når median **2,00 R** i
din favør før de vender, mens SL-handlerne dør ved **0,62 R**. Kun 8 % af
taberne når 2 R mod 54 % af BE-handlerne. De 97 BE-handler, der i dag
lander på præcis 0,00 R, er den største uudnyttede pulje i modellen.

| Variant | n | R | maxDD | Calmar | <−10 R | t |
|---|---:|---:|---:|---:|---:|---:|
| Basis | 249 | +98,50 | −22,00 | 4,48 | 5 | +1,94 |
| Delgevinst ½ ved 1,0 R | 249 | +70,38 | −11,94 | 5,90 | 4 | +2,28 |
| Mindstestop 2,5 ES-pt | 196 | +98,62 | −19,12 | 5,16 | 5 | +2,09 |
| **Begge dele** | 196 | **+72,62** | **−10,00** | **7,26** | **1** | **+2,52** |

Kombinationen halverer drawdownen og går fra fem til én episode under
−10 R, men koster 26 R i total.

**Det er et best-of-mange-valg.** Delgevinstniveauet er ikke monotont
(1,0 R bedst, 1,5–2,5 dårligere, 3,0 lidt bedre igen), hvilket er
kendetegnet ved støj. Med ~55 konfigurationer bag sig er t = 2,52 cirka
hvad ren støj producerer. **Skal valideres på 2022/2023 før det bruges.**

### Efterhåndsfund — brug dem IKKE uden nye data
- 15:40–15:50 alene står for +84,62 af de +99,38 (t = 2,56)
- Setups med NQ-stop 32–41 point taber penge (t = −0,23)
- Dage med tre handler: 7 dage, −25,38 R på NQ

---

## 9. Hvad der skal ske nu

Hent **2022 og 2023** fra Databento med `databento_konverter3.py`. Det er
data ingen har rørt.

Lås opsætningen først, skriftligt — inklusive om delgevinst og
mindstestop er med. Så kør den **én gang**. Det tal er det første
ærlige tal.

Justerer man efter at have set det, er det ikke længere et
out-of-sample-tal.

---

## 10. SMT — PARKERET

Ikke i arbejde. Tallene står her så de ikke går tabt.

86 handler på fuld døgndata nov 2024 – feb 2026: **−34,15 R**, t = −1,88.
SL 42 · BE 37 · TP 7. Den taber penge som den står og skal ikke handles.
Reproduceret præcist 16-09-2026.

Kendte fejl rettet undervejs: død-niveau-tjekket testede kun NQ ·
korrelations-gaten blev aldrig anvendt · blokering talte 5m-niveauer med ·
stop målt på løbende 1-minuts-ekstrem i stedet for 15s-lysets ekstrem.

Uløst: 27. april 2026 skulle fjernes af regel C, men bliver det ikke.
Journalen har 142 SMT-handler; der har kun været data til 41.

---

## 11. Data

Motoren forventer `ES.parquet` + `NQ.parquet` pr. mappe:
`time` (UTC), `open`, `high`, `low`, `close`, 15s-barer i **point**,
frontkontrakt volumenrullet, spreads og micros fjernet.
Se afsnit 1 om mellemtrinnet fra konverterens format.

**Datafilerne ligger ikke i repoet** (parquet er i `.gitignore`).

Verificeret 16-09-2026: nov 2024 – feb 2026, 341 handelsdage, døgndækning
02:00–22:09 dansk tid, ca. 4.750 af 5.760 mulige 15s-barer pr. dag.
ES 5.724–6.994, NQ 16.486–26.398. Ingen RTH-klipning.

**2026 marts–september mangler.** De tal i den gamle udgave af dette
dokument (+11,38 for jan–sep 2026, 286 handler) kom fra en separat
NinjaTrader-kilde. Databento-sættet dækker kun til 27. februar 2026.
Sammenholdt betyder det at **marts–september 2026 tilsammen gav −0,12 R
på syv måneder** — 2026-svagheden er ikke jævnt fordelt, den er
fuldstændig stilstand efter februar.
