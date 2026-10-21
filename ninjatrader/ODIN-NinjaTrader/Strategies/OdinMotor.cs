// ODIN - regelkernen for swing og market open, bar for bar. Port af motor/model.py (Python) til C#.
// Ingen NinjaTrader-afhaengigheder, saa den kan testes uden for NinjaTrader mod Python-motoren.
// Kun de regler planen bruger er med (brugt-regel "asset", vending = farve paa begge, fast stop i point,
// ingen strukturstop, ingen loebende formarked, ingen aktiv-sweep).
//
// INDDATA  PaaBar(t, ny, o, h, l, c, harE, eo, eh, el, ec) for hver 15-sekunders NQ-bar i tidsorden.
//          t = barens START i unix-sekunder, ny = barens start i New York-tid.
//          ES-baren med samme start, eller harE = false hvis ES ikke har en bar dér.
// UDDATA   liste af MotorOrdre - markedsordre ved barens luk med stop/TP/tidsudgang i point.
//
// REGLER (Magnus 2026-09-29 og plan 10/10)
//   niveauer   London 02:00-08:00 NY og formarked 08:00-09:00 NY, high/low paa NQ og ES
//   brugt      London-niveauer der er ramt 08:00-08:45 NY er brugt op (pr. asset)
//   vindue     fra VindueStart (08:45 NY) til (ikke med) baren der starter 09:29:45. Formarkedet taeller fra 09:00
//   sweep      beroering taeller. Et niveau taeller foerst naar BEGGE har taget samme niveau
//   minut      et nyt faelles niveau aabner sit minut, og det naeste hvis det skete i sidste 15 s
//   entry      foerste bar i et aabent minut hvor NQ og ES lukker modsat (close < open for short) -> swing
//   MO-retning swing TABT foer 09:29:45 -> modsat; aaben eller vundet -> samme vej; ingen swing -> ingen
//   MO         entry ved luk af 09:29:45-baren, ud ved luk af 09:30:45-baren
//   rv5        snit af de 5 foregaaende RTH-dages true range i % >= graensen -> ingen handler den dag

using System;
using System.Collections.Generic;

namespace NinjaTrader.NinjaScript.Strategies.Odin
{
	public class MotorIndstillinger
	{
		public double SwStop = 10.0;        // point
		public double SwTp = 175.0;         // point, 0 = intet
		public int SwSek = 4 * 3600;        // tidsudgang efter entry (bruges naar SwUdNy = 0)
		public int SwUdNy = 0;              // >0: luk swingen paa dette klokkeslaet NY (sekunder efter midnat)
		public double SwBe = 0.0;           // point i plus der flytter stoppet til entry (0 = intet)
		public double SwBeLaas = 0.0;
		public double MoStop = 30.0;
		public double MoTp = 0.0;
		public double Rv5Graense = 2.25;    // procent, 0 = slaaet fra
		public double Rv5Min = 0.0;         // kun swing: ingen swing under dette (0 = slaaet fra)
		public int MinRthBarer = 1000;
		public bool KunFormarked = false;   // kun formarkedets niveauer taeller
		public bool Fridage = false;        // ingen handler langfredag og Labor Day
		public int VindueStart = 525;       // minut efter midnat NY (525 = 08:45)

		// Planen 10/10 (motor/plan.py: swing())
		public static MotorIndstillinger PlanSwing()
		{
			MotorIndstillinger i = new MotorIndstillinger();
			i.SwStop = 40.0; i.SwTp = 0.0; i.SwUdNy = 11 * 3600; i.SwBe = 75.0;
			i.Rv5Graense = 2.0; i.Rv5Min = 1.0; i.Fridage = true; i.KunFormarked = true;
			return i;
		}

		// Market open som maalt (motor/plan_mo.py: Indstillinger(rv5_graense=2.25, fridage=True)).
		// Retningen afgoeres af den OPRINDELIGE swing-regel (London + formarked, status med stop 10 / TP 175).
		public static MotorIndstillinger MarketOpen()
		{
			MotorIndstillinger i = new MotorIndstillinger();
			i.Rv5Graense = 2.25; i.Fridage = true;
			return i;
		}
	}

