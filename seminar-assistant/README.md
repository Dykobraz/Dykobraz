# Seminární kolega pro macOS

**Začni zde: [Návod ke spuštění na Macu](SPUSTENI-MAC.md).** Obsahuje stažení z GitHubu, první instalaci i každé další spuštění.

Místní prototyp asistenta: systémový zvuk → pracovní rozpoznání v paměti → české poznámky a návrhy kroků. Používá ScreenCaptureKit, faster-whisper a Ollama. Žádné placené API. Zvuk ani doslovný přepis se neukládají do souborů. Poznámky jsou v paměti do ukončení aplikace; export je ruční. Zpracování probíhá po asi 15sekundových úsecích; skutečné zpoždění závisí na výkonu Macu a modelu.

Příjem zvuku, rozpoznávání řeči a tvorba poznámek probíhají odděleně. Pomalá generace poznámek neblokuje rozpoznávání další řeči; čekající pracovní texty se zpracují společně, nejvýše čtyři úseky na aktualizaci. Stavový řádek ukazuje přibližné množství čekajícího zvuku a počet textových úseků. Paměťové fronty jsou omezené: při více než přibližně dvou minutách čekajícího zvuku nebo 32 čekajících textových úsecích aplikace přizná přetížení a zastaví se. Obsah se potichu nevynechává. Toto opatření nezaručuje dostatečnou rychlost na každém Macu.

**Stav:** Python backend a HTTP rozhraní lze ověřit na Linuxu. Nativní zachytávač je určen pro macOS a musí se na Macu sestavit a otestovat. Celý řetězec živého zvuku zatím není ověřený. Před seminářem proveď níže uvedenou zkoušku.

## 1. Instalace na Macu

Rozbal projekt do vlastní složky, například `~/Applications/seminar-assistant`, a otevři v ní Terminál. Potřebuješ Homebrew z https://brew.sh a Apple Command Line Tools (`xcode-select --install`). Nikdy nevypínej ověřování podpisů nebo TLS.

```bash
cd ~/Applications/seminar-assistant
bash setup-mac.sh
```

Skript nainstaluje Python 3.12 a Ollama přes Homebrew, vytvoří `.venv`, nainstaluje Python závislosti a sestaví zachytávač. Nemění profilový repozitář Dykobraz. Pokud selže sestavení, nepokračuj předstíráním, že poslech funguje — pošli chybové hlášení bez obsahu semináře.

## 2. První stažení modelů

Ve složce projektu spusť:

```bash
bash prepare-models.sh
```

Skript dočasně spustí místní Ollama, pokud už neběží, stáhne modely a svůj server poté ukončí. Již běžící server neukončuje.

Stažení několika GB vyžaduje internet (Homebrew, PyPI, Hugging Face a registr Ollama). Tyto požadavky neobsahují zvuk semináře. Aplikace sama používá pouze místní Ollama na `127.0.0.1:11434`; model řeči načítá výhradně z místních souborů. Nepoužívej cloudový model ani cloudové přesměrování Ollama. Pro silnější Mac lze ručně zvolit větší místní model pomocí proměnné `NOTES_MODEL`, po jeho stažení; výchozí 3B model je kompromis mezi pamětí a kvalitou. Jazyk řeči se rozpoznává automaticky, poznámky jsou české.

## 3. Spuštění

```bash
bash start-mac.sh
```

Otevři v Chromu místní adresu vypsanou v Terminálu (`127.0.0.1`, port 8765). Vyplň své cíle. Nejprve pomocí vlastní krátké poznámky ověř místní Ollama. Potom spusť poslech. macOS může vyžadovat oprávnění v **Nastavení systému → Soukromí a zabezpečení → Záznam obrazovky a systémového zvuku**; název položky se může lišit podle jazyka systému. Povol aplikaci či Terminálu, který systém uvede, potřebné oprávnění, případně aplikaci znovu spusť.

Spouštěcí skript podle potřeby zapne místní Ollama a po ukončení aplikace vypne pouze server, který sám spustil. Nevytváří trvalou službu po přihlášení. První generování poznámek může trvat déle kvůli načítání modelu.

Zachytávač používá filtr displeje pro získání systémového zvuku; obrazové snímky se aplikaci nepředávají a obraz ani zvuk se nezapisují do souborů. Zachycuje se systémový výstup, včetně jiných přehrávajících aplikací a oznámení. Zavři ostatní přehrávání a zapni Nerušit. **Mikrofon není zahrnutý**, takže vlastní promluvy doplň ručně. Chráněný zvuk nebo konkrétní konfigurace zvukového výstupu nemusí být zachytitelné.

Sluchátka můžeš používat, ale ověř skutečnou konfiguraci při zkoušce. Ukončení karty v Chromu nezastaví server ani poslech. Použij **Zastavit**, nebo v Terminálu **Ctrl+C**. Zastavení zahodí rozpracovaný úsek; dokončení již spuštěného místního výpočtu může chvíli trvat, ale jeho výsledek se po zastavení nepřidá. **Vymazat relaci** odstraní poznámky z aplikace, nikoli dříve exportované soubory. Jde o běžné uvolnění paměti, nikoli o záruku forenzního vymazání RAM, swapu nebo systémových výpisů.

## 4. Povinná zkouška před seminářem

1. Spusť vlastní testovací řeč nebo nechráněné video v Chromu a použij stejná sluchátka jako na semináři.
2. Spusť poslech a ověř, že indikátor zvuku reaguje. Vyčkej na první poznámky; model na CPU může potřebovat výrazně déle než 15 sekund.
3. Ověř češtinu, smysl poznámek a rozlišení sdělení od návrhů. Pokud Mac nestíhá, automatický poslech nepovažuj za připravený; použij ruční poznámky.
4. Zastav poslech. Ověř, že se další obsah nepřidává. Vyzkoušej export a vymazání.
5. Znovu aplikaci spusť a ověř prázdnou relaci. Poznámky mezi týdny přenášej pouze záměrně, například vložením vlastního shrnutí z exportu; historie se automaticky neukládá.

Asistent může chybovat, vynechat důležitý bod nebo nesprávně rozpoznat jména. Rozpoznávání řeči interně vytváří krátkodobý pracovní text — bez tohoto kroku tento návrh nefunguje. Souhlas se zpracováním semináře zajišťuje uživatel; aplikace sama žádná oprávnění od pořadatele neověřuje. Návrhy úkolů neprovádí a neposílá žádné zprávy.

## Vývojové kontroly

```bash
python3 -m unittest discover -s tests -v
node --check web/app.js
bash -n setup-mac.sh prepare-models.sh start-mac.sh
```

Testy s náhradou modelu ověřují řízení relace, odmítnutí neoprávněných HTTP požadavků a zahazování opožděných výsledků. Nenahrazují test skutečných modelů, kompilaci Swiftu ani funkční zkoušku na Macu.
