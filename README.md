# Better Audio Books (BAB)

Gratis svenska ljudböcker från egen text. Det här projektet innehåller BAB:s
programkod och kostnadsfria Mac-tester. Dina böcker och privata filer ingår inte.

## Mac-tester

GitHub Actions bygger en testapp på standardmiljöerna macos-15 (Apple-chip)
och macos-15-intel. Jobben är spärrade i privata projekt. Ingen betald
Mac-tjänst, cache eller lagring av testartefakter används.

Bygget hämtar exakt hash-låsta Python-/röstbibliotek från officiella utgivare.
Röstmodellerna hämtas från Piper och verifieras både före och efter BAB:s
ändring för ordmarkering. Programkoden motsvarar BAB 1.6.2. Testpaketet
byggs med Apples pkgbuild på den riktiga Mac-testmaskinen. Varje jobb
innehåller bara sin egen arkitektur, till skillnad från den tidigare dubbla
Windows-byggda installationsfilen. Därför är det inte samma installationsfil.

Testerna kontrollerar bibliotek, verklig svensk offlinesyntes, ordtider,
Cocoa/WKWebView och att appen öppnar ett synligt fönster genom LaunchServices.
Resultat och felloggar visas under Actions. Testerna räknas inte som godkända
förrän ett riktigt jobb har slutförts.

Detta ersätter inte provlyssning, Gatekeeper-test av internetnedladdning,
fullständig visuell kontroll eller prestandamätning på en M3-Mac.
Inga säkerhetsinställningar ändras. Appen är osignerad.

Standardtestmiljöerna är gratis i offentliga projekt enligt GitHub:
https://docs.github.com/en/actions/reference/runners/github-hosted-runners

## Licenser

BAB:s Mac-värd och plattformsstöd distribueras under GPL-3.0-or-later.
Se app/COPYING-GPL-3.0.txt och app/RÖSTER-OCH-LICENSER.txt.
Beroenden har egna licenser som följer med i de verifierade arkiven.

Installationsfiler, egna ljudcachefiler och privata böcker ska inte läggas
in i Git-historiken. Det här testbygget publicerar inga binärer automatiskt.

## Rättning i 1.6.2

Startfilen väljer Apple-chipets egna Python även när LaunchServices startar
skalet genom Rosetta. Mac-fönstret använder direkt JavaScript-anrop vid
stängning, så att inställningar kan sparas utan CSP-blockerad eval.

## Verifierad Mac-körning 2026-10-08

BAB 1.6.2 klarade båda jobben: Apple-chip arm64 och Intel x86_64.
Installation med Apples verktyg, native bibliotek, båda offlinerösterna,
ordtider, färdigt Cocoa-fönster, sparad volym vid det riktiga stängningsanropet
och synligt appfönster via LaunchServices blev godkända.

Resultat: https://github.com/Andi444/Better-Audio-Books/actions/runs/37785058573

Testerna bygger egna paket på respektive Mac. Den dubbla installationsfil
som byggs på Windows är fortfarande ett separat paket som behöver provas
på en användares Mac. Signering, Gatekeeper och hörbar ljudutmatning ingår
inte i dessa automatiska tester.