	public class MotorOrdre
	{
		public string Navn;      // "SWING" eller "MO"
		public bool Kort;
		public double StopPt;    // 0 = intet stop
		public double TpPt;      // 0 = intet TP
		public long UdTid;       // luk ved lukket af den foerste bar der slutter >= denne tid (unix)
		public long T;           // start af baren ordren kom paa (fyldes ved dens luk)
		public double BePt;
		public double BeLaas;

		public override string ToString()
		{
			return string.Format("{0} {1} stop {2} tp {3}", Navn, Kort ? "SHORT" : "LONG", StopPt, TpPt);
		}
	}

	public class Motor
	{
		public readonly MotorIndstillinger Ind;
		public double? Rv5;
		public string MoRetning;            // "SHORT" / "LONG" / "INGEN" / "SPRING OVER"
		public readonly List<string> Log = new List<string>();

		private DateTime? dag;
		private readonly List<double> trp = new List<double>();
		private double[] rth;               // o, h, l, c, antal barer
		private double? forrigeLuk;

		// niveauer: 0 nLH, 1 nLL, 2 nPH, 3 nPL, 4 eLH, 5 eLL, 6 ePH, 7 ePL
		private const int NLH = 0, NLL = 1, NPH = 2, NPL = 3, ELH = 4, ELL = 5, EPH = 6, EPL = 7;
		private readonly double?[] niv = new double?[8];
		private readonly bool[] taget = new bool[8];
		private readonly bool[] brugt = new bool[8];      // kun London-niveauerne bruges
		private int sidstNH, sidstNL;
		private long fraH, tilH, fraL, tilL;

		// swingen (ogsaa naar den ikke handles - market open bruger dens status)
		private bool harSw;
		private bool swKort;
		private double swE, swStop;
		private long swT;
		private string swStatus;            // "aaben" / "tabt" / "vundet"
		private bool moGivet;

		public Motor(MotorIndstillinger ind)
		{
			Ind = ind;
			Nulstil();
		}

		public bool HarSwing { get { return harSw; } }
		public bool SwingKort { get { return swKort; } }
		public string SwingStatus { get { return swStatus; } }

		private void Nulstil()
		{
			for (int i = 0; i < 8; i++) { niv[i] = null; taget[i] = false; brugt[i] = false; }
			sidstNH = sidstNL = 0;
			fraH = tilH = fraL = tilL = 0;
			harSw = false; swStatus = null;
			moGivet = false;
			MoRetning = null;
		}

		private void NyDag()
		{
			if (rth != null && rth[4] > Ind.MinRthBarer)
			{
				double h = rth[1], l = rth[2], c = rth[3];
				if (forrigeLuk.HasValue)
				{
					double pc = forrigeLuk.Value;
					trp.Add(Math.Max(h - l, Math.Max(Math.Abs(h - pc), Math.Abs(l - pc))) / c * 100.0);
				}
				forrigeLuk = c;
			}
			rth = null;
			if (trp.Count >= 5)
			{
				double s = 0;
				for (int i = trp.Count - 5; i < trp.Count; i++) s += trp[i];
				Rv5 = s / 5.0;
			}
			else
				Rv5 = null;
			Nulstil();
		}

		// stop/TP i point rundet til tick (0,25)
		private static double Pt(double x)
		{
			return x != 0 ? Math.Round(x * 4.0, MidpointRounding.ToEven) / 4.0 : 0.0;
		}

		public bool HandelTilladt()
		{
			if (Ind.Fridage && dag.HasValue && ErFridag(dag.Value))
				return false;
			double g = Ind.Rv5Graense;
			return !(g > 0 && Rv5.HasValue && Rv5.Value >= g);
		}

		public static DateTime Paaske(int aar)
		{
			int a = aar % 19, b = aar / 100, c = aar % 100;
			int d = b / 4, e = b % 4;
			int f = (b + 8) / 25;
			int g = (b - f + 1) / 3;
			int h = (19 * a + b - d - g + 15) % 30;
			int i = c / 4, k = c % 4;
			int l = (32 + 2 * e + 2 * i - h - k) % 7;
			int m = (a + 11 * h + 22 * l) / 451;
			int mdr = (h + l - 7 * m + 114) / 31;
			int dg = ((h + l - 7 * m + 114) % 31) + 1;
			return new DateTime(aar, mdr, dg);
		}

