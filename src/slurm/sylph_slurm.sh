#!/bin/bash
#SBATCH --job-name=sylph_profile
#SBATCH --output=sylph_%j.out
#SBATCH --error=sylph_%j.err
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --partition=fast
#SBATCH --account=YOUR_PROJECT_NAME

# Script SLURM pour profiler des métagénomes avec Sylph
# Base de données: GTDB-226 (pré-installée sur le cluster)

# ==============================================================================
# CONFIGURATION - À MODIFIER SELON VOS BESOINS
# ==============================================================================

# Chemin vers la base de données GTDB-226 (pre-sketched Sylph database)
# Sur IFB, utilisez /shared/bank/ pour les bases publiques ou /shared/projects/ pour votre projet
SYLPH_DATABASE="/shared/bank/sylph/gtdb-r226.syldb"
# OU si dans votre projet:
# SYLPH_DATABASE="/shared/projects/YOUR_PROJECT_NAME/databases/sylph/gtdb-r226.syldb"

# Fichiers d'entrée (reads paired-end)
# Utilisez /shared/projects/YOUR_PROJECT_NAME/ pour vos données
FORWARD_READS="/shared/projects/YOUR_PROJECT_NAME/data/sample_R1.fastq.gz"
REVERSE_READS="/shared/projects/YOUR_PROJECT_NAME/data/sample_R2.fastq.gz"

# Nom de l'échantillon (pour les fichiers de sortie)
SAMPLE_NAME="sample01"

# Répertoire de sortie (dans votre espace projet)
OUTPUT_DIR="/shared/projects/YOUR_PROJECT_NAME/results/sylph_output"

# Nombre de threads (doit correspondre à --cpus-per-task)
THREADS=16

# Mode de profiling: "direct" ou "sketch_first"
# - "direct": profile directement depuis les reads (sylph v0.6+, plus simple)
# - "sketch_first": sketch les reads d'abord, puis profile (classique, utile pour multi-profiling)
PROFILING_MODE="direct"

# Options pour sylph-tax (intégration taxonomique)
GTDB_VERSION="GTDB_r226"  # Doit correspondre à votre database
TAXONOMY_DIR="/shared/projects/YOUR_PROJECT_NAME/databases/sylph_taxonomy"

# ==============================================================================
# INITIALISATION
# ==============================================================================

echo "=========================================="
echo "Sylph Taxonomic Profiling"
echo "=========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "=========================================="

# Créer les répertoires de sortie
mkdir -p ${OUTPUT_DIR}
mkdir -p ${TAXONOMY_DIR}

# Charger le module Sylph (si disponible) ou conda
# Option 1: Si Sylph est disponible comme module
# module load sylph

# Option 2: Si vous utilisez un environnement conda personnel
module load conda
conda activate sylph

# Option 3: Si vous utilisez Apptainer/Singularity
# module load apptainer
# SYLPH_CONTAINER="/path/to/sylph.sif"

# Vérification que Sylph est disponible
if ! command -v sylph &> /dev/null; then
    echo "ERROR: sylph command not found!"
    echo "Please check your conda environment."
    exit 1
fi

# Afficher la version de Sylph
echo "Sylph version:"
sylph --version

# Vérifier que la base de données existe
if [ ! -f "$SYLPH_DATABASE" ]; then
    echo "ERROR: Database not found at $SYLPH_DATABASE"
    exit 1
fi

echo "Using database: $SYLPH_DATABASE"
echo "Profiling mode: $PROFILING_MODE"
echo "=========================================="

# ==============================================================================
# PROFILING AVEC SYLPH
# ==============================================================================

if [ "$PROFILING_MODE" = "direct" ]; then
    # MODE 1: Profiling direct depuis les reads (sylph v0.6+)
    # Plus simple et recommandé pour la plupart des cas
    
    echo "Starting direct profiling (without pre-sketching)..."
    echo "Forward reads: $FORWARD_READS"
    echo "Reverse reads: $REVERSE_READS"
    echo "Threads: $THREADS"
    echo ""
    
    sylph profile ${SYLPH_DATABASE} \
        -1 ${FORWARD_READS} \
        -2 ${REVERSE_READS} \
        -t ${THREADS} \
        -o ${OUTPUT_DIR}/${SAMPLE_NAME}.tsv
    
    PROFILE_OUTPUT="${OUTPUT_DIR}/${SAMPLE_NAME}.tsv"
    
