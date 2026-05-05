#!/bin/bash
#SBATCH --job-name=singlem_profile
#SBATCH --output=singlem_%j.out
#SBATCH --error=singlem_%j.err
#SBATCH --time=1-00:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --partition=fast
#SBATCH --account=YOUR_PROJECT_NAME

# Script SLURM pour profiler des métagénomes avec SingleM
# Base de données: GTDB-226 (pré-installée sur le cluster)

# ==============================================================================
# CONFIGURATION - À MODIFIER SELON VOS BESOINS
# ==============================================================================

# Chemin vers la base de données GTDB-226 (metapackage SingleM)
# Sur IFB, utilisez /shared/bank/ pour les bases publiques ou /shared/projects/ pour votre projet
METAPACKAGE="/shared/bank/singlem/gtdb-r226_metapackage"
# OU si dans votre projet:
# METAPACKAGE="/shared/projects/YOUR_PROJECT_NAME/databases/singlem/gtdb-r226_metapackage"

# Fichiers d'entrée (reads paired-end)
# Utilisez /shared/projects/YOUR_PROJECT_NAME/ pour vos données
FORWARD_READS="/shared/projects/YOUR_PROJECT_NAME/data/sample_R1.fastq.gz"
REVERSE_READS="/shared/projects/YOUR_PROJECT_NAME/data/sample_R2.fastq.gz"

# Nom de l'échantillon (pour les fichiers de sortie)
SAMPLE_NAME="sample01"

# Répertoire de sortie (dans votre espace projet)
OUTPUT_DIR="/shared/projects/YOUR_PROJECT_NAME/results/singlem_output"

# Nombre de threads (doit correspondre à --cpus-per-task)
THREADS=16

# Seuil de couverture minimal pour rapporter un taxon
MIN_COVERAGE=0.35  # 0.35 par défaut pour reads, 0.1 pour génomes

# ==============================================================================
# INITIALISATION
# ==============================================================================

echo "=========================================="
echo "SingleM Taxonomic Profiling"
echo "=========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "Start time: $(date)"
echo "=========================================="

# Créer le répertoire de sortie
mkdir -p ${OUTPUT_DIR}

# Charger le module SingleM (si disponible) ou conda
# Option 1: Si SingleM est disponible comme module
# module load singlem

# Option 2: Si vous utilisez un environnement conda personnel
module load conda
conda activate singlem

# Option 3: Si vous utilisez Apptainer/Singularity
# module load apptainer
# SINGLEM_CONTAINER="/path/to/singlem.sif"

# Vérification que SingleM est disponible
if ! command -v singlem &> /dev/null; then
    echo "ERROR: singlem command not found!"
    echo "Please check your conda environment."
    exit 1
fi

# Afficher la version de SingleM
echo "SingleM version:"
singlem --version

# Vérifier que la base de données existe
if [ ! -d "$METAPACKAGE" ]; then
    echo "ERROR: Metapackage not found at $METAPACKAGE"
    exit 1
fi

echo "Using metapackage: $METAPACKAGE"
echo "=========================================="

# ==============================================================================
# PROFILING AVEC SINGLEM PIPE
# ==============================================================================

echo "Starting SingleM pipe..."
echo "Forward reads: $FORWARD_READS"
echo "Reverse reads: $REVERSE_READS"
echo "Threads: $THREADS"
echo ""

singlem pipe \
    --forward ${FORWARD_READS} \
    --reverse ${REVERSE_READS} \
    --metapackage ${METAPACKAGE} \
    --taxonomic-profile ${OUTPUT_DIR}/${SAMPLE_NAME}.profile.tsv \
    --archive-otu-table ${OUTPUT_DIR}/${SAMPLE_NAME}.archive.otu_table.json.gz \
    --otu-table ${OUTPUT_DIR}/${SAMPLE_NAME}.otu_table.csv \
    --min-taxon-coverage ${MIN_COVERAGE} \
    --threads ${THREADS}

# Vérifier le code de sortie
if [ $? -eq 0 ]; then
    echo "SingleM pipe completed successfully!"
else
    echo "ERROR: SingleM pipe failed!"
    exit 1
fi

# ==============================================================================
# GÉNÉRATION DE VISUALISATIONS ET FORMATS SUPPLÉMENTAIRES
# ==============================================================================

echo ""
echo "Generating additional outputs..."

# 1. Krona chart (visualisation interactive HTML)
echo "Creating Krona chart..."
singlem summarise \
    --input-taxonomic-profile ${OUTPUT_DIR}/${SAMPLE_NAME}.profile.tsv \
    --output-taxonomic-profile-krona ${OUTPUT_DIR}/${SAMPLE_NAME}.krona.html

# 2. Tableau avec informations supplémentaires (full_coverage, relative_abundance)
echo "Creating extended profile..."
singlem summarise \
    --input-taxonomic-profile ${OUTPUT_DIR}/${SAMPLE_NAME}.profile.tsv \
    --output-taxonomic-profile-with-extras ${OUTPUT_DIR}/${SAMPLE_NAME}.with_extras.tsv

# 3. Tableaux d'abondance relative pour tous les rangs taxonomiques
echo "Creating relative abundance tables for all taxonomic levels..."
singlem summarise \
    --input-taxonomic-profile ${OUTPUT_DIR}/${SAMPLE_NAME}.profile.tsv \
    --output-species-by-site-relative-abundance-prefix ${OUTPUT_DIR}/${SAMPLE_NAME}

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
echo "  - ${SAMPLE_NAME}.profile.tsv                  (taxonomic profile)"
echo "  - ${SAMPLE_NAME}.archive.otu_table.json.gz    (archive OTU table)"
echo "  - ${SAMPLE_NAME}.otu_table.csv                (OTU table)"
echo "  - ${SAMPLE_NAME}.krona.html                   (Krona visualization)"
echo "  - ${SAMPLE_NAME}.with_extras.tsv              (extended profile)"
echo "  - ${SAMPLE_NAME}-*.tsv                        (relative abundance tables)"
echo ""
echo "End time: $(date)"
echo "=========================================="

# Afficher un aperçu du profil taxonomique
echo ""
echo "Preview of taxonomic profile (top 20 lines):"
head -20 ${OUTPUT_DIR}/${SAMPLE_NAME}.profile.tsv

exit 0