		public static bool ErFridag(DateTime d)
		{
			if (d.Month == 9 && d.DayOfWeek == DayOfWeek.Monday && d.Day <= 7)
				return true;                                      // Labor Day
			return d.Date == Paaske(d.Year).AddDays(-2);          // langfredag
		}

		private static double? Maks(double? a, double b) { return a.HasValue ? Math.Max(a.Value, b) : b; }
		private static double? Min(double? a, double b) { return a.HasValue ? Math.Min(a.Value, b) : b; }

		public List<MotorOrdre> PaaBar(long t, DateTime ny, double o, double h, double l, double c,
		                              bool harE, double eo, double eh, double el, double ec)
		{
			int nyMin = ny.Hour * 60 + ny.Minute;
			int nySek = nyMin * 60 + ny.Second;
			if (!dag.HasValue || dag.Value != ny.Date)
			{
				dag = ny.Date;
				NyDag();
			}
			List<MotorOrdre> ud = new List<MotorOrdre>();

			// RTH til rv5 (09:30-16:00 NY)
			if (nyMin >= 570 && nyMin < 960)
			{
				if (rth == null)
					rth = new double[] { o, h, l, c, 1 };
				else
				{
					rth[1] = Math.Max(rth[1], h);
					rth[2] = Math.Min(rth[2], l);
					rth[3] = c;
					rth[4] += 1;
				}
			}
			// niveauer
			if (nyMin >= 120 && nyMin < 480)
			{
				niv[NLH] = Maks(niv[NLH], h);
				niv[NLL] = Min(niv[NLL], l);
				if (harE) { niv[ELH] = Maks(niv[ELH], eh); niv[ELL] = Min(niv[ELL], el); }
			}
			if (nyMin >= 480 && nyMin < 540)
			{
				niv[NPH] = Maks(niv[NPH], h);
				niv[NPL] = Min(niv[NPL], l);
				if (harE) { niv[EPH] = Maks(niv[EPH], eh); niv[EPL] = Min(niv[EPL], el); }
			}
			if (nyMin >= 480 && nyMin < 525)
			{
				if (niv[NLH].HasValue && h >= niv[NLH].Value) brugt[NLH] = true;
				if (niv[NLL].HasValue && l <= niv[NLL].Value) brugt[NLL] = true;
				if (harE && niv[ELH].HasValue && eh >= niv[ELH].Value) brugt[ELH] = true;
				if (harE && niv[ELL].HasValue && el <= niv[ELL].Value) brugt[ELL] = true;
			}

			const int tBeslut = 9 * 3600 + 29 * 60 + 45;       // 09:29:45 NY
			// swingens status til market open-retningen (barer efter entry, foer 09:29:45-baren)
			if (harSw && swStatus == "aaben" && t > swT && nySek < tBeslut)
			{
				double tp = Pt(Ind.SwTp);
				bool stopR, tpR;
				if (swKort) { stopR = h >= swE + swStop; tpR = l <= swE - tp; }
				else { stopR = l <= swE - swStop; tpR = h >= swE + tp; }
				if (stopR) swStatus = "tabt";
				else if (tpR) swStatus = "vundet";
			}

			// find swingen
			if (nyMin >= Ind.VindueStart && nySek < tBeslut && !harSw)
			{
				Sweep(h, l, harE, eh, el, nyMin >= 540);
				int nH, nL;
				if (Ind.KunFormarked)
				{
					nH = (taget[NPH] && taget[EPH]) ? 1 : 0;
					nL = (taget[NPL] && taget[EPL]) ? 1 : 0;
				}
				else
				{
					nH = ((taget[NLH] && taget[ELH]) ? 1 : 0) + ((taget[NPH] && taget[EPH]) ? 1 : 0);
					nL = ((taget[NLL] && taget[ELL]) ? 1 : 0) + ((taget[NPL] && taget[EPL]) ? 1 : 0);
				}
				long minNr = FloorDiv(t, 60);
				bool s15 = Mod(t, 60) == 45;
				if (nH > sidstNH) { fraH = minNr; tilH = s15 ? minNr + 1 : minNr; sidstNH = nH; }
				if (nL > sidstNL) { fraL = minNr; tilL = s15 ? minNr + 1 : minNr; sidstNL = nL; }
				bool ned = harE && c < o && ec < eo;
				bool op = harE && c > o && ec > eo;
				bool kortOK = nH > 0 && ned && fraH <= minNr && minNr <= tilH;
				bool langOK = nL > 0 && op && fraL <= minNr && minNr <= tilL;
				if (kortOK || langOK)
				{
					harSw = true; swKort = kortOK; swE = c; swT = t; swStatus = "aaben"; swStop = Pt(Ind.SwStop);
					Log.Add(string.Format("{0:yyyy-MM-dd HH:mm:ss} NY swing {1} {2}", ny, kortOK ? "SHORT" : "LONG", c));
					if (HandelTilladt() && !(Ind.Rv5Min > 0 && Rv5.HasValue && Rv5.Value < Ind.Rv5Min))
					{
						MotorOrdre od = new MotorOrdre();
						od.Navn = "SWING"; od.Kort = kortOK; od.StopPt = swStop; od.TpPt = Pt(Ind.SwTp);
						od.UdTid = Ind.SwUdNy > 0 ? t - nySek + Ind.SwUdNy : t + 15 + Ind.SwSek;
						od.T = t; od.BePt = Ind.SwBe; od.BeLaas = Ind.SwBeLaas;
						ud.Add(od);
					}
				}
			}

			// market open: beslutning paa baren der starter 09:29:45
			if (!moGivet && nySek == tBeslut)
			{
				moGivet = true;
				if (!harSw)
					MoRetning = "INGEN";
				else if (!HandelTilladt())
					MoRetning = "SPRING OVER";
				else
				{
					bool kort = swStatus == "tabt" ? !swKort : swKort;
					MoRetning = kort ? "SHORT" : "LONG";
					MotorOrdre od = new MotorOrdre();
					od.Navn = "MO"; od.Kort = kort; od.StopPt = Pt(Ind.MoStop); od.TpPt = Pt(Ind.MoTp);
					od.UdTid = t + 15 + 60; od.T = t;
					ud.Add(od);
				}
				Log.Add(string.Format("{0:yyyy-MM-dd HH:mm:ss} NY market open {1}", ny, MoRetning));
			}
			return ud;
		}

