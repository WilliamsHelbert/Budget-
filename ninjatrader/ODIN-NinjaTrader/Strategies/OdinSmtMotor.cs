// ODIN - regelkernen for Gungner (SMT / Sweep Trade) og Sleipner (Vergence), bar for bar.
// Port af smt_backtest.py (Helbert's Hjaelpe Indikator v2.6) til C#. Kun de regler scriptets standard-indstillinger
// bruger er med. Ingen NinjaTrader-afhaengigheder, saa den kan testes mod Python-scriptet (SmtTest.cs).
//
// INDDATA   PaaEs(t, o, h, l, c)   for hver 15s ES-bar (ES-baren med samme tid som en NQ-bar SKAL komme foerst)
//           PaaNq(t, ny, o, h, l, c) for hver 15s NQ-bar. t = barens start (unix), ny = barens start i New York-tid.
//           ES "fyldes frem" som i scriptet: har ES ingen bar paa NQ-barens tid, bruges ES-baren fra den seneste
//           NQ-tid hvor begge havde en bar (reindex + ffill). ES' 15m/5m-candles bygges af alle ES-barer.
// UDDATA    begivenheder: Ny (ny handel), Ugyldig, Lukket (SL/BE/TP), Be (stop flyttet til entry), Afloest
//           (en ny handel afloeser den aabne). Motoren handler selv paa papir - strategien foelger den.
//
// REGLER (scriptets standard)
//   niveauer  Asia 20:00-02:00, London 02:00-08:00, NY PRE 08:00-09:30 NY (high/low paa NQ og ES), NY PRE's 15m-
//             candles (doede hvis taget i NY PRE, gaelder til 09:31). En tidligere sessions niveau der tages senere
//             foer open "flytter med" og er ikke et selvstaendigt niveau.
//   vindue    09:30-10:00 NY. Kun minutter med tvaersum 3/6/9 (SMT).
//   SMT       kun det ene indeks sweeper (1 tick), og i SAMME minut lukker en 15s-candle tilbage paa den anden side
//             (senest candlen efter sweepet), begge lukker i trade-retningen, SL <= 30.
//   Vergence  begge indeks tager samme niveau (frisk) hoejst 5 min fra hinanden; foerste 15s-close hvor begge lukker
//             i retningen afgoer, indekset der tog frisk liq skal lukke tilbage forbi den, SL <= 30.
//   SL        1m-candlens top/bund ved entry, mindst 10 point.  TP  naermeste EQ/session-liq 35-75 point, ellers 75.
//   BE        naermeste EQ, 0,25/0,75, EQ foer open, session-liq, 15m, 5m (kun 09:30) 2-50 point; aktiv foerst efter
//             2 lukkede 15s-candles. Ugyldig hvis BE-spottet allerede er taget.
//   R         point / 10.

using System;
using System.Collections.Generic;
using System.Globalization;

namespace NinjaTrader.NinjaScript.Strategies.Odin
{
	public class SmtHandel
	{
		public string Dato, Tid, Niveau = "", Swept = "", Info = "", TpKilde = "", BeKilde = "-", Status, Resultat = "", Exit = "";
		public bool Kort;
		public double Entry;
		public double? Sl, Tp, Be, Points, R;
		public long T;
	}

	public enum SmtType { Ny, Ugyldig, Lukket, Be, Afloest }

	public class SmtBegivenhed
	{
		public SmtType Type;
		public SmtHandel Handel;
		public double Pris;          // Lukket: exitpris (SL eller TP). Be: ny stop (= entry)
		public SmtBegivenhed(SmtType type, SmtHandel h, double pris) { Type = type; Handel = h; Pris = pris; }
	}

	public class SmtMotor
	{
		private const double TICK = 0.25;
		private const int WIN_S = 9 * 60 + 30, WIN_E = 10 * 60, M15_END = 9 * 60 + 31;
		private const double MIN_SL = 10, MAX_SL = 30, TP_MIN = 35, TP_MAX = 75, BE_MIN = 2, BE_MAX = 50;
		private const int VRG_GAP = 5, NYPRE_MIN_BARS = 300;
		// Vergence: close tilbage maales kun mod niveauer BEGGE indeks har taget (15/10-26)
		private const bool VRG_SHARED = true;
		private static readonly HashSet<string> NO_TRADE_DAYS = new HashSet<string>(new string[] {
			"2022-01-17", "2022-02-21", "2022-04-15", "2022-05-30", "2022-06-20", "2022-07-04", "2022-09-05", "2022-11-24", "2022-12-26",
			"2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29", "2023-06-19", "2023-07-04", "2023-09-04", "2023-11-23", "2023-12-25",
			"2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
			"2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
			"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
			"2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24" });

		private class St
		{
			public long? aM, bM, aT, bT;
			public bool aDone, bDone, aTook, bTook, aTgT, bTgT, aPre;
			public double? aLv, bLv;
		}

		private class Sess
		{
			public double? aHi, aLo, bHi, bLo, aTgH, bTgH, aTgL, bTgL;
			public St hi, lo;
			public long aHiM, bHiM, aLoM, bLoM;
			public bool maHi, mbHi, maLo, mbLo;
		}

		private class Lv
		{
			public double a, b;
			public bool isHi, dead;
			public St st = new St();
			public long tm;
		}

