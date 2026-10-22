"""Ikon loading: mesin cuci yang sedang mencuci (SVG + animasi SMIL, tanpa file gambar).

Dipasang lewat CSS di ikon status Streamlit (pojok kanan atas, muncul saat app sedang
memproses) dan ditampilkan besar di tengah layar. File ini SAMA di repo osl-invoice-web
dan osl-absensi.
"""
from urllib.parse import quote

WASHER_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 132'>
<defs><clipPath id='kaca'><circle cx='60' cy='78' r='24'/></clipPath></defs>
<g>
<animateTransform attributeName='transform' type='translate' dur='0.28s' repeatCount='indefinite'
 values='0 0; 1.2 -0.6; 0 0; -1.2 -0.6; 0 0'/>
<rect x='22' y='121' width='14' height='7' rx='2' fill='#2A0F1D'/>
<rect x='84' y='121' width='14' height='7' rx='2' fill='#2A0F1D'/>
<rect x='10' y='6' width='100' height='117' rx='14' fill='#FFFFFF' stroke='#9F2063' stroke-width='4'/>
<line x1='12' y1='32' x2='108' y2='32' stroke='#9F2063' stroke-width='3'/>
<circle cx='26' cy='19' r='6' fill='#9F2063'/>
<circle cx='42' cy='19' r='3.5' fill='#C23B80'/>
<rect x='66' y='13' width='34' height='12' rx='3' fill='#FBF0F5' stroke='#9F2063' stroke-width='2'/>
<circle cx='72' cy='19' r='2' fill='#16A34A'>
 <animate attributeName='opacity' values='1;0.2;1' dur='0.9s' repeatCount='indefinite'/></circle>
<circle cx='60' cy='78' r='33' fill='#FBF0F5' stroke='#9F2063' stroke-width='5'/>
<circle cx='60' cy='78' r='26' fill='#E0F2FE' stroke='#C23B80' stroke-width='2'/>
<g clip-path='url(#kaca)'>
 <path d='M14 84 Q24 78 34 84 T54 84 T74 84 T94 84 T114 84 V110 H14 Z' fill='#7DD3FC' opacity='0.85'>
  <animateTransform attributeName='transform' type='translate' values='0 0; -20 -2; 0 0'
   dur='1.1s' repeatCount='indefinite'/></path>
 <g>
  <animateTransform attributeName='transform' type='rotate' from='0 60 78' to='360 60 78'
   dur='1.1s' repeatCount='indefinite'/>
  <rect x='46' y='60' width='15' height='11' rx='3' fill='#9F2063'/>
  <rect x='62' y='84' width='13' height='9' rx='3' fill='#F59E0B'/>
  <circle cx='70' cy='64' r='5' fill='#C23B80'/>
  <path d='M44 84 h8 v10 h-4 v-6 h-4 z' fill='#2563EB'/>
 </g>
 <circle cx='50' cy='96' r='2.4' fill='#FFFFFF' opacity='0.9'>
  <animate attributeName='cy' values='98;62' dur='1.3s' repeatCount='indefinite'/>
  <animate attributeName='opacity' values='0.9;0' dur='1.3s' repeatCount='indefinite'/></circle>
 <circle cx='66' cy='98' r='1.8' fill='#FFFFFF' opacity='0.9'>
  <animate attributeName='cy' values='100;60' dur='1.7s' begin='0.4s' repeatCount='indefinite'/>
  <animate attributeName='opacity' values='0.9;0' dur='1.7s' begin='0.4s' repeatCount='indefinite'/></circle>
 <circle cx='74' cy='96' r='2.8' fill='#FFFFFF' opacity='0.9'>
  <animate attributeName='cy' values='98;64' dur='1.5s' begin='0.8s' repeatCount='indefinite'/>
  <animate attributeName='opacity' values='0.9;0' dur='1.5s' begin='0.8s' repeatCount='indefinite'/></circle>
</g>
<path d='M44 64 A22 22 0 0 1 58 56' stroke='#FFFFFF' stroke-width='3' fill='none' stroke-linecap='round' opacity='0.8'/>
</g>
</svg>"""

WASHER_URI = "data:image/svg+xml," + quote(" ".join(WASHER_SVG.split()))

CSS = f"""
<style>
[data-testid="stStatusWidgetRunningManIcon"] {{ display: none !important; }}
[data-testid="stStatusWidgetRunningIcon"] svg, [data-testid="stStatusWidgetRunningIcon"] img
  {{ opacity: 0 !important; }}
/* wadah status Streamlit kadang opacity 0 saat muncul -> paksa terlihat */
[data-testid="stStatusWidget"]:has([data-testid="stStatusWidgetRunningIcon"]) {{ opacity: 1 !important; }}
[data-testid="stStatusWidgetRunningIcon"]::before {{
  content: ""; position: fixed; top: 50%; left: 50%; z-index: 1000010;
  transform: translate(-50%, -50%); width: 6.5rem; height: 7.2rem;
  background: url("{WASHER_URI}") center / contain no-repeat;
  filter: drop-shadow(0 6px 16px rgba(159,32,99,.28)); pointer-events: none;
  animation: osl-washer-in .25s ease .5s both;   /* proses singkat (<0,5 dtk) tak berkedip */
}}
@keyframes osl-washer-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
</style>
"""