		// formarkedets niveauer taeller kun fra 09:00 (pA); Londons kun hvis ikke brugt op foer 08:45
		private void Sweep(double h, double l, bool harE, double eh, double el, bool pA)
		{
			if (!taget[NLH] && !brugt[NLH] && niv[NLH].HasValue && h >= niv[NLH].Value) taget[NLH] = true;
			if (pA && !taget[NPH] && niv[NPH].HasValue && h >= niv[NPH].Value) taget[NPH] = true;
			if (harE && !taget[ELH] && !brugt[ELH] && niv[ELH].HasValue && eh >= niv[ELH].Value) taget[ELH] = true;
			if (harE && pA && !taget[EPH] && niv[EPH].HasValue && eh >= niv[EPH].Value) taget[EPH] = true;
			if (!taget[NLL] && !brugt[NLL] && niv[NLL].HasValue && l <= niv[NLL].Value) taget[NLL] = true;
			if (pA && !taget[NPL] && niv[NPL].HasValue && l <= niv[NPL].Value) taget[NPL] = true;
			if (harE && !taget[ELL] && !brugt[ELL] && niv[ELL].HasValue && el <= niv[ELL].Value) taget[ELL] = true;
			if (harE && pA && !taget[EPL] && niv[EPL].HasValue && el <= niv[EPL].Value) taget[EPL] = true;
		}

		private static long FloorDiv(long a, long b) { long q = a / b; if ((a % b != 0) && ((a < 0) != (b < 0))) q--; return q; }
		private static long Mod(long a, long b) { long m = a % b; return m < 0 ? m + b : m; }
	}
}
