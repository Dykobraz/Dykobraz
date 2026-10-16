# Jak spustit Seminárního kolegu na Macu

Aplikace běží na tvém Macu a ovládá se v Chromu. Účet u AI služby ani API klíč nepotřebuješ. První instalace stahuje několik GB modelů. Měj volné místo a nech Terminál otevřený.

## 1. Připrav Mac — pouze poprvé

Otevři **Terminál** (⌘ + mezerník, napiš Terminál).

Spusť:

```bash
xcode-select --install
```

Dokonči instalaci v okně macOS. Pokud systém oznámí, že nástroje už jsou nainstalované, pokračuj.

Ověř Homebrew:

```bash
brew --version
```

Pokud příkaz neexistuje, nainstaluj Homebrew podle **https://brew.sh**. Po instalaci proveď také jeho vypsané „Next steps“, aby příkaz `brew` fungoval v Terminálu. Poté otevři nové okno Terminálu.

## 2. Stáhni aplikaci z GitHubu

Následující příkazy vlož do Terminálu postupně. Složka `seminarni-kolega-repo` nesmí už existovat; případné vlastní soubory nemaž.

```bash
mkdir -p "$HOME/Applications"
git clone --branch seminarni-kolega --single-branch https://github.com/Dykobraz/Dykobraz.git "$HOME/Applications/seminarni-kolega-repo"
cd "$HOME/Applications/seminarni-kolega-repo/seminar-assistant"
bash setup-mac.sh
bash prepare-models.sh
```

Počkej na dokončení obou skriptů. Pokud příkaz vypíše chybu, nepokračuj dalším krokem; pošli samotnou chybu, bez obsahu semináře. Pokud je repozitář soukromý, přihlas se ke svému GitHub účtu jeho běžným postupem; přístupové tokeny neposílej do chatu.

## 3. Spusť aplikaci

```bash
cd "$HOME/Applications/seminarni-kolega-repo/seminar-assistant"
bash start-mac.sh
```

Nech toto okno Terminálu otevřené. V Chromu otevři `http://127.0.0.1:8765`.

1. Vlevo napiš, co se chceš naučit nebo na čem pracuješ.
2. Nejprve zkus přidat vlastní krátkou poznámku — ověříš tím místní AI model.
3. Pusť zkušební video v Chromu a klikni **Spustit poslech**.
4. Povol macOS požadovaný **záznam obrazovky a systémového zvuku**. Oprávnění najdeš v Nastavení systému → Soukromí a zabezpečení. Systém může jako žádající aplikaci uvést Terminál. Po změně oprávnění může být nutné aplikaci či Terminál znovu spustit.
5. Ověř indikátor zvuku a vyčkej na české poznámky. Zpracování probíhá po úsecích a podle výkonu může trvat desítky sekund i déle.

**Před seminářem ověř vše se stejnými sluchátky a webovou aplikací, které skutečně použiješ.** Nativní zachytávač zatím nebyl v tomto vývojovém prostředí sestaven ani vyzkoušen, protože běží na Linuxu. Funkčnost na tvém Macu není zatím potvrzená.

## Příští spuštění

Instalaci neopakuj. Stačí:

```bash
cd "$HOME/Applications/seminarni-kolega-repo/seminar-assistant"
bash start-mac.sh
```

Potom otevři v Chromu `http://127.0.0.1:8765`.

## Zastavení a zachování poznámek

- **Zastavit** ukončí poslech. Poznámky zůstanou v paměti, dokud aplikaci neukončíš nebo relaci nevymažeš.
- **Exportovat poznámky** stáhne soubor Markdown. Použij ho před ukončením, pokud chceš poznámky zachovat do příštího týdne.
- **Ctrl+C v Terminálu** ukončí aplikaci. Samotné zavření karty v Chromu poslech neukončí.
- Systémový zvuk zahrnuje i jiné aplikace a oznámení. Mikrofon ani vlastní promluvy se nezachytávají; můžeš je doplnit vlastní poznámkou.
- Zvuk a pracovní přepis se neukládají do souborů a neposílají poskytovateli AI. Poznámky mohou obsahovat chyby; doporučení si ověřuj.

## Aktualizace

Nejprve exportuj poznámky a ukonči aplikaci. Pokud jsi sám neupravoval zdrojové soubory:

```bash
cd "$HOME/Applications/seminarni-kolega-repo"
git pull --ff-only
cd seminar-assistant
bash setup-mac.sh
bash start-mac.sh
```

V Chromu pak použij ⌘⇧R. Pokud Git hlásí konflikt či vlastní změny, nic nemaž ani neresetuj; pošli hlášení.
