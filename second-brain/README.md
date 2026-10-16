# Second brain — přestavba

Samostatný nástupce Seminárního kolegy. Původní aplikace zůstává ve složce `seminar-assistant`.

## Směr

- Dlouhodobá osobní knihovna zdrojů, poznámek a projektů.
- U každé odpovědi dohledatelné pasáže původních zdrojů.
- Zřetelné rozlišení doložených informací, interpretací a navržených kroků.
- Zpracování výhradně místně, dokud uživatel nezmění svou volbu.
- Trvalé ukládání uživatelem vložených poznámek a zdrojů; žádné automatické ukládání zvuku či přepisů hovorů.
- Živý poslech bude samostatný vstup, až projde funkční zkouškou na cílovém Macu.

## Aktuální stav

`library.py` implementuje místní SQLite knihovnu, projekty, import textu, vyhledávání FTS5, přesné pasáže a export Markdown. Vyhledávání je zatím podle slov s podporou diakritiky, nikoli sémantické; nepoužívá model a neřeší české skloňování ani synonyma. Chybějící výsledky proto neznamenají, že informace v knihovně určitě není.

Výběr modelu, uživatelské rozhraní a integrace AI zatím nejsou dokončené. Čekají na rozhodnutí o místním versus cloudovém zpracování a na výkon Macu. Toto není hotová aplikace ke spuštění místo Seminárního kolegy.

Test jádra:

```bash
python3 -m unittest discover -s tests -v
```
