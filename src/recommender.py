from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

try:
    from .catalogue_utils import (
        TAXON_IRI,
        SAMPLE_FILTER,
        _flag_true,
        _release_as_int,
        _score_db_entry,
        _to_list,
        db_scope,
    )
    from .recommender_config import PREFERENCE_ALIASES, SCORE_WEIGHTS
except ImportError:  # pragma: no cover - fallback for direct execution
    from catalogue_utils import (
        TAXON_IRI,
        SAMPLE_FILTER,
        _flag_true,
        _release_as_int,
        _score_db_entry,
        _to_list,
        db_scope,
    )
    from recommender_config import PREFERENCE_ALIASES, SCORE_WEIGHTS


@dataclass(slots=True)
class CatalogDatabase:
    """Représentation typée d'une base de données du catalogue (un fichier JSON dans data/databases/).

    Sert de couche intermédiaire entre le JSON brut (dict) et le moteur de
    recommandation : évite de refaire des .get() défensifs partout, et donne
    accès direct aux relations hasPart / isPartOf utilisées pour les extensions
    parent/grand-parent.
    """
    id: str
    raw: dict[str, Any]
    sample: list[dict[str, Any]] = field(default_factory=list)
    origin: list[dict[str, Any]] = field(default_factory=list)
    taxonomic_scope: list[dict[str, Any]] = field(default_factory=list)
    has_part: list[dict[str, Any]] = field(default_factory=list)
    is_part_of: list[dict[str, Any]] = field(default_factory=list)
    compatible_tools: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, db_id: str, payload: dict[str, Any]) -> "CatalogDatabase":
        """Construit un CatalogDatabase depuis le dict JSON brut d'une BD.

        payload est gardé tel quel dans `raw` (pour l'affichage app.py qui lit
        encore certains champs directement), et les listes clés (sample,
        hasPart, isPartOf, ...) sont normalisées via _to_list pour ne jamais
        avoir à vérifier "est-ce une liste ou un objet seul" ailleurs.
        """
        return cls(
            id=db_id,
            raw=payload,
            sample=_to_list(payload.get("sample")),
            origin=_to_list(payload.get("origin")),
            taxonomic_scope=_to_list(payload.get("taxonomic_scope")),
            has_part=_to_list(payload.get("hasPart")),
            is_part_of=_to_list(payload.get("isPartOf")),
            compatible_tools=_to_list(payload.get("compatible_tools")),
        )


@dataclass(slots=True)
class CatalogTool:
    """Représentation typée d'un outil du catalogue (un fichier JSON dans data/tools/).

    uses_databases est la liste des BDs que cet outil sait effectivement
    utiliser (chaque entrée est un dict avec @id, taxonomy_system, release...).
    C'est cette liste, et uniquement elle, qui définit la compatibilité
    outil/BD dans tout le moteur — pas le simple fait qu'une BD existe dans le
    catalogue.
    """
    id: str
    raw: dict[str, Any]
    supports_shortreads: bool = False
    supports_longreads: bool = False
    strain_level: bool = False
    functional_profiling: bool = False
    ram: int | None = None
    uses_databases: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, tool_id: str, payload: dict[str, Any]) -> "CatalogTool":
        """Construit un CatalogTool depuis le dict JSON brut d'un outil, avec
        des valeurs par défaut sûres (False/None) si un champ est absent."""
        return cls(
            id=tool_id,
            raw=payload,
            supports_shortreads=bool(payload.get("supports_shortreads", False)),
            supports_longreads=bool(payload.get("supports_longreads", False)),
            strain_level=bool(payload.get("strain_level", False)),
            functional_profiling=bool(payload.get("functional_profiling", False)),
            ram=payload.get("ram"),
            uses_databases=_to_list(payload.get("uses_databases")),
        )

    def supports_reads(self, reads_key: str) -> bool:
        """Vrai si l'outil supporte le type de reads demandé ("Short Reads" /
        "Long Reads"). Non utilisée directement par recommend() actuellement
        (qui teste les attributs bruts dans tool_is_compatible), mais
        disponible si tu veux simplifier ces tests plus tard."""
        if reads_key == "Short Reads":
            return self.supports_shortreads
        if reads_key == "Long Reads":
            return self.supports_longreads
        return False