		private class Arm
		{
			public bool side;
			public double? va, vb;
			public string info, names;
			public long t;
		}

		private class Hit
		{
			public bool fired, isShort, swHi, swLo, sHi, sLo;
			public double? lvl;
			public string src = "", who = "", info = "";
			public List<Arm> varmList = new List<Arm>();
		}

		private class Frisk
		{
			public long m;
			public double lv;
			public string key;
			public bool brugt;
		}

		private class VSide
		{
			public List<Frisk> aF = new List<Frisk>(), bF = new List<Frisk>();
			public long? aE, bE, aFM, bFM, xT;
			public double? aFL, bFL;
			public bool neu, had;
		}

		private class Aaben
		{
			public bool kort, beHit, early, noBE;
			public double entry, sl, tp;
			public double? be;
			public int bars;
			public SmtHandel rec;
		}

		// 15m/5m-aggregat: seneste afsluttede candle (key, high, low) og den igangvaerende
		private class Agg
		{
			private readonly long sek;
			public long? curKey, prevKey;
			public double curH, curL, prevH, prevL;
			public Agg(long s) { sek = s; }
			public void Add(long t, double h, double l)
			{
				long k = FloorDiv(t, sek) * sek;
				if (curKey.HasValue && curKey.Value == k) { curH = Math.Max(curH, h); curL = Math.Min(curL, l); return; }
				if (curKey.HasValue) { prevKey = curKey; prevH = curH; prevL = curL; }
				curKey = k; curH = h; curL = l;
			}
			// sidste candle med start foer p (scriptets prev_period)
			public bool Foer(long p, out long key, out double h, out double l)
			{
				if (curKey.HasValue && curKey.Value < p) { key = curKey.Value; h = curH; l = curL; return true; }
				if (prevKey.HasValue && prevKey.Value < p) { key = prevKey.Value; h = prevH; l = prevL; return true; }
				key = 0; h = l = 0; return false;
			}
		}

		public readonly bool Vrg;
		private readonly TimeZoneInfo newYork;
		private static readonly DateTime epoke = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
		public readonly List<SmtHandel> Handler = new List<SmtHandel>();

		// ES fyldt frem: senest modtagne ES-bar og den der bruges (kun opdateret naar ES har en bar paa NQ-barens tid)
		private bool bok;
		private double esO, esH, esL, esC;
		private long esT = long.MinValue;
		private double nyO, nyH, nyL, nyC;
		private readonly Agg g15a = new Agg(900), g05a = new Agg(300), g15b = new Agg(900), g05b = new Agg(300);

		private readonly Sess asia = new Sess(), lon = new Sess(), ny = new Sess();
		private List<Lv> lv15 = new List<Lv>(), lv05 = new List<Lv>();
		private bool prevA, prevL, prevN;
		private long? lastQt, lastFt;
		private int? prevMn;
		private double? m1Hi, m1Lo;
		private long? prevQ15;
		private double? aq15Hi, aq15Lo, bq15Hi, bq15Lo;
		private long? lastMin;
		private double[] curMinOHLC;
		private bool dAct, uAct;
		private double dTop, dBot, uTop, uBot;
		private double? preD, preU, pDT, pDB, pUB, pUT;
		private long? preDHitM, preUHitM;
		private long? lastTradeM;
		private List<Arm> vArms = new List<Arm>();
		private readonly Dictionary<bool, VSide> vSide = new Dictionary<bool, VSide>();
		private string vDay, resetDay;
		private readonly List<KeyValuePair<long, double>> hitsD = new List<KeyValuePair<long, double>>(), hitsU = new List<KeyValuePair<long, double>>(),
			hitsSH = new List<KeyValuePair<long, double>>(), hitsSL = new List<KeyValuePair<long, double>>();
		private readonly Dictionary<string, int> nyCnt = new Dictionary<string, int>();
		private long? curM;
		private bool mHi, mLo, mBad;
		private Aaben o;

		// pr. bar
		private long t, minB;
		private int tMin;
		private bool inWin, is369;
		private double hi, lo, cl, op, bh, bl, bc, bo;
		private Hit h;

		public SmtMotor(bool vergence)
		{
			Vrg = vergence;
			newYork = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
			vSide[true] = new VSide();
			vSide[false] = new VSide();
		}

		public bool HarAaben { get { return o != null; } }

		private DateTime NyTid(long u) { return TimeZoneInfo.ConvertTimeFromUtc(epoke.AddSeconds(u), newYork); }

		public void PaaEs(long tt, double eo, double eh, double el, double ec)
		{
			esT = tt; nyO = eo; nyH = eh; nyL = el; nyC = ec;
			g15b.Add(tt, eh, el);
			g05b.Add(tt, eh, el);
		}

