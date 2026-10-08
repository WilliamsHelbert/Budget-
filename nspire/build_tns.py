"""Bygger en (eksperimentel) TI-Nspire .tns-fil ud fra en markdown-guide.

Brug: python3 build_tns.py uafhaengighedstest.md uafhaengighedstest.tns
.tns er et ikke-officielt, proprietært format; filen er IKKE testet på en
rigtig Nspire. Importér ellers teksten manuelt i en Notes-side.
"""
import sys, zipfile
from xml.sax.saxutils import escape

src, dst = sys.argv[1], sys.argv[2]
lines = [l.rstrip() for l in open(src, encoding="utf-8") if l.strip()]
text = "\n".join(l.lstrip("#| ").replace("**", "").replace("`", "") for l in lines)

problem = f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<prob xmlns="urn:TI.Problem" ver="1.0" pbname=""><sym></sym>
<card clay="0" h1="10000" h2="10000" w1="10000" w2="10000"><isDummyCard>0</isDummyCard><flag>0</flag>
<wdgt xmlns:np="urn:TI.Notepad" type="TI.Notepad" ver="1.0"><np:mFlags>1024</np:mFlags><np:value>2</np:value>
<np:fmtxt>{escape(text)}</np:fmtxt></wdgt></card></prob>'''
doc = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?><doc ver="1.0"><settings/></doc>'

with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("Document.xml", doc)
    z.writestr("Problem1.xml", problem)
print("skrev", dst)
