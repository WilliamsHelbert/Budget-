// =====================================================================
//  HelbertModels  -  NinjaTrader 8 strategi (SMT + Vergence)
//  ---------------------------------------------------------------
//  Direkte oversaettelse af backtesten (backtest/smt_backtest.py),
//  backtest/SMT_REGELBOG.md og backtest/REGLER.md, oktober 2026.
//  De to modeller koerer hver for sig (egne niveauer, egne dagsregler,
//  eget kurvefilter) paa samme chart.
//
//  OPSAETNING
//    - Laeg strategien paa et MNQ- eller NQ-chart med 15 SEKUNDERS bars
//      (Data Series: MNQ 12-26, Type Second, Value 15, Trading hours:
//      "CME US Index Futures ETH"). MES/ES hentes automatisk (CompareSymbol).
//    - Load mindst 10 dage (gerne 1 aar) saa sessioner og kurvefilter er klar.
//    - Calculate = On bar close (saettes automatisk).
//
//  SIKKERHED
//    - Kun handler i vinduet 09:30-10:00 New York-tid (15:30-16:00 dansk).
//    - Max 2 trades pr. dag pr. model, stop modellen efter vundet trade.
//    - Ingen trades paa dage hvor New York-boersen er lukket, eller hvis
//      NY PRE (08:00-09:30) mangler data (fx CME-nedbrud 28/11-25).
//    - Aabner den ene model et trade modsat et AABENT rigtigt trade fra den
//      anden model, tages det nye kun paa papir (ingen modsatte ordrer).
//    - Alle signaler (ogsaa papir-trades) skrives i en CSV-log:
//      Dokumenter\NinjaTrader 8\HelbertModels_log.csv
// =====================================================================
#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Windows.Media;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class HelbertModels : Strategy
    {
        // ───────────── faste regler (som backtesten) ─────────────
        private const double TICK = 0.25;
        private const int ASIA_S = 20 * 60, ASIA_E = 2 * 60;
        private const int LON_S = 2 * 60, LON_E = 8 * 60;
        private const int NY_S = 8 * 60, NY_E = 9 * 60 + 30;
        private const int WIN_S = 9 * 60 + 30, WIN_E = 10 * 60;
        private const int M15_END = 9 * 60 + 31;
        private const double MIN_SL = 10, MAX_SL = 30, TP_MIN = 35, TP_MAX = 75, BE_MIN = 2, BE_MAX = 50;
        private const int VRG_GAP = 5;          // Vergence: max minutter mellem de to indeks' foerste take af samme niveau
        private const int NYPRE_MIN_BARS = 300; // NY PRE har 360 15s-bars; faerre end 300 = data mangler -> ingen trades

        // New York-boersen lukket (ingen 09:30-open) - ingen trades
        private static readonly HashSet<string> NyseClosed = new HashSet<string> {
            "2023-01-02","2023-01-16","2023-02-20","2023-04-07","2023-05-29","2023-06-19","2023-07-04","2023-09-04","2023-11-23","2023-12-25",
            "2024-01-01","2024-01-15","2024-02-19","2024-03-29","2024-05-27","2024-06-19","2024-07-04","2024-09-02","2024-11-28","2024-12-25",
            "2025-01-01","2025-01-09","2025-01-20","2025-02-17","2025-04-18","2025-05-26","2025-06-19","2025-07-04","2025-09-01","2025-11-27","2025-12-25",
            "2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25","2026-06-19","2026-07-03","2026-09-07","2026-11-26","2026-12-25",
            "2027-01-01","2027-01-18","2027-02-15","2027-03-26","2027-05-31","2027-06-18","2027-07-05","2027-09-06","2027-11-25","2027-12-24",
            "2028-01-17","2028-02-21","2028-04-14","2028-05-29","2028-06-19","2028-07-04","2028-09-04","2028-11-23","2028-12-25" };

        // ───────────── typer ─────────────
        private class St
        {
            public long aM = -1, bM = -1, aT = -1, bT = -1;
            public bool aDone, bDone, aTook, bTook, aTgT, bTgT, aPre;
            public double aLv = double.NaN, bLv = double.NaN;   // Vergence: niveauet efter det er taget = indeksets yderpunkt
        }
        private class Sess
        {
            public double aHi = double.NaN, aLo = double.NaN, bHi = double.NaN, bLo = double.NaN;
            public St hi, lo;
            public long aHiM = -1, bHiM = -1, aLoM = -1, bLoM = -1;
            public double aTgH = double.NaN, bTgH = double.NaN, aTgL = double.NaN, bTgL = double.NaN;
            public bool maHi, mbHi, maLo, mbLo;
        }
        private class Lv
        {
            public double a, b; public bool isHi, dead; public long tm = -1; public St st = new St();
        }
        private class VArm
        {
            public bool shrt; public double va = double.NaN, vb = double.NaN; public string names; public long t;
        }
        private class Hit
        {
            public bool fired, isShort, swHi, swLo, sHi, sLo;
            public double lvl = double.NaN; public string src = "", who = "";
            public List<VArm> varm = new List<VArm>();
        }
        private class VTrade
        {
            public bool shrt, beHit, early, noBE, real;
            public double entry, sl, sl0, tp, be = double.NaN;
            public int bars; public string date, time, src, who, beSrc, tpSrc;
        }
        private class VF { public long m; public double lvl; public string key; public bool used; }
        private class VSide
        {
            public List<VF> aF = new List<VF>(), bF = new List<VF>();
            public long aE = -1, bE = -1, aFM = -1, bFM = -1, xT = -1;
            public double aFL = double.NaN, bFL = double.NaN;
            public bool isNew, had;
            public void Reset()
            {
                aF.Clear(); bF.Clear(); aE = bE = aFM = bFM = xT = -1;
                aFL = bFL = double.NaN; isNew = had = false;
            }
        }
        private struct NBar { public long t; public double o, h, l, c; }

        // ═════════════ EEN MODEL (SMT eller Vergence) ═════════════
        private class Engine
        {
            public readonly HelbertModels S; public readonly bool vrg; public readonly string tag;
            public int contracts; public bool useCurve;
            public Engine(HelbertModels s, bool isVrg) { S = s; vrg = isVrg; tag = isVrg ? "VRG" : "SMT"; }

            private Sess asia = new Sess(), lon = new Sess(), ny = new Sess();
            private List<Lv> lv15 = new List<Lv>(), lv05 = new List<Lv>();
            private bool prevA, prevL, prevN;
            private int prevMn = -1;
            public double m1Hi = double.NaN, m1Lo = double.NaN;
            private long prevQ15 = -1, prevQ5 = -1;
            private double aq15Hi, aq15Lo, bq15Hi = double.NaN, bq15Lo = double.NaN;
            private double aq5Hi, aq5Lo, bq5Hi = double.NaN, bq5Lo = double.NaN;
            private long q15Start = -1, q5Start = -1;

            // EQ
            private long lastMin = -1;
            private double[] curMin;
            private bool dAct, uAct;
            private double dTop, dBot, uTop, uBot;
            private double pDT = double.NaN, pDB = double.NaN, pUB = double.NaN, pUT = double.NaN;
            private long preDHitM = -1, preUHitM = -1;
            private string resetDay = "";
            private List<KeyValuePair<long, double>> hitsD = new List<KeyValuePair<long, double>>(), hitsU = new List<KeyValuePair<long, double>>();
            private List<KeyValuePair<long, double>> hitsSH = new List<KeyValuePair<long, double>>(), hitsSL = new List<KeyValuePair<long, double>>();

            // Vergence
            private VSide vHi = new VSide(), vLo = new VSide();
            private string vDay = "";
            private List<VArm> vArms = new List<VArm>();

            // minut / dag
            private long curM = -1; private bool mHi, mLo, mBad;
            private long lastTradeM = -1;
            private string tradeDay = ""; private int dayCount; private bool dayWin;
            public VTrade o;
            public List<double> curve = new List<double>();
            public double cum;

            // ── een 15s-bar (samme raekkefoelge som backtesten) ──
            public void Step(NBar a, bool bok, NBar es, bool noTradeDay)
            {
                long t = a.t;
                DateTime lt = S.NyTime(t);
                int tMin = lt.Hour * 60 + lt.Minute;
                bool inWin = tMin >= WIN_S && tMin < WIN_E;
                bool isOpenM = tMin == WIN_S;
                int ds = lt.Minute / 10 + lt.Minute % 10;
                bool is369 = ds == 3 || ds == 6 || ds == 9;
                long minB = t / 60;
                string dstr = lt.ToString("yyyy-MM-dd");
                DateTime dk = lt.AddHours(6);
                double hi = a.h, lo = a.l, cl = a.c, op = a.o;
                double bh = bok ? es.h : double.NaN, bl = bok ? es.l : double.NaN;
                double bc = bok ? es.c : double.NaN, bo = bok ? es.o : double.NaN;

                bool newMin = lt.Minute != prevMn;
                prevMn = lt.Minute;
                m1Hi = (newMin || double.IsNaN(m1Hi)) ? hi : Math.Max(m1Hi, hi);
                m1Lo = (newMin || double.IsNaN(m1Lo)) ? lo : Math.Min(m1Lo, lo);

                // 15m / 5m: afsluttet candle -> niveauer
                long q15B = t / 900, q5B = t / 300;
                bool newQ15 = q15B != prevQ15, newQ5 = q5B != prevQ5;
                if (newQ15 && prevQ15 >= 0 && InNy(q15Start) && !double.IsNaN(bq15Hi))
                {
                    lv15.Add(new Lv { a = aq15Hi, b = bq15Hi, isHi = true, tm = q15Start });
                    lv15.Add(new Lv { a = aq15Lo, b = bq15Lo, isHi = false, tm = q15Start });
                }
                if (newQ5 && prevQ5 >= 0 && InNy(q5Start) && !double.IsNaN(bq5Hi))
                {
                    lv05.Add(new Lv { a = aq5Hi, b = bq5Hi, isHi = true, tm = q5Start });
                    lv05.Add(new Lv { a = aq5Lo, b = bq5Lo, isHi = false, tm = q5Start });
                }
                if (newQ15) { prevQ15 = q15B; q15Start = q15B * 900; aq15Hi = hi; aq15Lo = lo; bq15Hi = bok ? bh : double.NaN; bq15Lo = bok ? bl : double.NaN; }
                else
                {
                    aq15Hi = Math.Max(aq15Hi, hi); aq15Lo = Math.Min(aq15Lo, lo);
                    if (bok) { bq15Hi = double.IsNaN(bq15Hi) ? bh : Math.Max(bq15Hi, bh); bq15Lo = double.IsNaN(bq15Lo) ? bl : Math.Min(bq15Lo, bl); }
                }
                if (newQ5) { prevQ5 = q5B; q5Start = q5B * 300; aq5Hi = hi; aq5Lo = lo; bq5Hi = bok ? bh : double.NaN; bq5Lo = bok ? bl : double.NaN; }
                else
                {
                    aq5Hi = Math.Max(aq5Hi, hi); aq5Lo = Math.Min(aq5Lo, lo);
                    if (bok) { bq5Hi = double.IsNaN(bq5Hi) ? bh : Math.Max(bq5Hi, bh); bq5Lo = double.IsNaN(bq5Lo) ? bl : Math.Min(bq5Lo, bl); }
                }

                // sessioner
                bool aOn = tMin >= ASIA_S || tMin < ASIA_E;
                bool lOn = tMin >= LON_S && tMin < LON_E;
                bool nOn = tMin >= NY_S && tMin < NY_E;
                bool aStart = aOn && !prevA, lStart = lOn && !prevL, nStart = nOn && !prevN;
                prevA = aOn; prevL = lOn; prevN = nOn;

                Merge(asia, aOn, tMin, hi, lo, bh, bl, bok);
                Merge(lon, lOn, tMin, hi, lo, bh, bl, bok);
                if (aOn) Build(asia, aStart, q15B, hi, lo, bh, bl, bok);
                if (lOn) Build(lon, lStart, q15B, hi, lo, bh, bl, bok);
                if (nOn) Build(ny, nStart, q15B, hi, lo, bh, bl, bok);

                if (nStart) { lv15.Clear(); lv05.Clear(); }
                if (nOn)
                {
                    foreach (var m in lv15.Concat(lv05))
                    {
                        bool aHit = m.isHi ? hi >= m.a : lo <= m.a;
                        bool bHit = bok && (m.isHi ? bh >= m.b : bl <= m.b);
                        if (aHit || bHit) m.dead = true;
                    }
                }
                else
                {
                    foreach (var m in lv05.Concat(tMin >= M15_END ? lv15 : new List<Lv>()))
                        if (m.isHi ? hi >= m.a : lo <= m.a) m.st.aTook = true;
                }

                // ── tjek niveauer ──
                if (vrg && inWin && vDay != dstr) { vDay = dstr; vHi.Reset(); vLo.Reset(); }
                Hit h = new Hit();
                var B = new BarIn { t = t, minB = minB, inWin = inWin, is369 = is369, hi = hi, lo = lo, cl = cl, op = op, bh = bh, bl = bl, bc = bc, bo = bo, bok = bok };
                if (!nOn)
                {
                    Check(ny.hi, ny.aHi, ny.bHi, true, "NY PRE", TgA(ny, true), TgB(ny, true), null, h, B);
                    Check(ny.lo, ny.aLo, ny.bLo, false, "NY PRE", TgA(ny, false), TgB(ny, false), null, h, B);
                }
                if (!lOn)
                {
                    if (!(lon.maHi || lon.mbHi)) Check(lon.hi, lon.aHi, lon.bHi, true, "London", TgA(lon, true), TgB(lon, true), null, h, B);
                    if (!(lon.maLo || lon.mbLo)) Check(lon.lo, lon.aLo, lon.bLo, false, "London", TgA(lon, false), TgB(lon, false), null, h, B);
                }
                if (!aOn)
                {
                    if (!(asia.maHi || asia.mbHi)) Check(asia.hi, asia.aHi, asia.bHi, true, "Asia", TgA(asia, true), TgB(asia, true), null, h, B);
                    if (!(asia.maLo || asia.mbLo)) Check(asia.lo, asia.aLo, asia.bLo, false, "Asia", TgA(asia, false), TgB(asia, false), null, h, B);
                }
                if (!nOn && tMin < M15_END)
                {
                    foreach (var m in lv15)
                    {
                        bool isExt = m.isHi ? Math.Abs(m.a - Nz(ny.aHi)) < TICK / 2 : Math.Abs(m.a - Nz(ny.aLo)) < TICK / 2;
                        if (!m.dead && !isExt)
                            Check(m.st, m.a, m.b, m.isHi, "15m", double.NaN, double.NaN, m.tm >= 0 ? S.NyTime(m.tm).AddHours(6).ToString("HH:mm") : null, h, B);
                    }
                }

                // ── EQ (1m-candles, fulgt paa 15s) ──
                bool new1m = lastMin >= 0 && minB != lastMin;
                bool bearE = false, bullE = false;
                double[] prevMin = null;
                if (new1m)
                {
                    prevMin = (double[])curMin.Clone();
                    double own = (curMin[1] + curMin[2]) / 2;
                    bearE = curMin[3] < curMin[0] && curMin[3] < own;
                    bullE = curMin[3] > curMin[0] && curMin[3] > own;
                    if (inWin && tMin == WIN_S) { bearE = false; bullE = false; }
                }
                if (lastMin < 0 || minB != lastMin) { curMin = new[] { op, hi, lo, cl }; lastMin = minB; }
                else { curMin[1] = Math.Max(curMin[1], hi); curMin[2] = Math.Min(curMin[2], lo); curMin[3] = cl; }

                if (inWin && resetDay != dstr) { resetDay = dstr; dAct = false; uAct = false; }
                if (dAct)
                {
                    if (hi >= (dTop + dBot) / 2) { dAct = false; hitsD.Add(new KeyValuePair<long, double>(t, (dTop + dBot) / 2)); }
                    else dBot = Math.Min(dBot, lo);
                }
                if (bearE && !dAct) { dTop = prevMin[1]; dBot = Math.Min(prevMin[2], lo); dAct = true; }
                if (uAct)
                {
                    if (lo <= (uBot + uTop) / 2) { uAct = false; hitsU.Add(new KeyValuePair<long, double>(t, (uBot + uTop) / 2)); }
                    else uTop = Math.Max(uTop, hi);
                }
                if (bullE && !uAct) { uBot = prevMin[2]; uTop = Math.Max(prevMin[1], hi); uAct = true; }

                // EQ foer open
                if (tMin < WIN_S)
                {
                    pDT = dAct ? dTop : double.NaN; pDB = dAct ? dBot : double.NaN;
                    pUB = uAct ? uBot : double.NaN; pUT = uAct ? uTop : double.NaN;
                    preDHitM = -1; preUHitM = -1;
                }
                else
                {
                    bool gfD = cl > op, gfU = cl < op;
                    if (preDHitM < 0 && !double.IsNaN(pDT))
                    {
                        if (gfD) pDB = Math.Min(pDB, lo);
                        if (hi >= (pDT + pDB) / 2) preDHitM = minB;
                        else if (!gfD) pDB = Math.Min(pDB, lo);
                    }
                    if (preUHitM < 0 && !double.IsNaN(pUB))
                    {
                        if (gfU) pUT = Math.Max(pUT, hi);
                        if (lo <= (pUB + pUT) / 2) preUHitM = minB;
                        else if (!gfU) pUT = Math.Max(pUT, hi);
                    }
                    // 15:29-candlens EQ, hvis der ikke stod en live EQ ved open
                    if (new1m && tMin == WIN_S && resetDay == dstr && prevMin != null)
                    {
                        double own = (prevMin[1] + prevMin[2]) / 2;
                        if (prevMin[3] < prevMin[0] && prevMin[3] < own && double.IsNaN(pDT))
                        { pDT = prevMin[1]; pDB = Math.Min(prevMin[2], lo); preDHitM = -1; }
                        if (prevMin[3] > prevMin[0] && prevMin[3] > own && double.IsNaN(pUB))
                        { pUB = prevMin[2]; pUT = Math.Max(prevMin[1], hi); preUHitM = -1; }
                    }
                }
                double preD = double.IsNaN(pDT) ? double.NaN : (pDT + pDB) / 2;
                double preU = double.IsNaN(pUB) ? double.NaN : (pUB + pUT) / 2;

                // ── daglig status ved open ──
                if (inWin && isOpenM && S.statusDay[vrg ? 1 : 0] != dstr)
                {
                    S.statusDay[vrg ? 1 : 0] = dstr;
                    if (!vrg)
                    {
                        S.nDays++;
                        S.Print(string.Format(CultureInfo.InvariantCulture,
                            "HelbertModels {0} 15:30  NY PRE H/L {1}/{2} (ES {3}/{4})  London {5}/{6}{7}  Asia {8}/{9}{10}  15m-niveauer {11}  EQ foer open bear {12} bull {13}  ES-data {14}{15}",
                            dstr, ny.aHi, ny.aLo, ny.bHi, ny.bLo, lon.aHi, lon.aLo, (lon.maHi || lon.mbHi || lon.maLo || lon.mbLo) ? " (samlet)" : "",
                            asia.aHi, asia.aLo, (asia.maHi || asia.mbHi || asia.maLo || asia.mbLo) ? " (samlet)" : "",
                            lv15.Count(m => !m.dead), double.IsNaN(preD) ? "-" : preD.ToString("0.00", CultureInfo.InvariantCulture),
                            double.IsNaN(preU) ? "-" : preU.ToString("0.00", CultureInfo.InvariantCulture), bok ? "ok" : "MANGLER",
                            noTradeDay ? "  -> INGEN TRADES I DAG (boersen lukket / data mangler)" : ""));
                    }
                }

                // ── minut-status ──
                if (minB != curM) { curM = minB; mHi = false; mLo = false; mBad = false; }
                if (inWin) { mHi = mHi || h.swHi; mLo = mLo || h.swLo; }
                if (mHi && mLo && !mBad) mBad = true;

                // ── aabent trade (virtuelt - styrer papirkurve og BE paa den rigtige ordre) ──
                if (o != null) Manage(o, hi, lo, cl);

                // ── Vergence: arm og afgoer ──
                if (vrg) Vergence(h, B);

                // ── nyt trade ──
                if (dstr != tradeDay) { tradeDay = dstr; dayCount = 0; dayWin = false; }
                if (h.fired && !mBad && lastTradeM != minB && !noTradeDay)
                    NewTrade(h, t, minB, isOpenM, cl, dstr, dk, preD, preU);
            }

            private class BarIn { public long t, minB; public bool inWin, is369, bok; public double hi, lo, cl, op, bh, bl, bc, bo; }

            private bool InNy(long tStart)
            {
                if (tStart < 0) return false;
                DateTime x = S.NyTime(tStart);
                int m = x.Hour * 60 + x.Minute;
                return m >= NY_S && m < WIN_S;
            }
            private static double Nz(double v) { return double.IsNaN(v) ? 0 : v; }

            private void Merge(Sess s, bool on, int tMin, double hi, double lo, double bh, double bl, bool bok)
            {
                if (on || double.IsNaN(s.aHi) || tMin >= WIN_S) return;
                if (hi > s.aHi) { s.aHi = hi; s.maHi = true; }
                if (lo < s.aLo) { s.aLo = lo; s.maLo = true; }
                if (bok && !double.IsNaN(s.bHi) && bh > s.bHi) { s.bHi = bh; s.mbHi = true; }
                if (bok && !double.IsNaN(s.bLo) && bl < s.bLo) { s.bLo = bl; s.mbLo = true; }
            }

            private void Build(Sess s, bool isStart, long q15B, double hi, double lo, double bh, double bl, bool bok)
            {
                if (isStart)
                {
                    s.aHi = hi; s.aLo = lo;
                    s.bHi = bok ? bh : double.NaN; s.bLo = bok ? bl : double.NaN;
                    s.hi = new St(); s.lo = new St();
                    s.aHiM = s.bHiM = s.aLoM = s.bLoM = q15B;
                    s.aTgH = s.bTgH = s.aTgL = s.bTgL = double.NaN;
                    s.maHi = s.mbHi = s.maLo = s.mbLo = false;
                }
                else
                {
                    if (hi >= s.aHi) s.aHiM = q15B;
                    if (lo <= s.aLo) s.aLoM = q15B;
                    if (bok && (double.IsNaN(s.bHi) || bh >= s.bHi)) s.bHiM = q15B;
                    if (bok && (double.IsNaN(s.bLo) || bl <= s.bLo)) s.bLoM = q15B;
                    s.aHi = Math.Max(s.aHi, hi); s.aLo = Math.Min(s.aLo, lo);
                    if (bok)
                    {
                        s.bHi = double.IsNaN(s.bHi) ? bh : Math.Max(s.bHi, bh);
                        s.bLo = double.IsNaN(s.bLo) ? bl : Math.Min(s.bLo, bl);
                    }
                }
                if (s.aHiM == q15B) s.bTgH = bq15Hi;
                if (s.bHiM == q15B) s.aTgH = aq15Hi;
                if (s.aLoM == q15B) s.bTgL = bq15Lo;
                if (s.bLoM == q15B) s.aTgL = aq15Lo;
            }

            private double TgA(Sess s, bool isHi)
            {
                if (isHi ? (s.maHi || s.mbHi) : (s.maLo || s.mbLo)) return double.NaN;
                return isHi ? (s.aHiM != s.bHiM ? s.aTgH : double.NaN) : (s.aLoM != s.bLoM ? s.aTgL : double.NaN);
            }
            private double TgB(Sess s, bool isHi)
            {
                if (isHi ? (s.maHi || s.mbHi) : (s.maLo || s.mbLo)) return double.NaN;
                return isHi ? (s.aHiM != s.bHiM ? s.bTgH : double.NaN) : (s.aLoM != s.bLoM ? s.bTgL : double.NaN);
            }

            // ── een side af eet niveau ──
            private void Check(St st, double aL, double bL, bool isHi, string nm, double aTg, double bTg, string tag15, Hit h, BarIn B)
            {
                if (st == null || double.IsNaN(aL) || double.IsNaN(bL)) return;
                double hi = B.hi, lo = B.lo, cl = B.cl, op = B.op, bh = B.bh, bl = B.bl, bc = B.bc, bo = B.bo;
                bool bok = B.bok, inWin = B.inWin; long t = B.t, minB = B.minB;
                bool aSweep = isHi ? hi >= aL + TICK : lo <= aL - TICK;
                bool bSweep = bok && (isHi ? bh >= bL + TICK : bl <= bL - TICK);
                string lvlNm = nm + (isHi ? " high" : " low");
                if (inWin && aSweep && !st.aTook && nm != "15m")
                {
                    if (isHi) { h.sHi = true; hitsSH.Add(new KeyValuePair<long, double>(t, aL)); }
                    else { h.sLo = true; hitsSL.Add(new KeyValuePair<long, double>(t, aL)); }
                }
                if (aSweep) st.aTook = true;
                if (bSweep) st.bTook = true;
                bool newTg = false;
                if (inWin && !double.IsNaN(aTg) && !st.aTgT && (isHi ? (aTg < aL && hi >= aTg + TICK) : (aTg > aL && lo <= aTg - TICK)))
                { st.aTgT = true; newTg = true; }
                if (inWin && bok && !double.IsNaN(bTg) && !st.bTgT && (isHi ? (bTg < bL && bh >= bTg + TICK) : (bTg > bL && bl <= bTg - TICK)))
                { st.bTgT = true; newTg = true; }
                bool aTk = st.aTook || st.aTgT, bTk = st.bTook || st.bTgT;

                if (vrg)
                {
                    // Vergence: et niveau taget foerste gang i vinduet = FRISK liq. Bagefter flytter
                    // niveauet med til indeksets nye yderpunkt (ny liq, men ikke frisk).
                    if (!inWin) return;
                    string vKey = lvlNm + (tag15 != null ? " " + tag15 : "");
                    double curA = double.IsNaN(st.aLv) ? aL : st.aLv;
                    double curB = double.IsNaN(st.bLv) ? bL : st.bLv;
                    bool nA = isHi ? hi >= curA + TICK : lo <= curA - TICK;
                    bool nB = bok && (isHi ? bh >= curB + TICK : bl <= curB - TICK);
                    VSide sd = isHi ? vHi : vLo;
                    if (nA)
                    {
                        if (double.IsNaN(st.aLv))
                        {
                            sd.aF.Add(new VF { m = minB, lvl = aL, key = vKey });
                            sd.aFL = (sd.aFM != minB || double.IsNaN(sd.aFL)) ? aL : (isHi ? Math.Max(sd.aFL, aL) : Math.Min(sd.aFL, aL));
                            sd.aFM = minB;
                        }
                        if (curA == aL || !sd.had) { sd.aE = minB; sd.isNew = true; }
                        st.aLv = isHi ? hi : lo;
                    }
                    if (nB)
                    {
                        if (double.IsNaN(st.bLv))
                        {
                            sd.bF.Add(new VF { m = minB, lvl = bL, key = vKey });
                            sd.bFL = (sd.bFM != minB || double.IsNaN(sd.bFL)) ? bL : (isHi ? Math.Max(sd.bFL, bL) : Math.Min(sd.bFL, bL));
                            sd.bFM = minB;
                        }
                        if (curB == bL || !sd.had) { sd.bE = minB; sd.isNew = true; }
                        st.bLv = isHi ? bh : bl;
                    }
                    if (nA || nB) { sd.xT = t; h.swHi = h.swHi || isHi; h.swLo = h.swLo || !isHi; }
                    return;
                }

                if (!inWin)
                {
                    if (aSweep) { st.aDone = true; st.aPre = true; }
                    if (bSweep) st.bDone = true;
                    return;
                }
                bool newA = !st.aDone && st.aM < 0 && aSweep;
                bool newB = !st.bDone && st.bM < 0 && bSweep;
                if (newA) { st.aM = minB; st.aT = t; }
                if (newB) { st.bM = minB; st.bT = t; }
                if (newA || newB) { h.swHi = h.swHi || isHi; h.swLo = h.swLo || !isHi; }
                if ((newA || newB || newTg) && aTk && bTk && !(st.aDone && st.bDone)) { st.aDone = true; st.bDone = true; }
                if (!B.is369) { if (newA) st.aDone = true; if (newB) st.bDone = true; }
                if (!st.aDone && st.aM >= 0 && st.aM != minB) st.aDone = true;
                if (!st.bDone && st.bM >= 0 && st.bM != minB) st.bDone = true;
                if (h.fired) return;
                bool dirOK = isHi ? (cl < op && bok && bc < bo) : (cl > op && bok && bc > bo);
                bool aBack = !st.aDone && !bTk && st.aM == minB && (isHi ? cl < aL : cl > aL);
                bool bBack = !st.bDone && !aTk && st.bM == minB && bok && (isHi ? bc < bL : bc > bL);
                if (aBack && t - st.aT > 15) aBack = false;   // tid close: sweep-candlen eller den naeste
                if (bBack && t - st.bT > 15) bBack = false;
                bool slOK = isHi ? (m1Hi - cl <= MAX_SL) : (cl - m1Lo <= MAX_SL);
                if (dirOK && (aBack || bBack) && !slOK) { st.aDone = true; st.bDone = true; }
                if (dirOK && (aBack || bBack) && slOK)
                {
                    h.fired = true; h.isShort = isHi; h.lvl = aL; h.src = lvlNm;
                    h.who = aBack && bBack ? "NQ + ES" : (aBack ? "NQ" : "ES");
                    st.aDone = true; st.bDone = true;
                }
            }

            // ── Vergence: begge indeks har taget SAMME niveau (foerste take hoejst 5 min fra hinanden).
            //    Foerste 15s-close i samme minut hvor begge lukker i retningen afgoer: indekset der tog
            //    frisk liq i det minut skal lukke tilbage forbi den (begge, hvis begge), og SL <= 30. ──
            private void Vergence(Hit h, BarIn B)
            {
                long minB = B.minB, t = B.t;
                foreach (bool side in new[] { true, false })
                {
                    VSide sd = side ? vHi : vLo;
                    if (sd.isNew)
                    {
                        var fa = sd.aF.Where(f => !f.used && sd.bF.Any(g => g.key == f.key && Math.Abs(g.m - f.m) <= VRG_GAP)).ToList();
                        var fb = sd.bF.Where(f => !f.used && sd.aF.Any(g => g.key == f.key && Math.Abs(g.m - f.m) <= VRG_GAP)).ToList();
                        if (fa.Count > 0 || fb.Count > 0)
                        {
                            var faN = fa.Where(f => f.m == minB).ToList();
                            var fbN = fb.Where(f => f.m == minB).ToList();
                            if (faN.Count > 0 || fbN.Count > 0) { fa = faN; fb = fbN; }
                            var ma = new HashSet<long>(fa.Select(g => g.m));
                            var mb = new HashSet<long>(fb.Select(g => g.m));
                            fa = sd.aF.Where(f => ma.Contains(f.m)).ToList();
                            fb = sd.bF.Where(f => mb.Contains(f.m)).ToList();
                            double aLv = fa.Count > 0 ? (side ? fa.Max(f => f.lvl) : fa.Min(f => f.lvl)) : double.NaN;
                            double bLv = fb.Count > 0 ? (side ? fb.Max(f => f.lvl) : fb.Min(f => f.lvl)) : double.NaN;
                            var names = fa.Concat(fb).Select(f => f.key).Distinct().ToList();
                            names.Sort(StringComparer.Ordinal);
                            foreach (var f in fa.Concat(fb)) f.used = true;
                            sd.had = true;
                            h.varm.Add(new VArm { shrt = side, va = aLv, vb = bLv, names = string.Join(" / ", names) });
                        }
                    }
                    sd.isNew = false;
                }
                vArms = vArms.Where(v => v.t / 60 == minB).ToList();
                foreach (var v in h.varm)
                    if (!mBad) { v.t = t; vArms.Add(v); }
                if (vArms.Count == 0 || mBad) return;
                var keep = new List<VArm>();
                foreach (var v in vArms)
                {
                    if (t - v.t > 15) continue;   // tid close: for sent efter sweepet
                    bool aD = v.shrt ? B.cl < B.op : B.cl > B.op;
                    bool bD = B.bok && (v.shrt ? B.bc < B.bo : B.bc > B.bo);
                    if (!(aD && bD)) { keep.Add(v); continue; }
                    VSide sdv = v.shrt ? vHi : vLo;
                    long am = v.t / 60;
                    double va = v.va, vb = v.vb;
                    if (sdv.aFM == am && sdv.bFM == am)
                    {
                        if (double.IsNaN(va)) va = sdv.aFL;
                        if (double.IsNaN(vb)) vb = sdv.bFL;
                    }
                    bool backA = double.IsNaN(va) || (v.shrt ? B.cl < va : B.cl > va);
                    bool backB = double.IsNaN(vb) || (B.bok && (v.shrt ? B.bc < vb : B.bc > vb));
                    bool slOK = v.shrt ? (m1Hi - B.cl <= MAX_SL) : (B.cl - m1Lo <= MAX_SL);
                    if (backA && backB && slOK && !h.fired)
                    {
                        h.fired = true; h.isShort = v.shrt; h.lvl = va; h.src = v.names;
                        h.who = !double.IsNaN(va) && !double.IsNaN(vb) ? "Begge" : (!double.IsNaN(va) ? "NQ" : "ES");
                    }
                    // afvist = faerdigt (foerste close hvor begge lukker i retningen afgoer)
                }
                vArms = keep;
            }

            // ── nyt trade: BE, ugyldig-regler, SL/TP, dagsregler, kurvefilter ──
            private void NewTrade(Hit h, long t, long minB, bool isOpenM, double px, string dstr, DateTime dk, double preD, double preU)
            {
                bool sh = h.isShort;
                var cands = new List<Tuple<double, string, bool>>();
                double elo = sh ? (uAct ? uBot : double.NaN) : (dAct ? dBot : double.NaN);
                double ehi = sh ? (uAct ? uTop : double.NaN) : (dAct ? dTop : double.NaN);
                if (!double.IsNaN(elo))
                {
                    cands.Add(Tuple.Create((elo + ehi) / 2, "EQ", false));
                    cands.Add(Tuple.Create(elo + (sh ? 0.75 : 0.25) * (ehi - elo), sh ? "0.75" : "0.25", false));
                }
                if (preDHitM < 0) cands.Add(Tuple.Create(preD, "EQ foer open", false));
                if (preUHitM < 0) cands.Add(Tuple.Create(preU, "EQ foer open", false));
                foreach (var p in new[] { Tuple.Create("Asia", asia), Tuple.Create("London", lon), Tuple.Create("NY PRE", ny) })
                {
                    St st = sh ? p.Item2.lo : p.Item2.hi;
                    if (st != null && !st.aPre)
                        cands.Add(Tuple.Create(sh ? p.Item2.aLo : p.Item2.aHi, p.Item1 + (sh ? " low" : " high"), st.aTook));
                }
                foreach (var m in lv15)
                    if (m.isHi != sh && !m.dead && !m.st.aTook) cands.Add(Tuple.Create(m.a, sh ? "15m low" : "15m high", false));
                if (isOpenM)
                    foreach (var m in lv05)
                        if (m.isHi != sh && !m.dead && !m.st.aTook) cands.Add(Tuple.Create(m.a, sh ? "5m low" : "5m high", false));

                double be = double.NaN; string beS = "-"; bool beBad = false;
                foreach (var c in cands)
                {
                    if (double.IsNaN(c.Item1)) continue;
                    double d = Math.Abs(px - c.Item1);
                    if ((sh ? c.Item1 < px : c.Item1 > px) && d >= BE_MIN && d <= BE_MAX && (double.IsNaN(be) || d < Math.Abs(px - be)))
                    { be = c.Item1; beS = c.Item2; beBad = c.Item3; }
                }
                // EQ foer open (BE-siden) ramt i entry-minuttet = ugyldig (kun hvis slaaet til; fra som standard 9/10-26)
                double peq = sh ? preU : preD; long phm = sh ? preUHitM : preDHitM;
                if (S.PreOpenInvalid && !double.IsNaN(peq) && phm == minB && (sh ? px - peq : peq - px) <= BE_MAX) { beBad = true; beS = "EQ foer open"; }
                // live EQ / session-liq paa BE-siden taget i entry-minuttet foer entry-candlen
                long m0 = minB * 60;
                Func<List<KeyValuePair<long, double>>, bool> anyHit = L =>
                {
                    foreach (var x in L)
                        if (x.Key >= m0 && x.Key < t && (sh ? px - x.Value : x.Value - px) >= -BE_MIN) return true;
                    return false;
                };
                bool eqT = sh ? anyHit(hitsU) : anyHit(hitsD);
                bool slT = sh ? anyHit(hitsSL) : anyHit(hitsSH);
                if (eqT || slT) { beBad = true; beS = eqT ? (sh ? "bullish EQ" : "bearish EQ") : (sh ? "session low" : "session high"); }

                double sl = sh ? Math.Max(m1Hi, px + MIN_SL) : Math.Min(m1Lo, px - MIN_SL);
                var tcs = new List<Tuple<double, string>>();
                if (uAct) tcs.Add(Tuple.Create((uBot + uTop) / 2, "EQ"));
                if (dAct) tcs.Add(Tuple.Create((dBot + dTop) / 2, "EQ"));
                foreach (var p in new[] { Tuple.Create("Asia", asia), Tuple.Create("London", lon), Tuple.Create("NY PRE", ny) })
                {
                    St st = sh ? p.Item2.lo : p.Item2.hi;
                    if (st != null && !st.aTook) tcs.Add(Tuple.Create(sh ? p.Item2.aLo : p.Item2.aHi, p.Item1 + (sh ? " low" : " high")));
                }
                double tp = double.NaN; string tpS = "75p";
                foreach (var c in tcs)
                {
                    if (double.IsNaN(c.Item1)) continue;
                    double d = sh ? px - c.Item1 : c.Item1 - px;
                    if (d >= TP_MIN && d <= TP_MAX && (double.IsNaN(tp) || d < Math.Abs(px - tp))) { tp = c.Item1; tpS = c.Item2; }
                }
                if (double.IsNaN(tp)) tp = sh ? px - TP_MAX : px + TP_MAX;

                string tm = dk.ToString("HH:mm:ss");
                if (beBad)
                {
                    S.WriteCsv(tag, dstr, tm, sh, h.src, h.who, px, sl, tp, be, beS, "UGYLDIG (BE allerede ramt)", "", double.NaN, false);
                    S.Print(string.Format("{0} {1} {2} {3} {4} ({5}) UGYLDIG - BE ({6}) allerede ramt", tag, dstr, tm, sh ? "SHORT" : "LONG", h.src, h.who, beS));
                    return;
                }
                lastTradeM = minB;   // kun eet trade pr. minut (ogsaa naar dagsreglerne springer det over)
                // dagsregler: stop efter win, max 2 pr. dag (gyldige trades taeller ogsaa paa papir)
                if (dayWin || dayCount >= 2)
                {
                    S.WriteCsv(tag, dstr, tm, sh, h.src, h.who, px, sl, tp, be, beS, dayWin ? "SPRUNGET OVER (dagen vundet)" : "SPRUNGET OVER (max 2)", "", double.NaN, false);
                    S.Print(string.Format("{0} {1} {2} {3} {4} - sprunget over ({5})", tag, dstr, tm, sh ? "SHORT" : "LONG", h.src, dayWin ? "dagen vundet" : "max 2"));
                    return;
                }
                dayCount++;

                // kurvefilter: rigtigt trade kun naar papirkurven er paa/over snittet af de sidste 30 punkter
                bool real = true; string why = "";
                if (useCurve && curve.Count >= 30)
                {
                    double ma = curve.Skip(curve.Count - 30).Average();
                    real = curve[curve.Count - 1] >= ma;
                    if (!real) why = " (kurvefilter)";
                }
                // ingen modsatte ordrer: den anden model har et aabent rigtigt trade den anden vej
                Engine other = S.OtherEngine(this);
                if (real && other != null && other.o != null && other.o.real && other.o.shrt != sh) { real = false; why = " (modsat " + other.tag + "-trade aabent)"; }

                if (o != null)
                {
                    S.WriteCsv(tag, o.date, o.time, o.shrt, o.src, o.who, o.entry, o.sl0, o.tp, o.be, o.beSrc, "OK", "AFLOEST", 0, o.real);
                    curve.Add(cum);   // afloest = 0R paa kurven
                    if (o.real && S.LiveOrders) { if (o.shrt) S.ExitShort("Exit" + tag, tag); else S.ExitLong("Exit" + tag, tag); }
                }
                o = new VTrade { shrt = sh, entry = px, sl = sl, sl0 = sl, tp = tp, be = be, beSrc = beS, tpSrc = tpS, date = dstr, time = tm, src = h.src, who = h.who, real = real };

                if (real && S.LiveOrders)
                {
                    int qty = contracts;
                    if (S.RiskDollars > 0)
                    {
                        double pv = S.Instrument.MasterInstrument.PointValue;
                        qty = Math.Max(1, (int)Math.Floor(S.RiskDollars / (Math.Abs(px - sl) * pv)));
                    }
                    S.SetStopLoss(tag, CalculationMode.Price, sl, false);
                    S.SetProfitTarget(tag, CalculationMode.Price, tp);
                    if (sh) S.EnterShort(qty, tag); else S.EnterLong(qty, tag);
                }
                // markering paa chartet
                try
                {
                    DateTime barTime = TimeZoneInfo.ConvertTimeFromUtc(S.epoch.AddSeconds(t + 15), NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
                    if (sh) Draw.ArrowDown(S, tag + t, false, barTime, px + 4, real ? Brushes.Red : Brushes.Gray);
                    else Draw.ArrowUp(S, tag + t, false, barTime, px - 4, real ? Brushes.Lime : Brushes.Gray);
                    Draw.Text(S, tag + "t" + t, false, tag + (sh ? " SHORT " : " LONG ") + h.src, barTime, sh ? px + (vrg ? 16 : 10) : px - (vrg ? 16 : 10), 0,
                        Brushes.White, new NinjaTrader.Gui.Tools.SimpleFont("Arial", 10), System.Windows.TextAlignment.Center, Brushes.Transparent, Brushes.Transparent, 0);
                }
                catch { }
                S.Print(string.Format("{0} {1} {2} {3} {4} ({5}) entry {6} SL {7} TP {8} BE {9} [{10}] {11}{12}",
                    tag, dstr, tm, sh ? "SHORT" : "LONG", h.src, h.who, px, sl, tp, double.IsNaN(be) ? "-" : be.ToString(), beS, real ? "RIGTIG" : "PAPIR", why));
            }

            // ── styr det aabne trade (virtuelt) ──
            private void Manage(VTrade x, double hi, double lo, double cl)
            {
                bool hitSL = x.shrt ? hi >= x.sl : lo <= x.sl;
                bool hitTP = x.shrt ? lo <= x.tp : hi >= x.tp;
                if (hitSL || hitTP)
                {
                    double pts; string res;
                    if (hitSL) { pts = x.shrt ? x.entry - x.sl : x.sl - x.entry; res = x.beHit ? "BE" : "SL"; }
                    else { pts = Math.Abs(x.tp - x.entry); res = "TP"; }
                    double R = Math.Round(pts / 10.0, 2);
                    if (R > 0) dayWin = true;
                    cum += R; curve.Add(cum);
                    S.WriteCsv(tag, x.date, x.time, x.shrt, x.src, x.who, x.entry, x.sl0, x.tp, x.be, x.beSrc, "OK", res, R, x.real);
                    o = null;
                    return;
                }
                if (!x.beHit && !double.IsNaN(x.be) && !x.noBE)
                {
                    bool touch = x.shrt ? lo <= x.be : hi >= x.be;
                    if (x.bars < 2)
                    {
                        if (touch) x.early = true;
                        if (x.bars == 1 && x.early)
                        {
                            if (x.shrt ? cl < x.entry : cl > x.entry) MoveBE(x);
                            else x.noBE = true;
                        }
                    }
                    else if (touch) MoveBE(x);
                }
                x.bars++;
            }

            private void MoveBE(VTrade x)
            {
                x.beHit = true;
                x.sl = x.entry;
                if (x.real && S.LiveOrders && S.Position.MarketPosition != MarketPosition.Flat)
                    S.SetStopLoss(tag, CalculationMode.Price, x.entry, false);
            }
        }

        // ───────────── strategi-tilstand ─────────────
        private TimeZoneInfo nyTz;
        private readonly DateTime epoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        private NBar esBar; private bool esHave;
        private NBar pendNq; private bool pend;
        private Engine smt, vrgE;
        private string logPath;
        private string[] statusDay = { "", "" };
        private bool wrongChart;
        private int nBars, nPaired, nDays; private DateTime lastNy;
        private string nyCntDay = ""; private int nyCnt;
        private HashSet<string> extraClosed = new HashSet<string>();

        // ───────────── indstillinger ─────────────
        [NinjaScriptProperty]
        [Display(Name = "Sammenlign med (MES/ES)", Order = 1, GroupName = "1. Data")]
        public string CompareSymbol { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Koer SMT", Order = 1, GroupName = "2. Modeller")]
        public bool UseSMT { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Koer Vergence", Order = 2, GroupName = "2. Modeller")]
        public bool UseVergence { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "SMT: antal kontrakter", Order = 1, GroupName = "3. Risiko")]
        public int SmtContracts { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Vergence: antal kontrakter", Order = 2, GroupName = "3. Risiko")]
        public int VrgContracts { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100000)]
        [Display(Name = "Risiko i $ pr. trade (0 = brug antal kontrakter)", Order = 3, GroupName = "3. Risiko")]
        public double RiskDollars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "SMT: kurvefilter (30)", Order = 1, GroupName = "4. Regler")]
        public bool SmtCurveFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Vergence: kurvefilter (30)", Order = 2, GroupName = "4. Regler")]
        public bool VrgCurveFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "SMT: startkurve (R pr. papir-trade, kommasepareret)", Order = 3, GroupName = "4. Regler")]
        public string SmtSeedCurve { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Vergence: startkurve (R pr. papir-trade, kommasepareret)", Order = 4, GroupName = "4. Regler")]
        public string VrgSeedCurve { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Send rigtige ordrer", Order = 5, GroupName = "4. Regler")]
        public bool LiveOrders { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "EQ foer open ramt = ugyldigt trade", Order = 6, GroupName = "4. Regler")]
        public bool PreOpenInvalid { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Ekstra dage uden trades (yyyy-mm-dd, kommasepareret)", Order = 7, GroupName = "4. Regler")]
        public string ExtraNoTradeDays { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "HelbertModels";
                Description = "SMT + Vergence (Helbert) - MNQ/NQ 15s med MES/ES som sammenligning";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.UniqueEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TraceOrders = false;
                CompareSymbol = "MES 12-26";
                UseSMT = true;
                UseVergence = true;
                SmtContracts = 5;
                VrgContracts = 5;
                RiskDollars = 0;
                SmtCurveFilter = true;
                VrgCurveFilter = true;
                SmtSeedCurve = "";
                VrgSeedCurve = "";
                LiveOrders = true;
                PreOpenInvalid = false;
                ExtraNoTradeDays = "";
            }
            else if (State == State.Configure)
            {
                AddDataSeries(CompareSymbol, BarsPeriodType.Second, 15);
            }
            else if (State == State.Realtime)
            {
                Print(string.Format("HelbertModels: historik faerdig - {0} bars, {1} med {2}, {3} dage med 15:30-vindue, sidste bar {4} (NY)",
                    nBars, nPaired, CompareSymbol, nDays, lastNy.ToString("yyyy-MM-dd HH:mm:ss")));
            }
            else if (State == State.DataLoaded)
            {
                string msg = "HelbertModels startet paa " + Instrument.FullName + " / " + CompareSymbol + " (" + BarsPeriod.Value + " " + BarsPeriod.BarsPeriodType + ")"
                    + "  SMT " + (UseSMT ? SmtContracts + " stk" : "fra") + ", Vergence " + (UseVergence ? VrgContracts + " stk" : "fra");
                Print(msg);
                Log(msg, NinjaTrader.Cbi.LogLevel.Information);
                wrongChart = !Instrument.FullName.StartsWith("NQ") && !Instrument.FullName.StartsWith("MNQ");
                if (wrongChart)
                {
                    string w = "HelbertModels: FORKERT CHART - strategien skal ligge paa et NQ/MNQ 15 Second chart, ikke " + Instrument.FullName + ". Den handler ikke.";
                    Print(w);
                    Log(w, NinjaTrader.Cbi.LogLevel.Warning);
                }
                try { nyTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
                catch { nyTz = TimeZoneInfo.FindSystemTimeZoneById("America/New_York"); }
                logPath = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "HelbertModels_log.csv");
                try { File.WriteAllText(logPath, "model;dato;tid_dk;retning;niveau;swept;entry;sl;tp;be;be_kilde;status;resultat;R;rigtig\n"); }
                catch { }
                smt = UseSMT ? new Engine(this, false) { contracts = SmtContracts, useCurve = SmtCurveFilter } : null;
                vrgE = UseVergence ? new Engine(this, true) { contracts = VrgContracts, useCurve = VrgCurveFilter } : null;
                if (smt != null) Seed(smt, SmtSeedCurve);
                if (vrgE != null) Seed(vrgE, VrgSeedCurve);
                extraClosed.Clear();
                if (!string.IsNullOrWhiteSpace(ExtraNoTradeDays))
                    foreach (var d in ExtraNoTradeDays.Split(new[] { ',', ';', ' ' }, StringSplitOptions.RemoveEmptyEntries)) extraClosed.Add(d.Trim());
            }
        }

        private static void Seed(Engine e, string s)
        {
            e.cum = 0;
            if (string.IsNullOrWhiteSpace(s)) return;
            foreach (var p in s.Split(new[] { ';', ' ' }, StringSplitOptions.RemoveEmptyEntries).SelectMany(x => x.Split(',')))
            {
                double r;
                if (double.TryParse(p.Trim(), NumberStyles.Any, CultureInfo.InvariantCulture, out r)) { e.cum += r; e.curve.Add(e.cum); }
            }
        }

        private Engine OtherEngine(Engine e) { return e == smt ? vrgE : smt; }

        // ── tid ──
        private long ToUnixStart(DateTime barEnd)
        {
            DateTime utc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(barEnd, DateTimeKind.Unspecified), NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
            return (long)(utc - epoch).TotalSeconds - 15;
        }
        private DateTime NyTime(long t)
        {
            return TimeZoneInfo.ConvertTimeFromUtc(epoch.AddSeconds(t), nyTz);
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress == 1)
            {
                esBar = new NBar { t = ToUnixStart(Times[1][0]), o = Opens[1][0], h = Highs[1][0], l = Lows[1][0], c = Closes[1][0] };
                esHave = true;
                if (pend && pendNq.t == esBar.t) { pend = false; Step(pendNq, true); }
                return;
            }
            if (BarsInProgress != 0 || wrongChart) return;
            NBar nq = new NBar { t = ToUnixStart(Times[0][0]), o = Opens[0][0], h = Highs[0][0], l = Lows[0][0], c = Closes[0][0] };
            // forrige NQ-bar ventede paa ES og fik ingen -> koer den uden ES
            if (pend) { pend = false; Step(pendNq, false); }
            if (esHave && esBar.t == nq.t) Step(nq, true);
            else { pendNq = nq; pend = true; }
        }

        private void Step(NBar a, bool bok)
        {
            DateTime lt = NyTime(a.t);
            nBars++; if (bok) nPaired++; lastNy = lt;
            if (nBars == 1) Print("HelbertModels: foerste bar " + lt.ToString("yyyy-MM-dd HH:mm:ss") + " (NY)");
            string dstr = lt.ToString("yyyy-MM-dd");
            int tMin = lt.Hour * 60 + lt.Minute;
            // NY PRE-data til stede? (08:00-09:30 = 360 bars)
            if (tMin >= NY_S && tMin < NY_E) { if (nyCntDay != dstr) { nyCntDay = dstr; nyCnt = 0; } nyCnt++; }
            bool noTrade = NyseClosed.Contains(dstr) || extraClosed.Contains(dstr) || nyCntDay != dstr || nyCnt < NYPRE_MIN_BARS;
            if (smt != null) smt.Step(a, bok, esBar, noTrade);
            if (vrgE != null) vrgE.Step(a, bok, esBar, noTrade);
        }

        private void WriteCsv(string model, string dstr, string tm, bool sh, string src, string who, double px, double sl, double tp, double be, string beS,
            string status, string res, double R, bool real)
        {
            try
            {
                var ci = CultureInfo.InvariantCulture;
                string line = string.Join(";", model, dstr, tm, sh ? "SHORT" : "LONG", src, who,
                    px.ToString(ci), sl.ToString(ci), tp.ToString(ci), double.IsNaN(be) ? "" : be.ToString(ci), beS,
                    status, res, double.IsNaN(R) ? "" : R.ToString(ci), real ? "ja" : "nej");
                File.AppendAllText(logPath, line + "\n");
            }
            catch { }
        }
    }
}