		public List<SmtBegivenhed> PaaNq(long tt, DateTime lt, double o_, double h_, double l_, double c_)
		{
			List<SmtBegivenhed> ud = new List<SmtBegivenhed>();
			t = tt; op = o_; hi = h_; lo = l_; cl = c_;
			if (esT == t) { bok = true; esO = nyO; esH = nyH; esL = nyL; esC = nyC; }
			bh = esH; bl = esL; bc = esC; bo = esO;
			g15a.Add(t, hi, lo);
			g05a.Add(t, hi, lo);
			tMin = lt.Hour * 60 + lt.Minute;
			inWin = tMin >= WIN_S && tMin < WIN_E;
			bool isOpenM = tMin == WIN_S;
			int ds = lt.Minute / 10 + lt.Minute % 10;
			is369 = ds == 3 || ds == 6 || ds == 9;
			minB = FloorDiv(t, 60);
			string dstr = lt.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
			DateTime dk = lt.AddHours(6);

			bool newMin = !prevMn.HasValue || lt.Minute != prevMn.Value;
			prevMn = lt.Minute;
			m1Hi = newMin || !m1Hi.HasValue ? hi : Math.Max(m1Hi.Value, hi);
			m1Lo = newMin || !m1Lo.HasValue ? lo : Math.Min(m1Lo.Value, lo);
			long q15B = FloorDiv(t, 900);
			bool newQ15 = !prevQ15.HasValue || q15B != prevQ15.Value;
			prevQ15 = q15B;
			aq15Hi = newQ15 || !aq15Hi.HasValue ? hi : Math.Max(aq15Hi.Value, hi);
			aq15Lo = newQ15 || !aq15Lo.HasValue ? lo : Math.Min(aq15Lo.Value, lo);
			if (bok)
			{
				bq15Hi = newQ15 || !bq15Hi.HasValue ? bh : Math.Max(bq15Hi.Value, bh);
				bq15Lo = newQ15 || !bq15Lo.HasValue ? bl : Math.Min(bq15Lo.Value, bl);
			}

			bool aOn = tMin >= 20 * 60 || tMin < 2 * 60, lOn = tMin >= 2 * 60 && tMin < 8 * 60, nOn = tMin >= 8 * 60 && tMin < WIN_S;
			if (nOn) { int n; nyCnt.TryGetValue(dstr, out n); nyCnt[dstr] = n + 1; }
			bool aStart = aOn && !prevA, lStart = lOn && !prevL, nStart = nOn && !prevN;
			prevA = aOn; prevL = lOn; prevN = nOn;

			Merge(asia, aOn);
			Merge(lon, lOn);
			if (aOn) Build(asia, aStart, q15B);
			if (lOn) Build(lon, lStart, q15B);
			if (nOn) Build(ny, nStart, q15B);

			// 15m / 5m niveauer fra NY PRE
			long k15 = FloorDiv(t, 900) * 900, k05 = FloorDiv(t, 300) * 300;
			long qT, fT, eT, gT;
			double qah, qal, fah, fal, qbh, qbl, fbh, fbl;
			bool harQ = g15a.Foer(k15, out qT, out qah, out qal);
			bool harF = g05a.Foer(k05, out fT, out fah, out fal);
			bool newM15 = harQ && (!lastQt.HasValue || qT != lastQt.Value);
			if (newM15) lastQt = qT;
			bool newM05 = harF && (!lastFt.HasValue || fT != lastFt.Value);
			if (newM05) lastFt = fT;
			if (nStart) { lv15 = new List<Lv>(); lv05 = new List<Lv>(); }
			if (newM15 && INyPre(qT) && g15b.Foer(k15, out eT, out qbh, out qbl))
			{
				lv15.Add(new Lv { a = qah, b = qbh, isHi = true, tm = qT });
				lv15.Add(new Lv { a = qal, b = qbl, isHi = false, tm = qT });
			}
			if (newM05 && INyPre(fT) && g05b.Foer(k05, out gT, out fbh, out fbl))
			{
				lv05.Add(new Lv { a = fah, b = fbh, isHi = true });
				lv05.Add(new Lv { a = fal, b = fbl, isHi = false });
			}
			if (nOn)
			{
				foreach (Lv m in Kaede(lv15, lv05))
				{
					bool aHit = m.isHi ? hi >= m.a : lo <= m.a;
					bool bHit = bok && (m.isHi ? bh >= m.b : bl <= m.b);
					if (aHit || bHit) m.dead = true;
				}
			}
			else
			{
				foreach (Lv m in Kaede(lv05, tMin >= M15_END ? lv15 : new List<Lv>()))
					if (m.isHi ? hi >= m.a : lo <= m.a) m.st.aTook = true;
			}

			// tjek niveauer
			if (Vrg && inWin && vDay != dstr)
			{
				vDay = dstr;
				vSide[true] = new VSide();
				vSide[false] = new VSide();
			}
			h = new Hit();
			if (!nOn)
			{
				double? a1, b1;
				Tg(ny, true, out a1, out b1); Check(ny.hi, ny.aHi, ny.bHi, true, "NY PRE", a1, b1, null);
				Tg(ny, false, out a1, out b1); Check(ny.lo, ny.aLo, ny.bLo, false, "NY PRE", a1, b1, null);
			}
			if (!lOn)
			{
				double? a1, b1;
				if (!(lon.maHi || lon.mbHi)) { Tg(lon, true, out a1, out b1); Check(lon.hi, lon.aHi, lon.bHi, true, "London", a1, b1, null); }
				if (!(lon.maLo || lon.mbLo)) { Tg(lon, false, out a1, out b1); Check(lon.lo, lon.aLo, lon.bLo, false, "London", a1, b1, null); }
			}
			if (!aOn)
			{
				double? a1, b1;
				if (!(asia.maHi || asia.mbHi)) { Tg(asia, true, out a1, out b1); Check(asia.hi, asia.aHi, asia.bHi, true, "Asia", a1, b1, null); }
				if (!(asia.maLo || asia.mbLo)) { Tg(asia, false, out a1, out b1); Check(asia.lo, asia.aLo, asia.bLo, false, "Asia", a1, b1, null); }
			}
			if (!nOn && tMin < M15_END)
			{
				foreach (Lv m in lv15)
				{
					double ext = m.isHi ? (ny.aHi ?? 0) : (ny.aLo ?? 0);
					bool isExt = Math.Abs(m.a - ext) < TICK / 2;
					if (!m.dead && !isExt)
						Check(m.st, m.a, m.b, m.isHi, "15m", null, null, NyTid(m.tm).AddHours(6).ToString("HH:mm", CultureInfo.InvariantCulture));
				}
			}

			// EQ paa 1m: vurder den netop lukkede minut-candle paa foerste bar i et nyt minut
			bool new1m = lastMin.HasValue && minB != lastMin.Value;
			double[] prevMin = null;
			bool bearE = false, bullE = false;
			if (new1m)
			{
				prevMin = (double[])curMinOHLC.Clone();
				double own = (prevMin[1] + prevMin[2]) / 2;
				bearE = prevMin[3] < prevMin[0] && prevMin[3] < own;
				bullE = prevMin[3] > prevMin[0] && prevMin[3] > own;
				if (inWin && tMin == WIN_S) bearE = bullE = false;
			}
			if (!lastMin.HasValue || minB != lastMin.Value) { curMinOHLC = new double[] { op, hi, lo, cl }; lastMin = minB; }
			else { curMinOHLC[1] = Math.Max(curMinOHLC[1], hi); curMinOHLC[2] = Math.Min(curMinOHLC[2], lo); curMinOHLC[3] = cl; }
			if (inWin && resetDay != dstr) { resetDay = dstr; dAct = uAct = false; }
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
			// EQ foer market open (til BE) - laases fra 09:30 og vokser videre indtil den rammes
			if (tMin < WIN_S)
			{
				preD = dAct ? (dTop + dBot) / 2 : (double?)null;
				preU = uAct ? (uBot + uTop) / 2 : (double?)null;
				pDT = dAct ? dTop : (double?)null; pDB = dAct ? dBot : (double?)null;
				pUB = uAct ? uBot : (double?)null; pUT = uAct ? uTop : (double?)null;
				preDHitM = preUHitM = null;
			}
			else
			{
				bool gfD = cl > op, gfU = cl < op;
				if (!preDHitM.HasValue && pDT.HasValue)
				{
					if (gfD) pDB = Math.Min(pDB.Value, lo);
					if (hi >= (pDT.Value + pDB.Value) / 2) preDHitM = minB;
					else if (!gfD) pDB = Math.Min(pDB.Value, lo);
					preD = (pDT.Value + pDB.Value) / 2;
				}
				if (!preUHitM.HasValue && pUB.HasValue)
				{
					if (gfU) pUT = Math.Max(pUT.Value, hi);
					if (lo <= (pUB.Value + pUT.Value) / 2) preUHitM = minB;
					else if (!gfU) pUT = Math.Max(pUT.Value, hi);
					preU = (pUB.Value + pUT.Value) / 2;
				}
				// 09:29-candlen lukker foer open: dens EQ er ogsaa en "EQ foer open"
				if (new1m && tMin == WIN_S && resetDay == dstr)
				{
					double own = (prevMin[1] + prevMin[2]) / 2;
					if (prevMin[3] < prevMin[0] && prevMin[3] < own && !pDT.HasValue)
					{ pDT = prevMin[1]; pDB = Math.Min(prevMin[2], lo); preDHitM = null; preD = (pDT.Value + pDB.Value) / 2; }
					if (prevMin[3] > prevMin[0] && prevMin[3] > own && !pUB.HasValue)
					{ pUB = prevMin[2]; pUT = Math.Max(prevMin[1], hi); preUHitM = null; preU = (pUB.Value + pUT.Value) / 2; }
				}
			}

			// minut-status: high- og low-side taget i samme minut -> ingen nye handler i minuttet
			if (!curM.HasValue || minB != curM.Value) { curM = minB; mHi = mLo = mBad = false; }
			if (inWin) { mHi = mHi || h.swHi; mLo = mLo || h.swLo; }
			if (mHi && mLo && !mBad) mBad = true;

			// aaben handel
			if (o != null)
			{
				bool hitSL = o.kort ? hi >= o.sl : lo <= o.sl;
				bool hitTP = o.kort ? lo <= o.tp : hi >= o.tp;
				if (hitSL || hitTP)
				{
					SmtHandel tr = o.rec;
					double pts, px;
					if (hitSL) { pts = o.kort ? o.entry - o.sl : o.sl - o.entry; tr.Resultat = o.beHit ? "BE" : "SL"; px = o.sl; }
					else { pts = Math.Abs(o.tp - o.entry); tr.Resultat = "TP"; px = o.tp; }
					tr.Points = Math.Round(pts, 2);
					tr.R = Math.Round(pts / 10.0, 2);
					tr.Exit = dk.ToString("HH:mm:ss", CultureInfo.InvariantCulture);
					ud.Add(new SmtBegivenhed(SmtType.Lukket, tr, px));
					o = null;
				}
				else
				{
					if (!o.beHit && o.be.HasValue && !o.noBE)
					{
						bool touch = o.kort ? lo <= o.be.Value : hi >= o.be.Value;
						if (o.bars < 2)
						{
							if (touch) o.early = true;
							if (o.bars == 1 && o.early)
							{
								if (o.kort ? cl < o.entry : cl > o.entry) { o.beHit = true; o.sl = o.entry; ud.Add(new SmtBegivenhed(SmtType.Be, o.rec, o.entry)); }
								else o.noBE = true;
							}
						}
						else if (touch) { o.beHit = true; o.sl = o.entry; ud.Add(new SmtBegivenhed(SmtType.Be, o.rec, o.entry)); }
					}
					o.bars++;
				}
			}

			// Vergence: en side er klar, naar begge indeks har taget samme niveau frisk hoejst 5 min fra hinanden
			if (Vrg) VergenceArme(dstr);

			if (h.fired && lastTradeM.HasValue && lastTradeM.Value == minB) h.fired = false;      // eet trade pr. minut
			if (h.fired)
			{
				int n; nyCnt.TryGetValue(dstr, out n);
				if (NO_TRADE_DAYS.Contains(dstr) || n < NYPRE_MIN_BARS) h.fired = false;
			}
			if (h.fired && !mBad) NyHandel(lt, dk, isOpenM, ud);

			// gamle "ramt"-markeringer bruges kun i indevaerende minut
			Trim(hitsD); Trim(hitsU); Trim(hitsSH); Trim(hitsSL);
			return ud;
		}