@dataclass(slots=True)
class SurveyContext:
    """Regroupe en un seul objet toutes les réponses du questionnaire utilisateur
    (app.py) pour un appel à recommend(). Évite de faire passer 9 paramètres
    séparés à chaque fonction interne du moteur — on passe `ctx` partout à la
    place, et les propriétés ci-dessous dérivent les booléens/listes utiles
    à la demande plutôt que de les recalculer à chaque appelant.
    """
    sample_key: str | None #formerly envo_key
    origin_key: str | None #formerly host_key
    selected_orgs: list[str]
    reads_key: str
    pref_taxo: str
    wants_strain: bool
    wants_func: bool
    max_ram: int

    @property
    def wants_virus(self) -> bool:
        """Vrai si l'utilisateur a coché 'Virus' parmi les taxons ciblés."""
        return "Virus" in self.selected_orgs

    @property
    def wants_fungi(self) -> bool:
        """Vrai si l'utilisateur a coché 'Fungi' parmi les taxons ciblés."""
        return "Fungi" in self.selected_orgs

    @property
    def wants_euk(self) -> bool:
        """Vrai si l'utilisateur a coché 'Eukaryota' parmi les taxons ciblés."""
        return "Eukaryota" in self.selected_orgs

    @property
    def wants_bacteria(self) -> bool:
        """Vrai si l'utilisateur a coché 'Bacteria' parmi les taxons ciblés."""
        return "Bacteria" in self.selected_orgs

    @property
    def wants_archaea(self) -> bool:
        """Vrai si l'utilisateur a coché 'Archaea' parmi les taxons ciblés."""
        return "Archaea" in self.selected_orgs

    @property
    def taxon_keys(self) -> list[str]:
        """Convertit les noms de taxons choisis (ex. 'Bacteria') en leurs IRI
        NCBITaxon (ex. 'NCBITaxon_2') via le mapping TAXON_IRI, pour les
        comparer aux tags des BDs."""
        return [TAXON_IRI[o] for o in self.selected_orgs]


def _normalize_pref(pref_taxo: str | None) -> str:
    """Normalise la préférence de taxonomie de référence (GTDB/NCBI/Any) saisie
    par l'utilisateur vers une forme canonique en minuscules. Gère les
    synonymes de "aucune préférence" (None, "Indifférent", "Any", ...) via
    PREFERENCE_ALIASES (recommender_config.py), pour que l'UI puisse être
    traduite/reformulée sans casser la comparaison faite plus loin dans recommend()."""
    if pref_taxo is None:
        return "any"
    return PREFERENCE_ALIASES.get(str(pref_taxo).strip().lower(), str(pref_taxo).strip().lower())


def tool_is_compatible(tool: dict[str, Any] | CatalogTool, ctx: SurveyContext) -> bool:
    """Filtre grossier appliqué à un outil AVANT même de regarder ses BDs :
    reads courts/longs, capacités requises (strain-level, functional
    profiling) et RAM disponible. Si un de ces critères ne matche pas,
    l'outil est écarté immédiatement — inutile d'aller chercher une BD pour lui.

    Accepte à la fois un CatalogTool (chemin normal, utilisé par recommend())
    et un simple dict (chemin de compatibilité / tests, même logique mais lue
    directement sur le JSON brut via .get()).
    """
    if isinstance(tool, CatalogTool):
        if ctx.reads_key == "Short Reads" and not tool.supports_shortreads:
            return False
        if ctx.reads_key == "Long Reads" and not tool.supports_longreads:
            return False
        if ctx.wants_strain and not tool.strain_level:
            return False
        if ctx.wants_func and not tool.functional_profiling:
            return False
        if tool.ram and isinstance(tool.ram, (int, float)) and tool.ram > ctx.max_ram:
            return False
        return True

    # if ctx.reads_key == "Short Reads" and not tool.get("supports_shortreads"):
    #     return False
    # if ctx.reads_key == "Long Reads" and not tool.get("supports_longreads"):
    #     return False
    # if ctx.wants_strain and not _flag_true(tool.get("strain_level")):
    #     return False
    # if ctx.wants_func and not _flag_true(tool.get("functional_profiling")):
    #     return False
    # ram = tool.get("ram")
    # if ram and isinstance(ram, (int, float)) and ram > ctx.max_ram:
    #     return False
    # return True


