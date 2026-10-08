# BAB – gratis Mac-tester

Det här paketet förbereder verkliga Mac-tester av BAB 1.6.1. Testerna har ännu
inte körts på macOS. Programmet kan fortfarande ha startfel.

## Endast gratis körning

Testerna kan startas manuellt i GitHub Actions i ett **offentligt** kodprojekt.
De körs på standardmiljöerna `macos-15` (Apple-chip) och `macos-15-intel`.
Jobben spärras om projektet är privat. Ingen schemaläggning, betald testdator,
cache, uppladdning av testartefakter, Mac-hyra eller Apple-prenumeration ingår.
Resultat och felloggar visas direkt i GitHub Actions.

GitHub beskriver standardmiljöerna som gratis för offentliga projekt:
https://docs.github.com/en/actions/reference/runners/github-hosted-runners

## Vad som behöver publiceras för att köra

1. Skapa ett tomt offentligt GitHub-projekt, exempelvis `Better-Audio-Books`.
2. Lägg `.github/`, `tests/` och denna README i projektets rot.
3. Skapa en offentlig testutgåva med taggen `bab-1.6.1-test` och bifoga exakt
   `BAB-Mac-Installation-1.6.1-Testversion.pkg` från projektets outputs-mapp.
   Installationsfilen har SHA256:
   `e2d0300503ca88ef034d01f78b20185dee483a6e82137577208a9fada2db0412`.
4. Under Actions väljer du **BAB Mac tests** och **Run workflow**.

Installationsfilen innehåller BAB:s programkod, röstmodeller och deras licenser.
Dina sparade böcker, läspositioner, privata bilagor, kontouppgifter och lokala
ljudcache ligger utanför paketet och ska inte publiceras. Ladda aldrig upp hela
arbetsmappen. Bara de utvalda projektfilerna och den angivna installationsfilen
behövs för testen.

## Vad testen faktiskt gör

- Verifierar den befintliga installationsfilens SHA256 före installation.
- Installerar samma paket som vännen fick i GitHubs tillfälliga Mac-maskin.
- Laddar de paketerade Mac-biblioteken med BAB:s egen Python.
- Skapar ny svensk uppläsning med båda offlinerösterna medan Python-nätanrop
  blockeras; kontrollerar ordtider och resursgränser.
- Startar den levererade Mac-värden med riktig Cocoa/WKWebView och kontrollerar
  att BAB:s gränssnitt blir redo utan att ladda offlineröster i bakgrunden.
- Försöker öppna den oförändrade appen via LaunchServices, som Finder använder,
  och kontrollerar att ett fönster verkligen visas. Felloggar skrivs i jobbloggen.

Om testmiljön saknar fungerande skrivbord visas fel; det räknas inte som ett
godkänt fönstertest. Testerna ändrar inte Gatekeeper, filkarantän eller signering.
De använder bara egen svensk testtext och tillfälliga bokmappar.

Dessa kontroller ersätter inte provlyssning, fullständig visuell kontroll,
Gatekeeper-test av en internetnedladdning eller prestandamätning på en M3-Mac.
Inga Mac-tester blir godkända förrän ett faktiskt GitHub-jobb har slutförts.