		private void Trim(List<KeyValuePair<long, double>> L)
		{
			long graense = minB * 60 - 120;
			L.RemoveAll(x => x.Key < graense);
		}

		private static IEnumerable<Lv> Kaede(List<Lv> a, List<Lv> b)
		{
			foreach (Lv x in a) yield return x;
			foreach (Lv x in b) yield return x;
		}

		private bool INyPre(long pt)
		{
			DateTime d = NyTid(pt);
			int m = d.Hour * 60 + d.Minute;
			return m >= 8 * 60 && m < WIN_S;
		}

		private void Build(Sess s, bool isStart, long q15B)
		{
			if (isStart)
			{
				s.aHi = hi; s.aLo = lo;
				if (bok) { s.bHi = bh; s.bLo = bl; } else { s.bHi = null; s.bLo = null; }
				s.hi = new St(); s.lo = new St();
				s.aHiM = s.bHiM = s.aLoM = s.bLoM = q15B;
				s.aTgH = s.bTgH = s.aTgL = s.bTgL = null;
				s.maHi = s.mbHi = s.maLo = s.mbLo = false;
			}
			else
			{
				if (hi >= s.aHi.Value) s.aHiM = q15B;
				if (lo <= s.aLo.Value) s.aLoM = q15B;
				if (bok && (!s.bHi.HasValue || bh >= s.bHi.Value)) s.bHiM = q15B;
				if (bok && (!s.bLo.HasValue || bl <= s.bLo.Value)) s.bLoM = q15B;
				s.aHi = Math.Max(s.aHi.Value, hi); s.aLo = Math.Min(s.aLo.Value, lo);
				if (bok)
				{
					s.bHi = s.bHi.HasValue ? Math.Max(s.bHi.Value, bh) : bh;
					s.bLo = s.bLo.HasValue ? Math.Min(s.bLo.Value, bl) : bl;
				}
			}
			if (s.aHiM == q15B) s.bTgH = bq15Hi;
			if (s.bHiM == q15B) s.aTgH = aq15Hi;
			if (s.aLoM == q15B) s.bTgL = bq15Lo;
			if (s.bLoM == q15B) s.aTgL = aq15Lo;
		}

