# Kilder til de to kausalkæder

**Grundprincip:** en kausalkæde er din egen analyse. Du skal ikke finde en kilde,
der siger præcis det, kæden siger — så havde det ikke været dit arbejde. Du skal
have kilde på hvert **led**: tallene og teorien. Selve sammenkædningen er din.

Nedenfor er hvert led delt op i tre typer:

- **TAL** — skal have kildehenvisning til et datasæt
- **TEORI** — skal have kildehenvisning til lærebogen
- **EGEN ANALYSE** — skal ikke have kilde, det er din egen slutning

---

## Kausalkæde 1: Fra svag yen til svagt forbrug

| Led | Type | Kilde |
|---|---|---|
| Svag yen (110 → 151 yen pr. dollar) | TAL | Bank of Japan eller FRED, serie AEXJPUS. **Endnu ikke verificeret** — se ark `Kildekritik` |
| → import bliver dyrere | TEORI | Lærebogen om valutakursens betydning for import- og eksportpriser |
| → forbrugerpriserne stiger (2,5 % i 2022, 3,2 % i 2023) | TAL | OECD Economic Outlook — jeres eget ark |
| → at det er importeret inflation | EGEN ANALYSE | Din slutning ud fra gabet mellem inflation (2,5 %) og kerneinflation (0,3 %). Teorien bag kerneinflation: **lærebogens afsnit 18.1** |
| → lønnen stiger ikke lige så meget | TAL | **MANGLER.** Se nedenfor |
| → japanerne kan købe mindre for deres løn | TEORI | Lærebogen om realløn. **Afsnit 23.1** |
| → de bruger af opsparingen | EGEN ANALYSE | Din slutning ud fra at opsparingen falder samtidig med at forbruget stiger |
| → opsparingen falder fra 7,7 % til 1,8 % | TAL | OECD Economic Outlook — jeres eget ark |
| → forbruget vokser kun 0,7 % | TAL | OECD Economic Outlook — jeres eget ark |

**Kæden er solid.** Ét led mangler dokumentation: lønudviklingen. Det er række
40-41 i arket, som stadig er tom.

---

## Kausalkæde 2: Fra demografi til manglende lønstigninger

| Led | Type | Kilde |
|---|---|---|
| Færre børn og en ældre befolkning | TAL | **MANGLER HELT.** Jeres ark har ingen demografiske tal |
| → arbejdsstyrken bliver mindre | TAL | **MANGLER HELT.** Række 50 i arket er tom |
| → der er færre ledige | TEORI | Lærebogen om arbejdsstyrke og beskæftigelse. **Afsnit 6.4** |
| → arbejdsløsheden falder til 2,4 % | TAL | OECD Economic Outlook — jeres eget ark |
| → virksomhederne har heller ikke brug for flere | **SVAGT LED** | Se nedenfor |
| → der opstår ikke kamp om arbejdskraften | EGEN ANALYSE | Følger af leddet ovenfor |
| → lønnen stiger ikke særlig meget | TAL | **MANGLER — og er omstridt.** Se nedenfor |
| → forbruget stiger ikke | TAL | OECD Economic Outlook — jeres eget ark |

### Kæde 2 er svagere end kæde 1. To problemer:

**Problem 1: Ledet om at virksomhederne ikke har brug for flere.**
Det er en påstand, jeg har skrevet uden at have data på det. Det er sandsynligt,
men du kan ikke belægge det med noget, du har lige nu. Enten finder du tal på
efterspørgslen efter arbejdskraft — i Japan bruger man *jobs-to-applicants
ratio*, altså antal ledige stillinger pr. jobsøgende — eller også skriver du
leddet om, så det ikke påstår mere, end du kan vise.

**Problem 2: Shunto-tallene taler imod kæden.**
De japanske overenskomstforhandlinger, shunto, gav omkring 5 % i lønstigning i
både 2024 og 2025. Det ser umiddelbart ud, som om lønnen *er* steget meget.
Forklaringen er, at shunto kun dækker fagligt organiserede i store virksomheder,
og at 5 % inkluderer almindelige anciennitetsstigninger. Men **du bliver nødt til
at nævne det og forklare det** — ellers har du en analyse, der falder, hvis
censor kender tallet.

Det er faktisk en styrke at tage det med. At vise et modargument og forklare,
hvorfor det ikke vælter din konklusion, er præcis det, der løfter karakteren.

---

## Hvor teorien står i jeres egen lærebog

Tabel 21.1 i lærebogen henviser selv til de afsnit, hvor hvert nøgletal er
gennemgået. Det er de nemmeste kildehenvisninger, I kan lave:

| Nøgletal | Afsnit i lærebogen |
|---|---|
| Økonomisk vækst | 1.1, 3.2 og 3.3 |
| Arbejdsløshed | 6.4 |
| Betalingsbalance | 10.1 |
| Eksport / import | 22.1, 22.2 og 24.1 |
| Offentlige finanser | 7.2, 7.3 og 7.4 |
| Inflation | 18.1 |
| Løn | 23.1 |
| Rente | 12.4 |

Fodnoteformat for en iBog, jf. vejledningen:
> Forfatter, "kapitlets titel", år [LINK]

---

## Hvad du skal hente — i prioriteret rækkefølge

1. **Lønudvikling** (bruges i begge kæder). OECD Data Explorer → *Average annual
   wages*. Eller Japans MHLW → *Monthly Labour Survey* → real wage index.
2. **Befolkning og arbejdsstyrke** (bærer hele kæde 2). Statistics Bureau of
   Japan → *Population Estimates* og *Labour Force Survey*. Globalis har danske
   sider om Japans befolkning, hvis du vil have noget lettere tilgængeligt.
3. **Valutakurs** (første led i kæde 1). Bank of Japan, eller FRED serie AEXJPUS.
4. **Jobs-to-applicants ratio**, hvis du vil redde det svage led i kæde 2.
5. **Kvalitativ kilde om japansk løndannelse** — hvorfor lønnen ikke reagerer.
   Det kan tallene ikke forklare. Søg på *shunto wage negotiations*, *lifetime
   employment Japan*, *non-regular workers Japan*.

Punkt 5 er værd at bruge tid på. Metodematerialet lægger vægt på
**metodetriangulering**, altså at man kombinerer kvantitativ og kvalitativ data.
Kæde 2 er præcis et sted, hvor tallene rejser spørgsmålet, men kun en artikel
eller rapport kan besvare det.

---

## Ærligt forbehold

Jeg har ikke kunnet åbne OECD, IMF, Bank of Japan eller de japanske
statistikbureauer fra dette miljø — de er blokeret af netværkspolitikken. Tal for
valutakurs, shunto og styringsrente stammer fra søgeresultater og er **ikke
verificeret mod primærkilden**. De står markeret som sådan i arket. Du skal selv
slå dem op, før de kommer i rapporten.
