#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
#  meteor_ifb.sbatch  —  Pipeline Meteor2 complet sur le cluster IFB Core
#  Usage : sbatch meteor_ifb.sbatch
#  Wiki  : https://github.com/metagenopolis/meteor/wiki
#  IFB   : https://doc.cluster.france-bioinformatique.fr/slurm/slurm_user_guide
# ══════════════════════════════════════════════════════════════════════════════

# ── Identité du job ──────────────────────────────────────────────────────────
#SBATCH --job-name=meteor_pipeline
#SBATCH -A <votre_projet>           # ← remplacer par votre compte projet IFB

# ── Partition et temps ───────────────────────────────────────────────────────
# "fast" (<=24h) suffit pour la plupart des analyses sur quelques échantillons.
# Passer à "long" (<=30 jours) si vous traitez de grandes cohortes.
#SBATCH --partition=fast
#SBATCH --time=12:00:00             # adapter selon taille réelle (hh:mm:ss)

# ── Ressources ───────────────────────────────────────────────────────────────
# meteor mapping s'appuie sur bowtie2 → bien parallélisé, 8 CPUs est un bon
# compromis (rendements décroissants au-delà selon Amdahl).
# RAM : 16 GB couvre la plupart des catalogues "fast" ; augmenter à 40-60 GB
# pour les catalogues "full" (ex. hs_10_4_gut full ≈ 30 GB index bowtie2).
#SBATCH --cpus-per-task=8
#SBATCH --mem=20GB

# ── Logs ─────────────────────────────────────────────────────────────────────
# %N = nom du nœud, %j = jobID → facile à retrouver avec reportseff
#SBATCH -o logs/meteor.%N.%j.out
#SBATCH -e logs/meteor.%N.%j.err

# ══════════════════════════════════════════════════════════════════════════════
#  PARAMÈTRES UTILISATEUR  —  à adapter avant de lancer
# ══════════════════════════════════════════════════════════════════════════════

# Ecosystème cible (meteor download --help pour la liste complète)
ECOSYSTEM="hs_10_4_gut"         # ex: hs_10_4_gut | mouse_10_4_gut | ocean_10_4 ...

# Utiliser le catalogue "fast" (100 gènes core/MSP) ou "full" (tous les gènes)
# fast → moins de RAM/temps, pas de profiling fonctionnel
# full → profiling fonctionnel disponible, plus de RAM nécessaire
FAST_MODE=true                  # true | false

# Répertoires de travail (adapter à votre espace projet /shared/projects/...)
WORKDIR="${SLURM_SUBMIT_DIR}"   # répertoire depuis lequel sbatch est lancé
FASTQ_DIR="${WORKDIR}/fastq"    # vos fichiers .fastq.gz bruts
SAMPLE_DIR="${WORKDIR}/sample"
CATALOGUE_DIR="${WORKDIR}/catalogue"
MAPPING_DIR="${WORKDIR}/mapping"
PROFILE_DIR="${WORKDIR}/profiles"
MERGE_DIR="${WORKDIR}/merging"
STRAIN_DIR="${WORKDIR}/strain"
TREE_DIR="${WORKDIR}/tree"
LOG_DIR="${WORKDIR}/logs"

# Préfixe pour les fichiers de fusion (meteor merge -p)
MERGE_PREFIX="run1"

# Seuil d'identité pour le mapping
# 97% recommandé pour catalogue fast, 95% pour full
IDENTITY_THRESHOLD=97           # ignoré si FAST_MODE=true (Meteor adapte auto)

# Profiling strain (nécessite --kf au mapping)
DO_STRAIN=true                  # true | false
# Seuils strain (valeurs de production ; baisser pour tests sur données raréfiées)
STRAIN_MIN_DEPTH=50             # -m : profondeur minimale (reads/position)
STRAIN_MIN_COV=0.8              # -c : fraction minimale de gènes core couverts

# Construction des arbres phylogénétiques
DO_TREE=true                    # true | false
TREE_MIN_SAMPLES=4              # -g : nb min d'échantillons pour construire un arbre
TREE_THREADS=8                  # -t : threads pour RAxML/FastTree