		private void Tg(Sess s, bool isHi, out double? a, out double? b)
		{
			a = b = null;
			if (isHi ? (s.maHi || s.mbHi) : (s.maLo || s.mbLo)) return;
			if (isHi && s.aHiM != s.bHiM) { a = s.aTgH; b = s.bTgH; }
			if (!isHi && s.aLoM != s.bLoM) { a = s.aTgL; b = s.bTgL; }
		}

		// Tager et indeks en tidligere sessions high/low i en senere session (foer open), flytter niveauet med
		private void Merge(Sess s, bool on)
		{
			if (on || !s.aHi.HasValue || tMin >= WIN_S) return;
			if (hi > s.aHi.Value) { s.aHi = hi; s.maHi = true; }
			if (lo < s.aLo.Value) { s.aLo = lo; s.maLo = true; }
			if (bok && s.bHi.HasValue && bh > s.bHi.Value) { s.bHi = bh; s.mbHi = true; }
			if (bok && s.bLo.HasValue && bl < s.bLo.Value) { s.bLo = bl; s.mbLo = true; }
		}

		private void Check(St st, double? aLn, double? bLn, bool isHi, string nm, double? aTg, double? bTg, string tag)
		{
			if (st == null || !aLn.HasValue || !bLn.HasValue) return;
			double aL = aLn.Value, bL = bLn.Value;
			bool aSweep = isHi ? hi >= aL + TICK : lo <= aL - TICK;
			bool bSweep = bok && (isHi ? bh >= bL + TICK : bl <= bL - TICK);
			string lvlNm = nm + (isHi ? " high" : " low");
			string vKey = lvlNm + (tag != null ? " " + tag : "");
			if (inWin && aSweep && !st.aTook && nm != "15m")
			{
				if (isHi) { h.sHi = true; hitsSH.Add(new KeyValuePair<long, double>(t, aL)); }
				else { h.sLo = true; hitsSL.Add(new KeyValuePair<long, double>(t, aL)); }
			}
			if (aSweep) st.aTook = true;
			if (bSweep) st.bTook = true;
			bool newTg = false;
			if (inWin && aTg.HasValue && !st.aTgT && (isHi ? (aTg.Value < aL && hi >= aTg.Value + TICK) : (aTg.Value > aL && lo <= aTg.Value - TICK)))
				st.aTgT = newTg = true;
			if (inWin && bok && bTg.HasValue && !st.bTgT && (isHi ? (bTg.Value < bL && bh >= bTg.Value + TICK) : (bTg.Value > bL && bl <= bTg.Value - TICK)))
				st.bTgT = newTg = true;
			bool aTk = st.aTook || st.aTgT, bTk = st.bTook || st.bTgT;

			if (Vrg)
			{
				// et niveau taget foerste gang i vinduet = FRISK liq; bagefter flytter det med til indeksets nye yderpunkt
				if (!inWin) return;
				double curA = st.aLv ?? aL, curB = st.bLv ?? bL;
				bool nA = isHi ? hi >= curA + TICK : lo <= curA - TICK;
				bool nB = bok && (isHi ? bh >= curB + TICK : bl <= curB - TICK);
				VSide sd = vSide[isHi];
				if (nA)
				{
					if (!st.aLv.HasValue)
					{
						sd.aF.Add(new Frisk { m = minB, lv = aL, key = vKey });
						sd.aFL = (!sd.aFM.HasValue || sd.aFM.Value != minB || !sd.aFL.HasValue) ? aL : (isHi ? Math.Max(sd.aFL.Value, aL) : Math.Min(sd.aFL.Value, aL));
						sd.aFM = minB;
					}
					if (curA == aL || !sd.had) { sd.aE = minB; sd.neu = true; }
					st.aLv = isHi ? hi : lo;
				}
				if (nB)
				{
					if (!st.bLv.HasValue)
					{
						sd.bF.Add(new Frisk { m = minB, lv = bL, key = vKey });
						sd.bFL = (!sd.bFM.HasValue || sd.bFM.Value != minB || !sd.bFL.HasValue) ? bL : (isHi ? Math.Max(sd.bFL.Value, bL) : Math.Min(sd.bFL.Value, bL));
						sd.bFM = minB;
					}
					if (curB == bL || !sd.had) { sd.bE = minB; sd.neu = true; }
					st.bLv = isHi ? bh : bl;
				}
				if (nA || nB)
				{
					sd.xT = t;
					h.swHi = h.swHi || isHi;
					h.swLo = h.swLo || !isHi;
				}
				return;
			}

			if (!inWin)
			{
				if (aSweep) { st.aDone = true; st.aPre = true; }
				if (bSweep) st.bDone = true;
				return;
			}
			bool newA = !st.aDone && !st.aM.HasValue && aSweep;
			bool newB = !st.bDone && !st.bM.HasValue && bSweep;
			if (newA) { st.aM = minB; st.aT = t; }
			if (newB) { st.bM = minB; st.bT = t; }
			if (newA || newB) { h.swHi = h.swHi || isHi; h.swLo = h.swLo || !isHi; }
			if ((newA || newB || newTg) && aTk && bTk && !(st.aDone && st.bDone)) st.aDone = st.bDone = true;
			if (!is369) { if (newA) st.aDone = true; if (newB) st.bDone = true; }
			if (!st.aDone && st.aM.HasValue && st.aM.Value != minB) st.aDone = true;
			if (!st.bDone && st.bM.HasValue && st.bM.Value != minB) st.bDone = true;
			if (!h.fired)
			{
				bool dirOK = isHi ? (cl < op && bok && bc < bo) : (cl > op && bok && bc > bo);
				bool aBack = !st.aDone && !bTk && st.aM.HasValue && st.aM.Value == minB && (isHi ? cl < aL : cl > aL);
				bool bBack = !st.bDone && !aTk && st.bM.HasValue && st.bM.Value == minB && bok && (isHi ? bc < bL : bc > bL);
				if (aBack && t - st.aT.Value > 15) aBack = false;      // entry paa sweep-candlen eller den naeste
				if (bBack && t - st.bT.Value > 15) bBack = false;
				bool slOK = isHi ? m1Hi.Value - cl <= MAX_SL : cl - m1Lo.Value <= MAX_SL;
				if (dirOK && (aBack || bBack) && !slOK) st.aDone = st.bDone = true;
				if (dirOK && (aBack || bBack) && slOK)
				{
					h.fired = true; h.isShort = isHi; h.lvl = aL; h.src = lvlNm;
					h.who = aBack && bBack ? "NQ + ES" : (aBack ? "NQ" : "ES");
					st.aDone = st.bDone = true;
				}
			}
		}