# def _tool_supports(tool: dict[str, Any], candidates: list[str]) -> bool:
#     """Vrai si au moins une des clés de `candidates` est un flag "vrai" (via
#     _flag_true) dans le dict brut `tool`. Utilitaire générique non utilisé
#     actuellement dans le flux principal de ce fichier (recommend() teste les
#     attributs CatalogTool directement) — gardée pour compatibilité/tests sur
#     des tools encore sous forme de dict."""
#     for k in candidates:
#         if _flag_true(tool.get(k)):
#             return True
#     return False


def _to_catalog_wrapper(databases: dict[str, Any], tools: dict[str, Any]) -> tuple[dict[str, CatalogDatabase], dict[str, CatalogTool]]:
    """Convertit les dicts bruts {id: json} chargés par load_catalogue() en
    dicts {id: CatalogDatabase} / {id: CatalogTool}. Appelée une seule fois en
    tête de recommend(), pour que tout le reste du moteur travaille sur des
    objets typés plutôt que sur des dicts JSON non validés."""
    wrapped_databases = {k: CatalogDatabase.from_dict(k, v) for k, v in databases.items()}
    wrapped_tools = {k: CatalogTool.from_dict(k, v) for k, v in tools.items()}
    return wrapped_databases, wrapped_tools


def _weighted_rank_tuple(result: dict[str, Any], databases: dict[str, Any], ctx: SurveyContext) -> tuple[Any, ...]:
    """Construit la clé de tri utilisée par sorted(results, key=...) dans recommend().

    Ne calcule PAS un score : produit un tuple comparé élément par élément,
    donc un tri à plusieurs niveaux de priorité (comme un tri Excel
    multi-colonnes) :
      1. -result["score"]  -> score décroissant (critère principal).
      2. -broad_boost      -> en cas d'égalité de score ET si l'utilisateur
                               n'a précisé ni sample_key ni origin_key (contexte
                               "Multi-environments/Autre"), les BDs composites
                               (qui ont des hasPart) passent devant les BDs simples.
      3. -part_count        -> nouvelle égalité -> la BD avec le plus de
                               sous-bases (hasPart) passe devant : préférence
                               pour l'exhaustivité en contexte large.

    Le signe "-" sur chaque terme sert juste à inverser l'ordre naturel de
    sorted() (croissant) en "plus grand = en premier".
    """
    db_id = result.get("db_id")
    db_obj = databases.get(db_id, {}) if db_id else {}
    part_count = len([p for p in _to_list(db_obj.get("hasPart")) if isinstance(p, dict) and p.get("@id")])
    # broad_boost = SCORE_WEIGHTS["broad_context_bonus"] if (ctx.sample_key is None and ctx.origin_key is None and part_count > 0) else 0
    broad_boost = SCORE_WEIGHTS["broad_context_bonus"] if (ctx.sample_key is None and ctx.origin_key is None and db_obj.get("sample") is None and db_obj.get("origin") is None else 0

    return (-result["score"], -broad_boost, -part_count)


def _find_tool_db_entry(tool: CatalogTool, db_id: str) -> dict[str, Any] | None:
    """Retourne l'entrée de tool.uses_databases correspondant à db_id, si elle existe.

    C'est ce qui détermine si "l'outil peut utiliser" une base donnée : la base
    doit être explicitement déclarée dans uses_databases de l'outil, pas juste
    exister dans le catalogue.
    """
    for u in _to_list(tool.uses_databases):
        if isinstance(u, dict) and u.get("@id") == db_id:
            return u
    return None


def _extension_chain(
    tool_id: str,
    tool: CatalogTool,
    wrapped_databases: dict[str, CatalogDatabase],
    databases: dict[str, Any],
    base_db_id: str,
    ctx: SurveyContext,
    max_levels: int = 2,
) -> list[dict[str, Any]]:
    """
    Remonte isPartOf depuis base_db_id (parent, puis grand-parent) et génère
    une entrée de résultat pour chaque ancêtre que l'outil sait AUSSI utiliser
    (présent dans tool.uses_databases).

    Le score de chaque ancêtre est recalculé via _score_db_entry, qui applique
    déjà nativement l'héritage de score depuis l'enfant qui matche le mieux
    (SCORE_WEIGHTS["part_score_inheritance"] + _composite_ancestry_bonus) —
    on ne réimplémente donc rien de cette logique ici, on la réutilise telle quelle.
    """
    entries: list[dict[str, Any]] = []
    child_id = base_db_id
    labels = ["parent", "grandparent"]

    for level in range(max_levels):
        child_db = wrapped_databases.get(child_id)
        if child_db is None:
            break
        parent_ids = [
            p.get("@id") for p in child_db.is_part_of
            if isinstance(p, dict) and p.get("@id")
        ]
        if not parent_ids:
            break

        parent_id = parent_ids[0]
        entry_u = _find_tool_db_entry(tool, parent_id)
        if entry_u is None:
            # L'outil ne déclare pas utiliser ce parent -> on arrête de remonter.
            break

        parent_db = wrapped_databases.get(parent_id)

        # Réutilise _score_db_entry telle quelle : elle relit hasPart du parent,
        # retrouve le meilleur enfant qui matche (potentiellement base_db_id
        # lui-même, ou un autre enfant si celui-ci score mieux) et applique déjà
        # part_score_inheritance + _composite_ancestry_bonus.
        score = _score_db_entry(
            parent_id, databases, ctx.sample_key, ctx.origin_key, ctx.taxon_keys,
            ctx.pref_taxo, ctx.wants_virus, ctx.wants_fungi, ctx.wants_euk,
            ctx.wants_bacteria, ctx.wants_archaea, entry_u.get("taxonomy_system"),
        )

        if score > 0:
            dl_info = []
            if parent_db:
                for ct in parent_db.compatible_tools:
                    if isinstance(ct, dict) and ct.get("@id") == tool_id:
                        dl_info = [v for v in ct.get("DB", []) if isinstance(v, dict)]
                        break
            releases = [str(x) for x in _to_list(entry_u.get("release")) if x is not None]

            entries.append({
                "tool_id": tool_id,
                "tool": tool.raw,
                "db_id": parent_id,
                "db": parent_db.raw if parent_db else {},
                "db_ts": entry_u.get("taxonomy_system"),
                "db_rel": entry_u,
                "score": score,
                "dl": dl_info,
                "releases": releases,
                "extension_of": child_id,
                "extension_level": labels[level] if level < len(labels) else f"level_{level + 1}",
            })

        # On continue de remonter vers le niveau suivant même si ce niveau-ci
        # n'a pas donné d'entrée valide (score <= 0) : un grand-parent composite
        # peut rester pertinent même si le parent direct ne matche pas.
        child_id = parent_id

    return entries


def recommend(databases: dict[str, Any], tools: dict[str, Any], sample_key: str | None, origin_key: str | None, selected_orgs: list[str], reads_key: str, pref_taxo: str, wants_strain: bool, wants_func: bool, max_ram: int) -> list[dict[str, Any]]:
    """Point d'entrée principal du moteur : pour chaque outil compatible avec
    les critères techniques (reads, RAM, capacités), trouve sa MEILLEURE base
    de données compatible, construit une entrée de résultat par couple
    (outil, meilleure BD), trie l'ensemble, puis insère après chaque entrée
    les extensions parent/grand-parent éventuelles (_extension_chain).

    Appelée depuis app.py (render_questionnaire) avec les réponses brutes du
    questionnaire ; construit ctx en interne pour ne pas exposer
    SurveyContext à l'appelant.
    """
    ctx = SurveyContext(
        sample_key=sample_key,
        origin_key=origin_key,
        selected_orgs=selected_orgs,
        reads_key=reads_key,
        pref_taxo=pref_taxo,
        wants_strain=wants_strain,
        wants_func=wants_func,
        max_ram=max_ram,
    )

    wrapped_databases, wrapped_tools = _to_catalog_wrapper(databases, tools)
    results: list[dict[str, Any]] = []

    # Étape 1 : pour chaque outil compatible techniquement, on cherche parmi
    # toutes ses BDs déclarées (uses_databases) celle qui obtient le meilleur
    # score vis-à-vis du contexte utilisateur (sample/origin/taxons/pref_taxo).
    # On ne garde qu'UNE seule BD par outil à ce stade (la meilleure) — les BDs
    # moins bonnes pour cet outil sont ignorées, pas de doublon outil x BD1/BD2 ici.
    for tool_id, tool in wrapped_tools.items():
        if not tool_is_compatible(tool, ctx):
            continue

        best_db_score = -1
        best_db_id = None
        best_db_ts = None
        best_db_rel = None

        for u in _to_list(tool.uses_databases):
            if not isinstance(u, dict):
                continue
            db_id = u.get("@id", "")
            ts = u.get("taxonomy_system")

            # Filtre dur : si l'utilisateur a une préférence de taxonomie de
            # référence (GTDB ou NCBI), on écarte purement et simplement les
            # entrées uses_databases qui ne correspondent pas — pas de score
            # réduit, l'entrée n'est même pas candidate.
            pref_norm = _normalize_pref(pref_taxo)
            if pref_norm != "any":
                pref_lower = pref_norm
                if isinstance(ts, list):
                    if pref_lower not in [str(x).lower() for x in ts]:
                        continue
                elif ts and str(ts).lower() != pref_lower:
                    continue

            # Score de cette entrée (outil, BD) vis-à-vis du contexte complet
            # (sample/origin/taxons ciblés) — toute la logique de matching
            # ENVO/host/taxon/GTDB vit dans catalogue_utils._score_db_entry.
            sc = _score_db_entry(
                db_id,
                databases,
                sample_key,
                origin_key,
                ctx.taxon_keys,
                pref_taxo,
                ctx.wants_virus,
                ctx.wants_fungi,
                ctx.wants_euk,
                ctx.wants_bacteria,
                ctx.wants_archaea,
                ts,
            )
            # On ne garde que le meilleur score vu jusqu'ici pour cet outil.
            if sc > best_db_score:
                best_db_score = sc
                best_db_id = db_id
                best_db_ts = ts
                best_db_rel = u

        # score <= 0 signifie "aucune BD ne satisfait vraiment les contraintes"
        # (cf. _score_db_entry qui retourne -1 en cas de contrainte violée) ->
        # on rejette l'outil entièrement plutôt que de proposer un mauvais match.
        if best_db_score <= 0:
            continue

        # Récupère les variantes de téléchargement (dl_info) déclarées côté BD
        # pour CE couple (tool_id, best_db_id) précisément — un même DB peut
        # avoir des liens de téléchargement différents selon l'outil qui l'utilise.
        db_obj = wrapped_databases.get(best_db_id, None)
        dl_info = []
        if db_obj:
            for ct in db_obj.compatible_tools:
                if isinstance(ct, dict) and ct.get("@id") == tool_id:
                    dl_info = [v for v in ct.get("DB", []) if isinstance(v, dict)]
                    break

        # Retrouve les releases compatibles déclarées côté outil pour cette BD
        # (ex. ["r220", "r226"] pour une entrée GTDB).
        releases = []
        for u in _to_list(tool.uses_databases):
            if isinstance(u, dict) and u.get("@id") == best_db_id:
                r = _to_list(u.get("release"))
                releases = [str(x) for x in r if x is not None]

        results.append(
            {
                "tool_id": tool_id,
                "tool": tool.raw,
                "db_id": best_db_id,
                "db": db_obj.raw if db_obj else {},
                "db_ts": best_db_ts,
                "db_rel": best_db_rel,
                "score": best_db_score,
                "dl": dl_info,
                "releases": releases,
            }
        )

    # Étape 2 : tri par pertinence décroissante (voir _weighted_rank_tuple).
    ranked = sorted(results, key=lambda r: _weighted_rank_tuple(r, databases, ctx))

    # Étape 3 : pour chaque couple (outil, BD) déjà classé, on insère juste
    # après lui ses extensions parent/grand-parent éventuelles (voir
    # _extension_chain). seen_pairs empêche qu'un couple (outil, BD) apparaisse
    # deux fois — que ce soit deux extensions identiques générées séparément,
    # ou une extension qui correspond à un couple déjà présent nativement dans `ranked`.
    final: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for r in ranked:
        pair = (r["tool_id"], r["db_id"])
        if pair in seen_pairs:
            continue
        final.append(r)
        seen_pairs.add(pair)
        for ext in _extension_chain(
            r["tool_id"], wrapped_tools[r["tool_id"]], wrapped_databases, databases, r["db_id"], ctx
        ):
            ext_pair = (ext["tool_id"], ext["db_id"])
            if ext_pair in seen_pairs:
                continue
            final.append(ext)
            seen_pairs.add(ext_pair)

    return final