# ══════════════════════════════════════════════════════════════════════════════
#  DÉBUT DU SCRIPT
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail   # arrêt immédiat en cas d'erreur
mkdir -p "${LOG_DIR}"

echo "════════════════════════════════════════════════════"
echo "  Meteor2 pipeline — IFB Core Cluster"
echo "  JobID     : ${SLURM_JOB_ID}"
echo "  Nœud      : ${SLURM_NODELIST}"
echo "  CPUs      : ${SLURM_CPUS_PER_TASK}"
echo "  RAM       : ${SLURM_MEM_PER_NODE} MB"
echo "  Start     : $(date)"
echo "════════════════════════════════════════════════════"

# ── Chargement du module ─────────────────────────────────────────────────────
module load meteor
echo "[INFO] Meteor version : $(meteor --version 2>&1 | head -1)"

# ── Détermination du nom du catalogue ────────────────────────────────────────
if ${FAST_MODE}; then
    CATALOGUE_FLAG="--fast"
    CATALOGUE_NAME="${ECOSYSTEM}_taxo_fast"
else
    CATALOGUE_FLAG=""
    CATALOGUE_NAME="${ECOSYSTEM}_taxo"
fi
CATALOGUE_PATH="${CATALOGUE_DIR}/${CATALOGUE_NAME}"

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 1 — Téléchargement du catalogue (si absent)
# ══════════════════════════════════════════════════════════════════════════════
if [ ! -d "${CATALOGUE_PATH}" ]; then
    echo ""
    echo "── ÉTAPE 1 : Téléchargement du catalogue ${ECOSYSTEM} ──"
    mkdir -p "${CATALOGUE_DIR}"
    srun meteor download \
        -i "${ECOSYSTEM}" \
        ${CATALOGUE_FLAG} \
        -o "${CATALOGUE_DIR}"
    echo "[OK] Catalogue disponible dans ${CATALOGUE_PATH}"
else
    echo "[SKIP] Catalogue déjà présent : ${CATALOGUE_PATH}"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 2 — Organisation des fichiers FASTQ
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "── ÉTAPE 2 : Organisation des FASTQ ──"
mkdir -p "${SAMPLE_DIR}"

# Si la structure échantillon existe déjà, on passe
if [ -z "$(ls -A ${SAMPLE_DIR} 2>/dev/null)" ]; then
    # Adapter -m si vos noms de fichiers encodent l'ID échantillon
    # ex: -m 'SAMPLE_\d+' pour des fichiers contenant SAMPLE_01, SAMPLE_02...
    srun meteor fastq \
        -i "${FASTQ_DIR}" \
        -o "${SAMPLE_DIR}"
    echo "[OK] Répertoire échantillon créé : ${SAMPLE_DIR}"
else
    echo "[SKIP] Structure échantillon déjà présente."
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 3 — Mapping + comptage des gènes (un sous-job par échantillon)
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "── ÉTAPE 3 : Mapping des échantillons ──"
mkdir -p "${MAPPING_DIR}"

# --kf : conserver le fichier CRAM filtré pour le profiling strain
# $SLURM_CPUS_PER_TASK synchronise les threads bowtie2 avec les CPUs alloués
KF_FLAG=""
if ${DO_STRAIN}; then
    KF_FLAG="--kf"
fi