		private void VergenceArme(string dstr)
		{
			foreach (bool side in new bool[] { true, false })
			{
				VSide sd = vSide[side];
				if (sd.neu)
				{
					List<Frisk> fa = sd.aF.FindAll(f => !f.brugt && sd.bF.Exists(g => g.key == f.key && Math.Abs(g.m - f.m) <= VRG_GAP));
					List<Frisk> fb = sd.bF.FindAll(f => !f.brugt && sd.aF.Exists(g => g.key == f.key && Math.Abs(g.m - f.m) <= VRG_GAP));
					if (fa.Count > 0 || fb.Count > 0)
					{
						List<Frisk> faN = fa.FindAll(f => f.m == minB), fbN = fb.FindAll(f => f.m == minB);
						if (faN.Count > 0 || fbN.Count > 0) { fa = faN; fb = fbN; }
						HashSet<long> mA = new HashSet<long>(), mB = new HashSet<long>();
						foreach (Frisk f in fa) mA.Add(f.m);
						foreach (Frisk f in fb) mB.Add(f.m);
						fa = sd.aF.FindAll(f => mA.Contains(f.m));
						fb = sd.bF.FindAll(f => mB.Contains(f.m));
						if (VRG_SHARED)
						{
							// kun niveauer begge indeks har taget (fx 15m low 15:15) - ikke NQ's NY PRE low alene
							List<Frisk> aAll = sd.aF, bAll = sd.bF;
							fa = fa.FindAll(f => bAll.Exists(g => g.key == f.key));
							fb = fb.FindAll(f => aAll.Exists(g => g.key == f.key));
						}
						double? aLv = null, bLv = null;
						foreach (Frisk f in fa) aLv = !aLv.HasValue ? f.lv : (side ? Math.Max(aLv.Value, f.lv) : Math.Min(aLv.Value, f.lv));
						foreach (Frisk f in fb) bLv = !bLv.HasValue ? f.lv : (side ? Math.Max(bLv.Value, f.lv) : Math.Min(bLv.Value, f.lv));
						SortedSet<string> navne = new SortedSet<string>(StringComparer.Ordinal);
						foreach (Frisk f in fa) { navne.Add(f.key); f.brugt = true; }
						foreach (Frisk f in fb) { navne.Add(f.key); f.brugt = true; }
						sd.had = true;
						h.varmList.Add(new Arm { side = side, va = aLv, vb = bLv, info = "", names = string.Join(" / ", navne) });
					}
				}
				sd.neu = false;
			}
			// entry skal komme i samme minut som det sweep der fuldendte Vergence
			vArms = vArms.FindAll(v => FloorDiv(v.t, 60) == minB);
			foreach (Arm a in h.varmList)
				if (!mBad) { a.t = t; vArms.Add(a); }
			if (vArms.Count > 0 && !mBad)
			{
				List<Arm> keep = new List<Arm>();
				foreach (Arm v in vArms)
				{
					if (t - v.t > 15) continue;                          // for sent efter sweepet
					bool aD = v.side ? cl < op : cl > op;
					bool bD = bok && (v.side ? bc < bo : bc > bo);
					if (!(aD && bD)) { keep.Add(v); continue; }
					VSide sdv = vSide[v.side];
					long am = FloorDiv(v.t, 60);
					double? va = v.va, vb = v.vb;
					if (!VRG_SHARED && sdv.aFM.HasValue && sdv.aFM.Value == am && sdv.bFM.HasValue && sdv.bFM.Value == am)
					{
						if (!va.HasValue) va = sdv.aFL;
						if (!vb.HasValue) vb = sdv.bFL;
					}
					bool backA = !va.HasValue || (v.side ? cl < va.Value : cl > va.Value);
					bool backB = !vb.HasValue || (bok && (v.side ? bc < vb.Value : bc > vb.Value));
					bool slOK = v.side ? m1Hi.Value - cl <= MAX_SL : cl - m1Lo.Value <= MAX_SL;
					if (backA && backB && slOK && !h.fired)
					{
						h.fired = true; h.isShort = v.side; h.lvl = va; h.src = v.names; h.info = v.info;
						h.who = va.HasValue && vb.HasValue ? "Begge" : (va.HasValue ? "NQ" : "ES");
					}
				}
				vArms = keep;
			}
		}

