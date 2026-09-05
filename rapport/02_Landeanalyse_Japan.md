# Makroøkonomisk landeanalyse af Japan, 2020–2025

Det her er arbejdsdokumentet — ikke rapportteksten. Formålet er at finde ud af,
**hvad historien i tallene faktisk er**, så vi bagefter ved, hvad rapporten skal
handle om. Metoden er den fra kapitel 21: hold nøgletallene op mod holdepunkterne
i tabel 21.1, og byg kausalkæder mellem dem.

---

## Trin 1: Nøgletallene holdt op mod holdepunkterne (tabel 21.1)

| Nøgletal | Japan 2025 | Holdepunkt (tabel 21.1) | Dom |
|---|---|---|---|
| BNP-vækst | 1,2 pct. | Stabil vækst = 1–2 pct. Under 1 pct. = lavkonjunktur | **I bunden af det normale.** Snubler let ned i lavkonjunktur |
| Ledighed | 2,4 pct. | Fuld beskæftigelse ved 3–4 pct. Under 3 pct. = rimeligt lav | **Under fuld beskæftigelse.** Arbejdsmarkedet er stramt |
| Inflation | 2,0 pct. | Centralbankernes målsætning er ca. 2 pct. | **Præcis på målet** — men se kæde B, vejen dertil er problemet |
| Betalingsbalance | +4,0 pct. af BNP | Overskud over 6 pct. er problematisk (EU's Sixpack) | **Sundt overskud.** Ingen ekstern finansieringsrisiko |
| Eksport vs. import | 2,4 vs. 2,0 pct. | Eksportvæksten bør overstige importvæksten | **Opfyldt** — men marginalt |
| Offentlig saldo | −3,3 pct. af BNP | Underskud på 1–3 pct. er acceptabelt kortvarigt | **Lige over grænsen** efter fem års forbedring |
| Offentlig gæld | 243,8 pct. af BNP | Tommelfingerreglen er højst 60 pct. af BNP | **Fire gange over.** Det mest ekstreme tal i hele arket |
| Løn | *mangler* | Bør ligge på niveau med handelspartnerne | Skal skaffes |
| Rente | *mangler* | Følger typisk inflation + risiko | Skal skaffes |

**Første observation:** Isoleret set ser Japan fint ud. Vækst i det normale
interval, inflation på målet, meget lav ledighed, overskud på betalingsbalancen.
Kun ét tal skriger: gælden.

Men den isolerede læsning er netop ikke en landeanalyse. Analysen ligger i
**sammenhængene** — og der falder billedet fra hinanden.

---

## Trin 2: Fire kausalkæder

### Kæde A — Væksten kommer udefra, ikke indefra

Vækstbidragene (pct.point, beregnet i `01_Datatjek_af_Excel.md`):

| År | Privat forbrug | Off. forbrug | Investeringer | Nettoeksport | Lager |
|----|---|---|---|---|---|
| 2021 | 0,22 | 0,73 | 0,05 | **1,00** | 0,20 |
| 2022 | 1,08 | 0,25 | −0,26 | −0,60 | 0,40 |
| 2023 | 0,38 | 0,10 | 0,43 | **0,80** | −0,20 |
| 2024 | 0,38 | −0,06 | **0,66** | 0,20 | −0,20 |
| 2025 | 0,38 | 0,00 | **0,72** | 0,10 | 0,00 |

Læg mærke til det centrale misforhold: **privatforbruget udgør 54 pct. af
økonomien, men bidrager kun 0,38 pct.point om året.** Investeringerne udgør 25,6
pct. og bidrager næsten dobbelt så meget. Nettoeksporten udgør netto −0,3 pct. af
BNP og har i 2021 og 2023 bidraget mere end nogen anden komponent.

> Svag indenlandsk efterspørgsel → væksten må hentes i nettoeksport og
> investeringer → økonomien bliver afhængig af udenlandsk efterspørgsel og
> valutakurs → væksten bliver sårbar over for forhold, Japan ikke selv styrer.

Dertil: det offentlige forbrug går fra +3,5 pct. (2021, coronahjælp) til −0,3
pct. (2024) og 0 (2025). **Finanspolitikken strammes**, samtidig med at
forbrugeren står stille. Der er ingen indenlandsk motor tilbage.

### Kæde B — Den importerede inflation, der åd reallønnen

Her er det mest interessante i hele materialet.

| | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| Forbrugerpriser | −0,2 | 2,5 | 3,2 | 2,6 | 2,0 |
| Kerneinflation | −0,7 | 0,3 | 2,7 | 2,3 | 2,0 |
| **Forskel** | +0,5 | **+2,2** | +0,5 | +0,3 | 0,0 |
| Opsparingskvote | 7,7 | 5,4 | 3,3 | 3,4 | **1,8** |

I 2022 stiger forbrugerpriserne 2,5 pct., mens kerneinflationen kun er 0,3 pct.
Kerneinflation er inflation uden energi og fødevarer. At kløften er 2,2
pct.point betyder, at **inflationen i 2022 var importeret** — energi- og
fødevarepriser, forstærket af en svækket yen — og ikke skabt af japansk
efterspørgsel. I 2023 lukker kløften: kerneinflationen springer til 2,7 pct.
Nu er de importerede prisstigninger væltet videre ind i den brede økonomi.

Og så det tal, der binder det hele sammen: **opsparingskvoten falder fra 7,7 pct.
til 1,8 pct. af den disponible indkomst.**

Man kan regne baglæns fra arkets egne tal. Hvis forbruget vokser 0,7 pct. realt,
priserne stiger 3,2 pct., og opsparingskvoten samtidig falder fra 5,4 til 3,3
pct., så må den disponible indkomst kun være vokset ca. 1,7 pct. nominelt — altså
et **realt fald på ca. 1,5 pct. i 2023**:

| År | Nominel disp. indkomst (afledt) | Forbrugerpriser | **Realt** |
|---|---|---|---|
| 2022 | +2,0 pct. | 2,5 | −0,5 pct. |
| 2023 | +1,7 pct. | 3,2 | **−1,5 pct.** |
| 2024 | +3,4 pct. | 2,6 | +0,8 pct. |
| 2025 | +1,0 pct. | 2,0 | **−0,9 pct.** |

*(Overslag. Beregnet som Y = C/(1−s) med forbrugerprisindekset som deflator.
Skal verificeres mod faktiske løndata, jf. de manglende rækker.)*

> Svag yen + globale energipriser → importeret inflation → priserne stiger
> hurtigere end lønnen → reallønsfald → husholdningerne skal vælge mellem at
> skære i forbruget eller tære på opsparingen → de tærer på opsparingen
> (7,7 → 1,8 pct.) → forbrugsvæksten holdes kunstigt oppe på beskedne 0,7 pct.

**Og her er pointen, som gør det til en problemstilling frem for en beskrivelse:
det kan ikke fortsætte.** En opsparingskvote på 1,8 pct. er tæt på gulvet. Den
stødpude, der har holdt japansk privatforbrug i live siden 2021, er brugt op.
Falder reallønnen igen, er der ikke mere at tære på — så rammer det forbruget
direkte, og så forsvinder de 0,38 pct.point.

### Kæde C — Det stramme arbejdsmarked, der ikke skaber lønpres

Ledigheden falder fra 2,8 til 2,4 pct. Efter tabel 21.1 er alt under 3 pct.
"rimeligt lav" — Japan ligger under det, man normalt kalder fuld beskæftigelse.

Efter almindelig makroøkonomisk teori burde det udløse lønpres: knaphed på
arbejdskraft → virksomhederne byder lønnen op → højere indkomster → højere
forbrug. **Det sker ikke.** Forbruget vokser 0,7 pct. om året, og reallønnen
falder (kæde B).

Det er en ægte modsætning, og den kræver en forklaring uden for tallene:

- **Demografien.** Arbejdsstyrken skrumper. Når både udbud af og efterspørgsel
  efter arbejdskraft falder, kan ledigheden være lav uden at der opstår pres.
  Den lave ledighed måler her *befolkningstilbagegang*, ikke et stærkt
  arbejdsmarked.
- **Løndannelsens indretning.** Livstidsansættelse og senioritetsbaseret løn i
  de store virksomheder, kombineret med en stor gruppe ikke-fastansatte, gør
  lønnen langt mindre følsom over for knaphed end i fx Danmark.
- **Forventningsdannelsen.** Efter tre årtier med deflation og nulvækst i lønnen
  forhandles der ikke, som om inflationen var kommet for at blive.

> Faldende arbejdsstyrke → lav ledighed uden knaphedspres → træg løndannelse →
> reallønnen følger ikke med inflationen → svagt privatforbrug → væksten må
> komme fra eksport og investeringer (tilbage til kæde A)

Bemærk, at kæde C forklarer kæde B, som forklarer kæde A. **Det er den røde tråd
i analysen.**

### Kæde D — 244 pct. gæld i en verden, hvor renten er ved at vende

Gælden ligger fladt på 240–245 pct. af BNP, mens underskuddet forbedres fra −6,2
til −3,3 pct. Hvorfor falder gældskvoten så ikke?

Fordi den holdes nede af **nominel** BNP-vækst:

| År | Realvækst | BNP-deflator | **Nominel BNP-vækst** | Gæld i pct. af BNP |
|---|---|---|---|---|
| 2021 | 2,2 | −0,2 | 2,0 | 240,0 |
| 2022 | 0,9 | 0,3 | 1,2 | 245,6 |
| 2023 | 1,7 | 3,5 | **5,2** | 244,8 |
| 2024 | 1,0 | 2,6 | 3,6 | 244,8 |
| 2025 | 1,2 | 2,2 | 3,4 | 243,8 |

I 2022, hvor den nominelle vækst kun er 1,2 pct., **stiger** gældskvoten med 5,6
pct.point. Fra 2023, hvor deflatoren springer til 3,5 pct., stabiliseres den.
Det er ikke en tilfældighed: så længe den nominelle vækst overstiger den
gennemsnitlige rente på gælden, æder væksten gældskvoten hurtigere, end
underskuddet bygger den op. **Inflationen er, kynisk sagt, det, der holder den
japanske statsgæld i skak.**

Og det er præcis derfor, det er skrøbeligt:

> Bank of Japan normaliserer pengepolitikken → renten på statsobligationer
> stiger → med en gæld på 244 pct. af BNP koster 1 pct.point højere
> gennemsnitsrente ca. **2,4 pct. af BNP** i ekstra renteudgifter, når gælden er
> refinansieret → til sammenligning er hele budgetforbedringen fra 2021 til 2025
> kun 2,9 pct.point → én pct.points rentestigning kan altså slette fem års
> konsolidering

Samtidig: en højere japansk rente styrker yennen → svækker eksportens
konkurrenceevne → rammer nettoeksporten, som er den ene af de to
vækstkomponenter, der stadig virker (kæde A). Og en lavere rente holder yennen
svag → holder den importerede inflation i gang → holder reallønnen nede (kæde B).

**Japan sidder i en klemme, hvor begge veje ud gør ondt.** Det er der, jeres
diskussion og vurdering skal ligge.

---

## Trin 3: Hvad rapporten skal handle om

Forløbet hedder *"Handel i et konkurrencepræget perspektiv"*. Sammenholder man
det med, hvad tallene faktisk viser, peger alt ét sted hen:

> **Japan har fået en billigere valuta og dermed en forbedret
> priskonkurrenceevne — men det har ikke skabt velstand. Det har importeret
> inflation, som har udhulet reallønnen og tvunget husholdningernes
> opsparingskvote fra 7,7 til 1,8 pct.**

Det er en modsætning, og vejledningen til rapportskrivning siger netop, at en god
problemstilling gerne må være en modsætning eller en konflikt ("hvordan kan det
være at…"). Det er ikke en beskrivelse, der kan besvares med et opslag — det
kræver, at man kobler flere nøgletal.

### Delkonklusion til analysen

Japans centrale økonomiske usikkerheder er:

1. **Væksten er udliciteret til udlandet.** Med et privatforbrug på 54 pct. af
   BNP, der kun bidrager 0,38 pct.point, hviler væksten på nettoeksport og
   investeringer. Det gør konjunkturen afhængig af global efterspørgsel og af
   yennens kurs.
2. **Forbrugets stødpude er brugt.** Opsparingskvoten kan ikke falde meget
   længere. Uden reallønsstigninger falder forbrugsbidraget bort.
3. **Gældens stabilitet hviler på, at renten forbliver lav.** Ved 244 pct. af BNP
   er rentefølsomheden så høj, at pengepolitisk normalisering i sig selv er en
   finanspolitisk trussel.
4. **Demografien er den underliggende årsag** til både den lave ledighed uden
   lønpres og den svage indenlandske efterspørgsel.

Punkt 1–3 er de tre, rapporten skal bære. Punkt 4 hører hjemme i redegørelsen som
baggrund.

---

## Hvad vi mangler for at kunne skrive det

| Mangler | Bruges til | Kilde |
|---|---|---|
| Nominel lønudvikling 2020–2025 | Dokumentere reallønsfaldet i kæde B direkte i stedet for at aflede det | OECD.Stat, Average annual wages |
| JPY/USD og effektiv valutakurs | Selve konkurrenceevne-mekanismen | Bank of Japan |
| Pengepolitisk rente + 10-årig JGB-rente | Kæde D | Bank of Japan / OECD |
| Bytteforholdet (terms of trade) | Vise, at eksportfremgangen delvis er en prisillusion | OECD Economic Outlook |
| Befolkning/arbejdsstyrke | Kæde C, redegørelsen | OECD / Globalis |
| Kvalitative kilder om løndannelse og *shunto*-forhandlingerne | Forklare kæde C. Analysen kan ikke forklares med tal alene | Artikler, fx Nikkei, Financial Times, danske erhvervsmedier |

De sidste er vigtige. Metode-materialet lægger vægt på **metodetriangulering** —
kvantitativ og kvalitativ data i kombination. Kæde C er præcis et sted, hvor
tallene rejser spørgsmålet, men kun kvalitative kilder kan besvare det.
