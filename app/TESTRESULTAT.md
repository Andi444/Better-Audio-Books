# BAB 1.6.1 — Mac-start med lägre belastning

- Mac-värden startar inte längre någon röstladdning i bakgrunden. Gränssnittet begär inte ljud när en bok öppnas eller en pausad röst byts på Mac.
- Mac använder en röstmodell i minnet åt gången och en beräkningstråd. ONNX väntar utan aktiv CPU-spinning. Numeriska bibliotek begränsas till en tråd i Mac-processen.
- Nästa avsnitt förbereds endast för den valda rösten under uppläsning på Mac. Samma klangvarianter återanvänder modellen. Första uppspelningen eller byte av grundröst kan ta en kort stund.
- Ordmarkering kontrolleras var 60 ms under läsning; vilande gränssnitt uppdaterar kontrollen var 500 ms i stället för varje bildruta.
- Båda verkliga offlinerösterna med Mac-resursinställningarna har skapat WAV-ljud och ordtider på Windows med nätåtkomst blockerad. En resident modell, trådgräns och avstängd spinning kontrollerade.
- Fyra plattformstester, elva servertester och textlogik godkända. Mac-start med simulerad fönstermotor verifierar att inga röster förladdas. UI-logiktest verifierar att Mac inte begär bakgrundsljud och att Windows behåller förberedelsen.
- Ingen Mac finns i byggmiljön. Faktisk Mac-CPU/RAM, installation, Cocoa-fönster och uppläsning återstår att provköra på vännens dator. Ingen förbättring i procent utlovas.

# BAB 1.6 — testresultat

## Version 1.6: Windows och Mac

- Samma backend, bibliotek, textvy och röstprofiler används för båda systemen. Windows behåller sitt tidigare native-fönster; Mac använder en separat Cocoa/WKWebView-värd.
- Fyra plattformskontroller godkända: Windows datamapp bevaras, Mac använder Application Support, explicit datamapp kan anges, samt Mac-värdens lokala API/sparande/stängning testas med en simulerad fönstermotor. Simuleringen är inte ett test av Cocoa.
- 11 serverkontroller godkända för bibliotek, position, röstläge, autentisering, cache och ljudformat. Tidigare UI-kontroller finns dokumenterade nedan.
- Mac-paketet innehåller både ARM64 och x86_64. Python-arkiv och alla hjul verifieras mot leverantörernas SHA256. Unix-körrättigheter och relativa symboliska länkar bevaras i ZIP-filen.
- Mac-kravet är macOS 13 eller senare. Piper 1.8.0 och ONNX Runtime 1.22.1/NumPy 1.26.4 väljs för att stödja båda arkitekturerna. Röstmodellerna är samma som på Windows.
- Denna körning sker på Windows. Mac-start, Finder-installation, Cocoa-fönster, ljud och Gatekeeper har inte provkörts på Mac. Mac-utgåvan är uttryckligen en testversion, inte en verifierad slutversion.
- Ny automatisk Edge-start för gränssnittstest kunde inte slutföras i denna körmiljö (testwebbläsaren stängdes vid start). Inga Windows-säkerhetsinställningar ändrades. Gemensam server och plattformslogik är testade separat.
- Windows-installationsfilen är osignerad. Mac-appen saknar Apple Developer ID-signering/notarisering. Plattformarnas skydd kan blockera dem.

## Version 1.5: långa texter

- Testat med användarens fullständiga text: 11 219 ord. Texten återfanns oförändrad i sparad bok och läsyta, bortsett från textfältets normala CRLF→LF-normalisering. Testtexten distribueras inte med programmet.
- Edge-test med CPU begränsad till 4× långsammare: öppning före cirka 4 371 ms, efter cirka 504 ms. Byte av textstorlek före cirka 3 840 ms, efter cirka 71 ms. Mätningar gäller testmiljön och är inga garantier för andra datorer.
- Stor inklistring via paste-händelsen, ångra/återställ, full textbevaring och lokal uppläsning från ett valt ord nära slutet verifierade. Ingen extern överföring av testtexten.
- Läsytan är uppdelad i 90 avsnitt för denna text. Chromium kan hoppa över layout av avsnitt utanför synfältet; alla ord ligger kvar i dokumentet.
- Befintliga kontroller av röstlägen, sparat val, volym, fasta kontroller och smala fönster godkända. 11 serverkontroller och tester av text-/tidslogik godkända.
- Samma osignerade Windows-startfil som 1.4. Denna prestandauppdatering åtgärdar inte Smart appkontroll.

## Version 1.4

- 80 röstprofiler: 40 offline och 40 online. Sofie/Mattias motor-ID, tonläge och tempo jämfördes med originalversionen: alla 40 oförändrade.
- Både Sofie och Mattias testades mot den riktiga onlinetjänsten. MP3, ordmarkering, klicka/läs härifrån, provlyssning och byte till offline under uppspelning fungerade.
- Alla 40 offlineprofiler skapade ljud med nätanrop blockerade. Fullständiga meningars fonemer används nu i modellen; isolerade ord används endast som referens för koppling till texten. Testat med tal, decimaler, förkortningar och dialog. Samtliga testord hade monotona tidsangivelser inom ljudets längd. Kopplingen kan vara ungefärlig vid kontextberoende uttal.
- Klangvarianternas omsampling har minskats för att minska förvrängning. Modellerna är oförändrade. Naturlighet är subjektiv; ingen garanti att lokala röster låter som onlinerösterna.
- Gränssnittet verifierat med blockerad extern trafik: inget onlineanrop vid enbart val av läge/röst eller öppning av bok. Läge och röst sparas med boken och återställs efter omladdning.
- 11 serverkontroller godkända, inklusive separata ljudformat/cache, felmeddelande vid nätfel, bevarat röstval/läsposition, åtkomstskydd och ljudintervall.
- Volym, fast verktygsrad, 1440/820/390 pixlars layout, Unicode/textklick och inga JavaScript-fel kontrollerade. Samma Windows-startfil som tidigare; tidigare begränsning av native-körning i testmiljön gäller fortfarande.

