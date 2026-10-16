# Spuštění Second Brain na Macu

Tato verze používá cloudovou AI, místní knihovnu a nové rozhraní. Nepotřebuje kompilovat Swift ani stahovat místní AI modely.

## 1. Stáhni novou větev

Nejdříve exportuj případné poznámky starého kolegy a ukonči ho pomocí **Ctrl+C** v Terminálu, kde běží. Potom v Terminálu spusť postupně:

```bash
cd "$HOME/Applications/seminarni-kolega-repo"
git remote set-branches --add origin second-brain
git fetch origin
git switch second-brain
git pull --ff-only
cd second-brain
bash setup-mac.sh
bash start-mac.sh
```

Příkaz `git switch` při prvním použití vytvoří místní větev z `origin/second-brain`. Pokud Git hlásí vlastní změny či konflikt, nic nemaž ani neresetuj a pošli hlášení. Nezaměňuj novou složku `second-brain` s původní `seminar-assistant`.

Příkaz `git remote set-branches --add` je důležitý pro původní kopii staženou pomocí `--single-branch`: přidá stahování nové větve a zachová původní nastavení ostatních větví.

Nemáš-li původní kopii repozitáře:

```bash
mkdir -p "$HOME/Applications"
git clone --branch second-brain --single-branch https://github.com/Dykobraz/Dykobraz.git "$HOME/Applications/seminarni-kolega-repo"
cd "$HOME/Applications/seminarni-kolega-repo/second-brain"
bash setup-mac.sh
bash start-mac.sh
```

Potřebuješ již nainstalované Homebrew. Instalace stáhne jen Python závislosti; žádné několikagigabajtové modely. Nech Terminál otevřený a v Chromu ručně vlož `http://127.0.0.1:8766`.

## 2. Připoj výkonnou AI

1. Přihlas se do svého OpenAI API účtu na **https://platform.openai.com/**, ověř účtování a nastav si upozornění na útratu či omezení svého projektu podle možností účtu. Předplatné ChatGPT nezahrnuje API kredit.
2. Vytvoř API klíč na **https://platform.openai.com/api-keys**.
3. V aplikaci otevři **Nastavení a připojení**, vlož klíč do pole **API klíč** a stiskni **Použít nastavení**. Klíč neposílej do tohoto chatu. Ukládá se pouze do paměti běžícího serveru.
4. Model je přednastavený na `gpt-4.1`; můžeš zadat jiný model dostupný ve svém API účtu s podporou Responses API a Structured Outputs. Pokud účet model nepovoluje, změň identifikátor podle dostupnosti ve svém účtu.

## 3. První funkční zkouška

1. Vytvoř projekt a přidej vlastní krátkou poznámku, například „Rozpočet projektu je 100 Kč. První experiment chci provést v pátek.“
2. V knihovně zdroj zaškrtni a klikni **Pracovat s výběrem**.
3. Napiš „Co už o plánu víme a co si mám ještě ujasnit?“ a klikni **Najít podklady**. Tento krok je místní.
4. Zkontroluj nabídnuté pasáže. Až pak stiskni **Odeslat dotaz do AI**; tím vzniká placený API požadavek.
5. Otevři citace a ověř je proti původní poznámce. Vyzkoušej otázku na něco, co v podkladu není — odpověď má přiznat chybějící informace.
6. Exportuj zdroj nebo odpověď, pokud je chceš použít jinde. Ukonči aplikaci, znovu ji spusť a ověř, že zdroj zůstal v knihovně. API klíč zadaný přes rozhraní je nutné zadat znovu.

## 4. Gmail a Google Kalendář

Tento krok je volitelný; knihovna a AI fungují i bez něj. Pro vlastní místní aplikaci potřebuješ vlastního Google OAuth klienta. Heslo Gmailu, API klíč OpenAI ani přihlášení v tomto chatu nenahrazují Google OAuth.

1. Otevři **https://console.cloud.google.com/** a vytvoř nebo vyber svůj projekt.
2. V **APIs & Services → Library** povol **Gmail API** a **Google Calendar API**.
3. V **Google Auth Platform / OAuth consent screen** nastav název aplikace a svůj kontaktní e-mail. Pro osobní test zvol příslušný testovací režim; u externí aplikace přidej svůj Gmail účet mezi **Test users**. Rozhraní Google může názvy položek měnit.
4. Povol čtecí rozsahy `https://www.googleapis.com/auth/gmail.readonly` a `https://www.googleapis.com/auth/calendar.readonly`. Aplikace si nevyžaduje oprávnění posílat poštu nebo měnit události.
5. V **Clients / Credentials → Create OAuth client ID** vyber typ **Desktop app** a stáhni klientský **JSON**.
6. V místní aplikaci otevři **Nastavení a připojení**, vyber stažený JSON v poli **Google OAuth JSON** a pak klikni **Připojit Google účet**.
7. Dokonči Google přihlášení v otevřeném prohlížeči. Použij účet přidaný mezi testovací uživatele. Pokud Google přístup odmítá, ověř nastavení svého projektu a pravidla organizace; neposílej do chatu stažený JSON ani tokeny.
8. V části **Gmail** vyhledej konkrétní zprávy, například `newer_than:7d` nebo `from:nekdo@example.com`. Importuj jen potřebnou zprávu do vybraného projektu.
9. V části **Kalendář** načti události na příštích sedm dní a případně je jednotlivě ulož jako podklady. Jde o primární kalendář účtu.

Pokud zůstane Google projekt v externím testovacím režimu, obnovovací tokeny mohou mít omezenou platnost, často sedm dní. Při vypršení účet znovu připoj. Návod Googlu pro desktop OAuth: **https://developers.google.com/identity/protocols/oauth2/native-app**.

Import uloží text místně. Cloudové AI se odešle až později při dotazu s příslušnými pasážemi. Přílohy se nestahují; události ani zprávy aplikace nemění. Google propojení je nutné ověřit skutečným přihlášením na tvém Macu.

## Každé další spuštění

```bash
cd "$HOME/Applications/seminarni-kolega-repo/second-brain"
bash start-mac.sh
```

Otevři `http://127.0.0.1:8766`. Knihovna a Google připojení zůstávají místní, API klíč případně zadej znovu. Ukončení aplikace: **Ctrl+C** v Terminálu. Podrobnosti o datech, zálohách a mazání jsou v [README](README.md).

Živý poslech v této verzi není zapnutý. Pro semináře zatím použij vlastní poznámky či povolené textové podklady; původní nespolehlivý přepis není základem odpovědí.