else
    # MODE 2: Sketch d'abord, puis profiling
    # Utile si vous voulez profiler le même échantillon contre plusieurs databases
    
    echo "Step 1: Sketching reads..."
    echo "Forward reads: $FORWARD_READS"
    echo "Reverse reads: $REVERSE_READS"
    echo ""
    
    # Copier les fichiers dans le répertoire de sortie pour éviter les conflits
    cp ${FORWARD_READS} ${OUTPUT_DIR}/
    cp ${REVERSE_READS} ${OUTPUT_DIR}/
    
    FWD_BASENAME=$(basename ${FORWARD_READS})
    REV_BASENAME=$(basename ${REVERSE_READS})
    
    cd ${OUTPUT_DIR}
    
    sylph sketch \
        -1 ${FWD_BASENAME} \
        -2 ${REV_BASENAME} \
        -t ${THREADS}
    
    SKETCH_FILE="${FWD_BASENAME}.paired.sylsp"
    
    echo ""
    echo "Step 2: Profiling from sketch..."
    
    sylph profile ${SYLPH_DATABASE} \
        ${SKETCH_FILE} \
        -t ${THREADS} \
        -o ${SAMPLE_NAME}.tsv
    
    cd -
    
    PROFILE_OUTPUT="${OUTPUT_DIR}/${SAMPLE_NAME}.tsv"
fi

# Vérifier le code de sortie
if [ $? -eq 0 ]; then
    echo "Sylph profiling completed successfully!"
else
    echo "ERROR: Sylph profiling failed!"
    exit 1
fi

# ==============================================================================
# INTÉGRATION TAXONOMIQUE AVEC SYLPH-TAX
# ==============================================================================

echo ""
echo "=========================================="
echo "Generating taxonomic profiles with sylph-tax"
echo "=========================================="

# Vérifier si sylph-tax est installé
if ! command -v sylph-tax &> /dev/null; then
    echo "WARNING: sylph-tax not found. Installing..."
    conda install -c bioconda sylph-tax -y
fi

# Télécharger les fichiers de taxonomie GTDB si nécessaire
if [ ! -f "${TAXONOMY_DIR}/${GTDB_VERSION}.tsv" ]; then
    echo "Downloading GTDB taxonomy files..."
    sylph-tax download --download-to ${TAXONOMY_DIR}
fi

# Générer le profil taxonomique (format .sylphmpa similaire à MetaPhlAn)
echo "Creating taxonomic profile..."
sylph-tax taxprof ${PROFILE_OUTPUT} \
    -t ${GTDB_VERSION} \
    -o ${OUTPUT_DIR}/${SAMPLE_NAME}_

# Le fichier de sortie sera nommé automatiquement selon le nom de l'échantillon
# Renommer pour clarté
if [ -f "${OUTPUT_DIR}/${SAMPLE_NAME}_"*.sylphmpa ]; then
    mv ${OUTPUT_DIR}/${SAMPLE_NAME}_*.sylphmpa ${OUTPUT_DIR}/${SAMPLE_NAME}.sylphmpa
fi

# ==============================================================================
# GÉNÉRATION DE STATISTIQUES ET RÉSUMÉS
# ==============================================================================

echo ""
echo "Generating summary statistics..."

# Extraire les top 20 génomes détectés
echo "Top 20 detected genomes:" > ${OUTPUT_DIR}/${SAMPLE_NAME}_top20.txt
head -21 ${PROFILE_OUTPUT} | tail -20 >> ${OUTPUT_DIR}/${SAMPLE_NAME}_top20.txt

# Compter le nombre de génomes détectés
NUM_GENOMES=$(tail -n +2 ${PROFILE_OUTPUT} | wc -l)
echo "Total genomes detected: $NUM_GENOMES" > ${OUTPUT_DIR}/${SAMPLE_NAME}_stats.txt

# Extraire les statistiques au niveau du domaine (domain level)
if [ -f "${OUTPUT_DIR}/${SAMPLE_NAME}.sylphmpa" ]; then
    echo ""
    echo "Domain-level abundances:" >> ${OUTPUT_DIR}/${SAMPLE_NAME}_stats.txt
    grep "d__" ${OUTPUT_DIR}/${SAMPLE_NAME}.sylphmpa | grep -v "|" >> ${OUTPUT_DIR}/${SAMPLE_NAME}_stats.txt
fi

# ==============================================================================
# RÉSUMÉ DES RÉSULTATS
# ==============================================================================

echo ""
echo "=========================================="
echo "ANALYSIS COMPLETE"
echo "=========================================="
echo "Output directory: ${OUTPUT_DIR}"
echo ""
echo "Generated files:"
echo "  - ${SAMPLE_NAME}.tsv              (sylph genome-level results)"
echo "  - ${SAMPLE_NAME}.sylphmpa         (taxonomic profile)"
echo "  - ${SAMPLE_NAME}_top20.txt        (top 20 genomes)"
echo "  - ${SAMPLE_NAME}_stats.txt        (summary statistics)"

if [ "$PROFILING_MODE" = "sketch_first" ]; then
    echo "  - ${FWD_BASENAME}.paired.sylsp    (sketch file - reusable)"
fi

echo ""
echo "End time: $(date)"
echo "=========================================="

# Afficher un aperçu des résultats
echo ""
echo "Preview of genome-level results (top 10):"
head -11 ${PROFILE_OUTPUT}

echo ""
echo "Preview of taxonomic profile (top 20 lines):"
if [ -f "${OUTPUT_DIR}/${SAMPLE_NAME}.sylphmpa" ]; then
    head -20 ${OUTPUT_DIR}/${SAMPLE_NAME}.sylphmpa
fi

exit 0