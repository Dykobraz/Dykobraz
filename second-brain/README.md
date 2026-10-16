# Second Brain

Osobní znalostní knihovna pro Mac: poznámky, dokumenty, projekty a vybrané zprávy či události z Googlu. Data jsou uložená místně; při odeslání otázky se vybrané pasáže posílají výkonné cloudové AI. Aplikace nepoužívá malý místní jazykový model, Ollama ani Swift.

**[Začni návodem pro Mac](SPUSTENI-MAC.md).**

## Co tato verze umí

- Trvale ukládat vlastní poznámky, textové soubory, Markdown a textová PDF do projektů.
- Vyhledávat pasáže a před odesláním ukázat přesný obsah určený pro AI.
- Odpovídat česky přes OpenAI Responses API; výchozí model `gpt-4.1`, volitelný v nastavení.
- Oddělovat doložená tvrzení, doporučení a nejistoty. Otevírat původní podklady u citací.
- Importovat jednotlivé e-maily bez příloh a jednotlivé události primárního Google kalendáře na příštích sedm dní.
- Exportovat zdroje a odpovědi do Markdownu.

Odesílání e-mailů a změny kalendáře nejsou implementované. Žádná zpráva se nepřidává automaticky do knihovny ani do AI. Propojení s Googlem používá pouze čtecí oprávnění.

Živý poslech není součástí této přestavby. Původní experiment zůstává v `seminar-assistant`; jeho nespolehlivé rozpoznávání řeči se nepoužívá jako vstup nové knihovny. Semináře lze zatím přidávat jako vlastní poznámky nebo povolené textové podklady. Cloudové zpracování zvuku by vyžadovalo zvláštní implementaci a souhlas s přenosem zvuku.

## Práce s podklady a limity kvality

Vyber zdroje v knihovně, otevři **Zeptat se kolegy**, napiš otázku a dej **Najít podklady**. Vyber pasáže a teprve potom **Odeslat dotaz do AI**. Samotné hledání neposílá data do OpenAI.

Vyhledávání je místní SQLite FTS5 podle slov, podporuje diakritiku, ale není sémantické: české skloňování a synonyma nemusí najít. Vybrané zdroje se nejprve prohledají podle otázky; pokud se nic nenajde, nabídnou se jejich počáteční pasáže. Bez ručního výběru se hledá ve vybraném projektu nebo celé knihovně. Kontroluj proto nabídnuté podklady; chybějící výsledek nedokazuje nepřítomnost informace.

Pro jeden dotaz lze vybrat nejvýše šest zdrojů a dvanáct pasáží po přibližně 1400 znacích. Celé dlouhé dokumenty se do jednoho dotazu nevejdou; pracuj s konkrétními otázkami. Nový dotaz či změna projektu vyžadují znovu připravit podklady.

Kontrola citací ověřuje existenci odkazu, příslušnost k vybraným podkladům a citaci u faktických tvrzení. **Nedokazuje, že model pasáž správně pochopil.** Odpovědi mohou chybovat. Citované zdroje jsou originály; uživatelské poznámky samy mohou obsahovat chyby. Pokyny uvnitř importovaných zdrojů se považují za nedůvěryhodný obsah.

PDF se zpracovává místně, nejvýše 8 MB a 300 stran. Skeny bez textové vrstvy, OCR, zašifrované PDF a e-mailové přílohy nejsou podporované. Textový zdroj má nejvýše 500 000 znaků.

## Data a přístupové údaje

Na Macu se data nacházejí v `~/Library/Application Support/Second Brain/`:

- `brain.sqlite3`: původní texty, projekty a vyhledávací index.
- `google-client.json`: konfigurace vlastního Google OAuth desktop klienta.
- `google-token.json`: obnovovací přístup pro Google účet, soubor s právy `0600` v adresáři `0700`. Je to místní soubor, nikoli šifrovaná Klíčenka; chraň svůj uživatelský účet a zálohy.

API klíč OpenAI zadaný v rozhraní je pouze v paměti serveru do ukončení nebo zapomenutí klíče. Na příští spuštění ho zadáš znovu; alternativně ho může dodat proměnná `OPENAI_API_KEY` ze zabezpečeného správce přístupových údajů. Nezapisuj klíče do Gitu ani příkazů ukládaných do historie shellu.

Odpovědi jsou v aktuální kartě prohlížeče, neukládají se automaticky do databáze. Exportuj je, chceš-li je uchovat. Místní zdroje a Google připojení restart přežijí. Smazání zdroje neodstraní dřívější exporty, zálohy, zobrazenou odpověď ani data již odeslaná poskytovateli AI.

Při kliknutí **Odeslat dotaz do AI** jde otázka a vybrané pasáže na `api.openai.com`. Nastavení `store: false` vypíná ukládání odpovědi pro pozdější načtení API; není to záruka nulové retence u poskytovatele. Platí podmínky tvého OpenAI API účtu. API má samostatné účtování, předplatné ChatGPT nestačí.

Odpojení Google smaže místní token. Dříve importované zdroje zůstávají v knihovně; trvalé odvolání oprávnění proveď v bezpečnostním nastavení svého Google účtu.

## Vývoj a ověření

Python 3.12; knihovna využívá SQLite FTS5. Instalace:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
node --check web/app.js
bash -n setup-mac.sh start-mac.sh
```

Spuštění na Linuxu pro vývoj: `BRAIN_DATA_DIR=/tmp/second-brain-dev .venv/bin/python server.py`. V produkčním osobním použití data ukládej do trvalé složky, nikoli `/tmp`. Server naslouchá pouze na loopback adrese, port 8766. Nezveřejňuj ho na internetu.

Testy zahrnují místní uložení a restart knihovny, projekty, výběr pasáží, kontrolu citací, klíče, Google MIME import, HTTP workflow a odmítnutí nečitelných PDF. Providerové odpovědi a Google přístup jsou při testech nahrazené. Skutečné OpenAI volání a Google OAuth nelze považovat za ověřené před jejich zkouškou s vlastním účtem na Macu. Test prohlížeče rovněž používal náhradní AI odpověď; ukázkové screenshoty nejsou doklad skutečného modelového výkonu.