		private void NyHandel(DateTime lt, DateTime dk, bool isOpenM, List<SmtBegivenhed> ud)
		{
			bool sh = h.isShort;
			double px = cl;
			// BE-kandidater: (niveau, navn, allerede taget)
			List<Tuple<double?, string, bool>> cands = new List<Tuple<double?, string, bool>>();
			bool eAct = sh ? uAct : dAct;
			if (eAct)
			{
				double elo = sh ? uBot : dBot, ehi = sh ? uTop : dTop;
				cands.Add(Tuple.Create((double?)((elo + ehi) / 2), "EQ", false));
				cands.Add(Tuple.Create((double?)(elo + (sh ? 0.75 : 0.25) * (ehi - elo)), sh ? "0.75" : "0.25", false));
			}
			if (!preDHitM.HasValue) cands.Add(Tuple.Create(preD, "EQ foer open", false));
			if (!preUHitM.HasValue) cands.Add(Tuple.Create(preU, "EQ foer open", false));
			foreach (Tuple<string, Sess> ns in new Tuple<string, Sess>[] { Tuple.Create("Asia", asia), Tuple.Create("London", lon), Tuple.Create("NY PRE", ny) })
			{
				St st = sh ? ns.Item2.lo : ns.Item2.hi;
				if (st != null && !st.aPre)
					cands.Add(Tuple.Create(sh ? ns.Item2.aLo : ns.Item2.aHi, ns.Item1 + (sh ? " low" : " high"), st.aTook));
			}
			foreach (Lv m in lv15)
				if (m.isHi != sh && !m.dead && !m.st.aTook) cands.Add(Tuple.Create((double?)m.a, sh ? "15m low" : "15m high", false));
			if (isOpenM)
				foreach (Lv m in lv05)
					if (m.isHi != sh && !m.dead && !m.st.aTook) cands.Add(Tuple.Create((double?)m.a, sh ? "5m low" : "5m high", false));
			double? be = null;
			string beS = "-";
			bool beBad = false;
			foreach (Tuple<double?, string, bool> c in cands)
			{
				if (!c.Item1.HasValue) continue;
				double cv = c.Item1.Value, d = Math.Abs(px - cv);
				if ((sh ? cv < px : cv > px) && d >= BE_MIN && d <= BE_MAX && (!be.HasValue || d < Math.Abs(px - be.Value)))
				{ be = cv; beS = c.Item2; beBad = c.Item3; }
			}
			// liq i trade-retningen taget i entry-minuttet (foer entry-candlen) -> BE-spottet er taget
			bool eqT = AnyHit(sh ? hitsU : hitsD, sh, px), slT = AnyHit(sh ? hitsSL : hitsSH, sh, px);
			if (eqT || slT)
			{
				beBad = true;
				beS = eqT ? (sh ? "bullish EQ" : "bearish EQ") : (sh ? "session low" : "session high");
			}
			double sl = sh ? Math.Max(m1Hi.Value, px + MIN_SL) : Math.Min(m1Lo.Value, px - MIN_SL);
			List<Tuple<double, string>> tcs = new List<Tuple<double, string>>();
			if (uAct) tcs.Add(Tuple.Create((uBot + uTop) / 2, "EQ"));
			if (dAct) tcs.Add(Tuple.Create((dBot + dTop) / 2, "EQ"));
			foreach (Tuple<string, Sess> ns in new Tuple<string, Sess>[] { Tuple.Create("Asia", asia), Tuple.Create("London", lon), Tuple.Create("NY PRE", ny) })
			{
				St st = sh ? ns.Item2.lo : ns.Item2.hi;
				double? v = sh ? ns.Item2.aLo : ns.Item2.aHi;
				if (st != null && !st.aTook && v.HasValue) tcs.Add(Tuple.Create(v.Value, ns.Item1 + (sh ? " low" : " high")));
			}
			double? tp = null;
			string tpS = "75p";
			foreach (Tuple<double, string> c in tcs)
			{
				double d = sh ? px - c.Item1 : c.Item1 - px;
				if (d >= TP_MIN && d <= TP_MAX && (!tp.HasValue || d < Math.Abs(px - tp.Value))) { tp = c.Item1; tpS = c.Item2; }
			}
			if (!tp.HasValue) tp = sh ? px - TP_MAX : px + TP_MAX;

			SmtHandel rec = new SmtHandel
			{
				Dato = lt.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture), Tid = dk.ToString("HH:mm:ss", CultureInfo.InvariantCulture), Kort = sh, Niveau = h.src, Swept = h.who, Info = h.info,
				Entry = px, Be = be, BeKilde = beS, T = t
			};
			if (beBad)
			{
				rec.Status = "UGYLDIG (BE allerede ramt)";
				Handler.Add(rec);
				ud.Add(new SmtBegivenhed(SmtType.Ugyldig, rec, px));
				return;
			}
			if (o != null)
			{
				o.rec.Resultat = "AFLOEST";
				o.rec.Exit = dk.ToString("HH:mm:ss", CultureInfo.InvariantCulture);
				ud.Add(new SmtBegivenhed(SmtType.Afloest, o.rec, px));
			}
			rec.Sl = sl; rec.Tp = tp; rec.TpKilde = tpS; rec.Status = "OK"; rec.Resultat = "AABEN";
			Handler.Add(rec);
			ud.Add(new SmtBegivenhed(SmtType.Ny, rec, px));
			lastTradeM = minB;
			o = new Aaben { kort = sh, entry = px, sl = sl, tp = tp.Value, be = be, rec = rec };
		}

		private bool AnyHit(List<KeyValuePair<long, double>> hits, bool sh, double px)
		{
			long m0 = minB * 60;
			foreach (KeyValuePair<long, double> x in hits)
				if (x.Key >= m0 && x.Key < t)
				{
					double d = sh ? px - x.Value : x.Value - px;
					if (d >= -BE_MIN) return true;
				}
			return false;
		}

		private static long FloorDiv(long a, long b) { long q = a / b; if ((a % b != 0) && ((a < 0) != (b < 0))) q--; return q; }
	}
}