## Historik från version 1.3

## Offline, volym och fast läsvy

- Alla 40 lokala klangvarianter läste en ny svensk testtext med Python-nätanslutningar blockerade. Inga nätanrop behövdes. Samtliga ord fick tidsangivelser från röstmodellens fonemlängder.
- Kall inläsning av båda modellerna: cirka 3 sekunder i testmiljön. Nytt 15-ordsavsnitt: cirka 0,4–0,6 sekunder per grundröst. Ytterligare klangvarianter av samma avsnitt: cirka 4–8 millisekunder på serversidan. Ett helt sparat avsnitt lästes ur cachen på cirka 0,3 millisekunder. Tiderna är mätningar, inte garantier för andra datorer.
- Gränssnittet testades med externa nätanrop blockerade både i webbläsaren och för Python-servern. Klicka/läs härifrån, paus, röstbyte under läsning och ordmarkering fungerade. Ett uppmätt röstbyte inklusive gränssnittet tog cirka 0,8 sekunder.
- Volym från 0 till 100 procent verifierad för uppläsning och provlyssning; sparad volym återställdes efter omladdning.
- Boktexten rullades 500 pixlar utan att toppens position eller fönstrets rullning ändrades. Typsnitt och storleksknappar ligger kvar. Kontrollerna verifierades vid 1440, 820 och 390 pixlars fönsterbredd. Inga JavaScript-fel noterades.
- Rösterna är Piper Alma och NST. Nätrösterna från äldre versioner används inte i denna version. Ingen internetanslutning behövs för nya boktexter.

## Historik från version 1.2

## Fönsterikoner och skrivbordsgenväg i 1.2

- Ett eget Windows-fönster med WebView2 ersätter Edge-appfönstret. DPI-medvetenhet och separata stora/små fönsterikoner är implementerade. Rätt ikonstorlek laddas även efter byte av skärmskalning.
- Ikonen har elva självständiga bildstorlekar: 16, 20, 24, 28, 32, 40, 48, 64, 96, 128 och 256 pixlar. Små storlekar har förenklade detaljer. Samma ikonpaket är inbäddat i BAB.exe.
- Genvägen skapas direkt via Windows Shell från Python, utan PowerShell eller start av hjälpprogram. Den faktiska HTTP-funktionen är testad med riktig genvägsskapning i en testmapp. Upprepat anrop gav en enda genväg. Målfil, ikon och AppUserModelID BetterAudioBooks.BAB verifierades genom Windows Shell.
- Windows programkontroll blockerade körningen av den nybyggda BAB.exe i testmiljön. Native-fönstrets start, WebView2-visning, stängning och hur ikonerna faktiskt ser ut i Windows är därför inte visuellt verifierade. Kompilering och filkontroller är godkända. Ingen säkerhetsinställning ändrades för att försöka kringgå blockeringen.

## Tidigare kontroller

Uppdateringen har verifierats med sex typsnitt i läsvyn, sparat typsnittsval efter omladdning och oförändrad text/läsposition vid byte. Layouten är kontrollerad vid 1440, 1024 och 390 pixlars bredd. Vektorloggan är exporterad direkt till 4096 × 4096 pixlar; Windows-ikonen innehåller sju storlekar mellan 16 och 256 pixlar. Startfilen är omkompilerad med den uppdaterade ikonen.

Genvägsskriptet har körts i en separat testmapp och den skapade Windows-genvägens mål och ikon har verifierats. Inget har lagts på användarens skrivbord under utvecklingen. Knappens anrop och återkoppling är verifierade i gränssnittet med ett simulerat serversvar.

Testad 23 september 2026 på Windows med den medföljande Python-miljön och Microsoft Edge.

- Alla 40 klangvarianter skapade verkligt svenskt ljud, med tidsangivelser för samtliga 11 ord i testfrasen.
- 8 automatiska servertester godkända: röstkatalog, svensk Unicode och ordkoppling, avvisning av felaktig ordkoppling, lokal åtkomstkontroll, bokhantering och läsposition, indatagränser, ljudcache och sökning i ljudfiler, avgränsad filåtkomst.
- Läsmotorns tester godkända: Unicode och emoji, exakta ordpositioner, full texttäckning mellan avsnitt samt markering från ljudets aktuella tid.
- Gränssnittstester med verkligt ljud godkända: klicka på två olika ord och starta därifrån, ordmarkering, paus, återuppta, ändra hastighet, spara och återläsa position efter omladdning.
- Automatisk övergång till nästa textavsnitt, färdigläsning och röstprov utan överlappande uppläsning godkända.
- Text med HTML-liknande innehåll visas som text. Fel på rösttjänsten lämnar boken kvar och tillåter nytt försök.
- Bokborttagning, ljust/mörkt tema och smal fönsterbredd kontrollerade. Inga JavaScript-fel under testerna.
- Windows-startfilen BAB.exe är kompilerad med BAB:s ikon. Automatisk godkännandegranskning blockerade testkörning av just den nya startfilen; dubbelklicksstart är därför inte verifierad. Appen testades genom att starta server.py med medföljande runtime/python.exe.

Rösterna är 20 tonhöjds-/tempovarianter av Mattias och 20 av Sofie, inte 40 separata personer. Tester av framtida tillgänglighet hos den externa rösttjänsten är inte möjliga.