for SUBDIR in "${SAMPLE_DIR}"/*/; do
    [ -d "${SUBDIR}" ] || continue
    SAMPLE_ID=$(basename "${SUBDIR}")
    MAPPING_OUT="${MAPPING_DIR}/${SAMPLE_ID}"

    if [ -d "${MAPPING_OUT}" ]; then
        echo "  [SKIP] Mapping déjà fait pour ${SAMPLE_ID}"
        continue
    fi

    echo "  [RUN] Mapping : ${SAMPLE_ID}"
    srun --ntasks=1 meteor mapping \
        -i "${SUBDIR}" \
        -r "${CATALOGUE_PATH}" \
        -o "${MAPPING_DIR}" \
        -t "${SLURM_CPUS_PER_TASK}" \
        ${KF_FLAG}
done
echo "[OK] Mapping terminé."

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 4 — Profiling taxonomique (et fonctionnel si catalogue full)
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "── ÉTAPE 4 : Profiling ──"
mkdir -p "${PROFILE_DIR}"

for SUBDIR in "${MAPPING_DIR}"/*/; do
    [ -d "${SUBDIR}" ] || continue
    SAMPLE_ID=$(basename "${SUBDIR}")
    PROFILE_OUT="${PROFILE_DIR}/${SAMPLE_ID}"

    if [ -d "${PROFILE_OUT}" ]; then
        echo "  [SKIP] Profil déjà calculé pour ${SAMPLE_ID}"
        continue
    fi

    echo "  [RUN] Profile : ${SAMPLE_ID}"
    srun --ntasks=1 meteor profile \
        -i "${SUBDIR}" \
        -r "${CATALOGUE_PATH}" \
        -o "${PROFILE_DIR}" \
        -n coverage
done
echo "[OK] Profiling terminé."

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 5 — Fusion des profils
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "── ÉTAPE 5 : Fusion des profils ──"
mkdir -p "${MERGE_DIR}"

srun meteor merge \
    -i "${PROFILE_DIR}" \
    -r "${CATALOGUE_PATH}" \
    -o "${MERGE_DIR}" \
    -p "${MERGE_PREFIX}"

echo "[OK] Tables fusionnées dans ${MERGE_DIR}/"

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 6 — Profiling strain (optionnel)
# ══════════════════════════════════════════════════════════════════════════════
if ${DO_STRAIN}; then
    echo ""
    echo "── ÉTAPE 6 : Profiling strain ──"
    mkdir -p "${STRAIN_DIR}"

    for SUBDIR in "${MAPPING_DIR}"/*/; do
        [ -d "${SUBDIR}" ] || continue
        SAMPLE_ID=$(basename "${SUBDIR}")

        # Vérifier qu'un fichier CRAM existe (nécessite --kf à l'étape mapping)
        if ! ls "${SUBDIR}"/*.cram 1>/dev/null 2>&1; then
            echo "  [WARN] Pas de CRAM pour ${SAMPLE_ID} (--kf absent au mapping ?)"
            continue
        fi

        echo "  [RUN] Strain : ${SAMPLE_ID}"
        srun --ntasks=1 meteor strain \
            -i "${SUBDIR}" \
            -r "${CATALOGUE_PATH}" \
            -o "${STRAIN_DIR}" \
            -m "${STRAIN_MIN_DEPTH}" \
            -c "${STRAIN_MIN_COV}" \
            --kc
    done
    echo "[OK] Profiling strain terminé."
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 7 — Construction des arbres phylogénétiques (optionnel)
# ══════════════════════════════════════════════════════════════════════════════
if ${DO_STRAIN} && ${DO_TREE}; then
    echo ""
    echo "── ÉTAPE 7 : Construction des arbres ──"
    mkdir -p "${TREE_DIR}"

    srun meteor tree \
        -i "${STRAIN_DIR}" \
        -o "${TREE_DIR}" \
        -g "${TREE_MIN_SAMPLES}" \
        -t "${TREE_THREADS}"

    echo "[OK] Arbres disponibles dans ${TREE_DIR}/"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  RÉSUMÉ FINAL
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════"
echo "  Pipeline terminé : $(date)"
echo "  Résultats :"
echo "    Mapping   → ${MAPPING_DIR}/"
echo "    Profils   → ${PROFILE_DIR}/"
echo "    Fusion    → ${MERGE_DIR}/${MERGE_PREFIX}_msp.tsv"
if ${DO_STRAIN}; then
    echo "    Strains   → ${STRAIN_DIR}/"
fi
if ${DO_STRAIN} && ${DO_TREE}; then
    echo "    Arbres    → ${TREE_DIR}/"
fi
echo ""
echo "  Efficacité du job (après complétion) :"
echo "    module load reportseff && reportseff ${SLURM_JOB_ID}"
echo "════════════════════════════════════════════════════"