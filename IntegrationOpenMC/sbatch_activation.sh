#!/bin/bash
# Two-step IHX sodium-activation calculation (Step 1 eigenvalue -> Step 2 MAGIC).
# Submit with:  sbatch sbatch_activation.sh
#
#SBATCH --partition=daily          # long partition (Step 1 + Step 2 > 1 h)
#SBATCH --cpus-per-task=128        # = OMP_NUM_THREADS
#SBATCH --ntasks-per-core=1        # no hyper-threading
#SBATCH --time=0-12:00:00
#SBATCH --output=sbatch_activation.log.out
#SBATCH --error=sbatch_activation.log.err

set -e

JSON=homogenised_model_cm20260725_194805.json

# Initialise conda for non-interactive shells and activate the env
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate openmc

# Cross sections (JEFF-3.3, matching the validated core model)
export OPENMC_CROSS_SECTIONS=$HOME/openmc_data/jeff-3.3-hdf5/cross_sections.xml
export OMP_NUM_THREADS=128
export PYTHONUNBUFFERED=1

echo "OPENMC_CROSS_SECTIONS=$OPENMC_CROSS_SECTIONS"
echo "Running on ${SLURM_JOB_CPUS_PER_NODE} cores with ${OMP_NUM_THREADS} threads"

echo "=== STEP 1: k-eigenvalue (converged source) ==="
srun stdbuf -oL -eL python3 -u step1_eigenvalue.py "$JSON"

echo "=== STEP 2: MAGIC weight windows + IHX activation tally ==="
srun stdbuf -oL -eL python3 -u step2_magic.py "$JSON"

echo "=== POST-PROCESSING ==="
python3 -u postprocess.py "$JSON"

echo "Done."
