#!/bin/env python3
#SBATH --qos=p71474_0096
#SBATCH --job-name=test_dynamite
#SBATCH -N 1
#SBATCH --mem-per-cpu=10
#SBATCH --output=dynamite_output.log
#SBATCH --error=dynamite_error.log

# new in config file - multiprocessing_settings: ncpus
# set this either to an integer or to 'all_available'

# to submit this locally, run ``python test_slurm.py``
# to submit this on cluster with slurm run ``sbatch test_slurm.py``

import time
import numpy as np
import matplotlib.pyplot as plt

import os
import shutil

import dynamite as dyn

def run_user_test(stat_mode=False):

    print('Using DYNAMITE version:', dyn.__version__)
    print('Located at:', dyn.__path__)

    # read configuration
    fname = 'test_slurm_config.yaml'
    c = dyn.config_reader.Configuration(fname, silent=True)

    io_settings = c.settings.io_settings
    outdir = io_settings['output_directory']
    # delete previous output if available
    models_folder = outdir + 'models/'
    models_file = outdir + io_settings['all_models_file']
    shutil.rmtree(models_folder, ignore_errors=True)
    if os.path.isfile(models_file):
        os.remove(models_file)
    plotdir = outdir + 'plots/'
    if not os.path.isdir(plotdir):
        os.mkdir(plotdir)
    plotfile = plotdir + 'slurm_model_timings.png'
    if os.path.isfile(plotfile):
        os.remove(plotfile)

    # re-read configuration now that old output has been deleted
    fname = 'test_slurm_config.yaml'
    c = dyn.config_reader.Configuration(fname, silent=True)

    # "run" the models
    t = time.perf_counter()
    smi = dyn.model_iterator.ModelIterator(
        system=c.system,
        all_models=c.all_models,
        settings=c.settings,
        ncpus=c.settings.multiprocessing_settings['ncpus'])
    delt = time.perf_counter()-t
    print(f'Computation time: {delt} seconds = {delt/60} minutes')

    # print all model results
    fig, ax = plt.subplots(2, 1, sharex=True, figsize=(6,4))
    ax[0].plot(c.all_models.table['which_iter'], '.')
    ax[1].plot(c.all_models.table['time_modified'], '.')
    ax[1].set_xlabel('model ID')
    ax[0].set_ylabel('Iteration')
    ax[1].set_ylabel('time modified')
    ax[0].set_ylabel('Iteration')
    fig.tight_layout()
    fig.subplots_adjust(hspace=0)
    fig.savefig(plotfile, dpi=300)
    plt.close()

    # print all model results
    print(f'Look at {plotfile}')
    c.all_models.table.pprint(max_lines=-1, max_width=-1)

    return

if __name__ == '__main__':
    run_user_test()

# end
