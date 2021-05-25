import logging
import subprocess
import sys
import numpy as np
import os
import scipy.integrate
from scipy.special import erf
from scipy.interpolate import UnivariateSpline
from copy import deepcopy
import matplotlib as mpl
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt
from plotbin import sauron_colormap as pb_sauron_colormap
from plotbin import display_pixels
# from loess.loess_2d import loess_2d
from dynamite import kinematics
from dynamite import weight_solvers
from dynamite import physical_system as physys

class Plotter():
    """Class to hold plotting routines

    Class containing methods for plotting results. Each plotting method saves a
    plot in the `outplot/plots` directory, and returns a `matplotlib` `figure`
    object.

    Parameters
    ----------
    system : a `dyn.physical_system.System` object
    settings : a `dyn.config_reader.Settings` object
    parspace : a list of `dyn.parameter_space.Parameter` object
    all_models : a list of `dyn.models.AllModels` object

    """
    def __init__(self,
                 system=None,
                 settings=None,
                 parspace=None,
                 all_models=None):
        self.logger = logging.getLogger(f'{__name__}.{__class__.__name__}')
        self.system = system
        self.settings = settings
        self.parspace = parspace
        self.all_models = all_models
        self.input_directory = settings.io_settings['input_directory']
        self.plotdir = settings.io_settings['plot_directory']
        pb_sauron_colormap.register_sauron_colormap()


    def make_chi2_vs_model_id_plot(self, which_chi2=None, figtype=None):
        """
        Generates a (kin)chi2 vs. model id plot

        Parameters
        ----------
        which_chi2 : STR, optional
            Determines whether chi2 or kinchi2 is used. If None, the setting
            in the configuration file's parameter settings is used.
            Must be None, 'chi2', or 'kinchi2'. The default is None.
        figtype : STR, optional
            Determines the file extension to use when saving the figure.
            If None, the default setting is used ('.png').

        Raises
        ------
        ValueError
            If which_chi2 is not one of None, 'chi2', or 'kinchi2'.

        Returns
        -------
        fig : matplotlib.pyplot.figure
            Figure instance.

        """
        if figtype == None:
            figtype = '.png'
        if which_chi2==None:
            which_chi2 = self.settings.parameter_space_settings['which_chi2']
        if which_chi2 not in ('chi2', 'kinchi2'):
            text = 'which_chi2 needs to be chi2 or kinchi2, ' \
                   f'but it is {which_chi2}'
            self.logger.error(text)
            raise ValueError(text)
        n_models = len(self.all_models.table)
        fig = plt.figure()
        plt.plot([i for i in range(n_models)],
                  self.all_models.table[which_chi2],
                  'rx')
        plt.gca().set_title(f'{which_chi2} vs. model id')
        plt.xlabel('model id')
        plt.ylabel(which_chi2)
        fig.gca().xaxis.set_major_locator(MaxNLocator(integer=True))
        self.logger.info(f'{which_chi2} vs. model id plot created '
                         f'({n_models} models).')

        figname = self.plotdir + which_chi2 + '_progress_plot' + figtype
        fig.savefig(figname)
        self.logger.info(f'Plot {figname} saved in {self.plotdir}')

        return fig

    def make_chi2_plot(self, which_chi2=None, n_excl=0, figtype=None):
        """
        Generates a chisquare plot

        The models generated are shown on a grid of parameter space.
        The best-fit model is marked with a black cross.
        The coloured circles represent models within 3 sigma
        confidence level (light colours and larger circles
        indicate smaller values of the chisquare). The small
        black dots indicate the models outside this confidence region.

        Parameters
        ----------
        which_chi2 : STR, optional
            Determines whether chi2 or kinchi2 is used. If None, the setting
            in the configuration file's parameter settings is used.
            Must be None, 'chi2', or 'kinchi2'. The default is None.
        nexcl : integer, optional
            Determines how many models (in the initial burn-in phase of
            the fit) to exclude from the plot. Must be an integer number.
            Default is 0 (all models are shown). Use this with caution!
        figtype : STR, optional
            Determines the file extension to use when saving the figure.
            If None, the default setting is used ('.png').

        Raises
        ------
        ValueError
            If which_chi2 is not one of None, 'chi2', or 'kinchi2'.

        Returns
        -------
        fig : matplotlib.pyplot.figure
            Figure instance.

        """

        if figtype == None:
            figtype = '.png'

        if which_chi2==None:
            which_chi2 = self.settings.parameter_space_settings['which_chi2']
        if which_chi2 not in ('chi2', 'kinchi2'):
            text = 'which_chi2 needs to be chi2 or kinchi2, ' \
                   f'but it is {which_chi2}'
            self.logger.error(text)
            raise ValueError(text)
        self.logger.info(f'Making chi2 plot scaled according to {which_chi2}')

        pars = self.parspace
        val = deepcopy(self.all_models.table)

        # exclude the first 50, 100 (specified by the user)
        # models in case the values were really off there
        # (or alternatively based on too big Delta chi2)
        val = val[n_excl:]

        #only use models that are finished
        val=val[val['all_done']==True]

        # add black hole scaling
        scale_factor = np.zeros(len(val))
        for i in range(len(val)):
            chi2val = val[which_chi2][i]
            model_id=np.where(self.all_models.table[which_chi2]==chi2val)[0][0]
            model = self.all_models.get_model_from_row(model_id)
            ml = model.parset['ml']
            ml_orblib = model.get_orblib().get_ml_of_original_orblib()
            scale_factor[i] = np.sqrt(ml/ml_orblib)

        #because of the large parameter range dh properties and black hole are plotted in log
        val['c-dh']=np.log10(val['c-dh'])
        val['f-dh']=np.log10(val['f-dh'])
        val['m-bh']=np.log10(val['m-bh']*scale_factor**2)

        #get number and names of parameters that are not fixed
        nofix_sel=[]
        nofix_name=[]
        nofix_latex=[]

        for i in np.arange(len(pars)):
            if pars[i].fixed==False:

                pars[i].name
                nofix_sel.append(i)
                if pars[i].name == 'ml':
                    nofix_name.insert(0, 'ml')
                    nofix_latex.insert(0, '$Y_{r}$')
                else:
                    nofix_name.append(pars[i].name)
                    nofix_latex.append(pars[i].LaTeX)

        nnofix=len(nofix_sel)

        nf=len(val)

        nGH = self.settings.weight_solver_settings['number_GH']
        stars = \
            self.system.get_component_from_class(physys.TriaxialVisibleComponent)
        Nobs = sum([len(kin.data) for kin in stars.kinematic_data])

        self.logger.info(f'nGH={nGH}, Nobs={Nobs}')

        ## 1 sigma confidence level
        #chlim = np.sqrt(2 * Nobs * nGH)
        chi2pmin=np.min(val[which_chi2])
        chlim = np.sqrt(2 * Nobs * nGH)
        chi2=val[which_chi2]
        chi2t = chi2 - chi2pmin
        chi2 = chi2t[np.argsort(-chi2t)]

        #start of the plotting

        figname = self.plotdir + which_chi2 + '_plot' + figtype

        colormap_orig = mpl.cm.viridis
        colormap = mpl.cm.get_cmap('viridis_r')

        fig = plt.figure(figsize=(10, 10))
        for i in range(0, nnofix - 1):
            for j in range(nnofix-1, i, -1):

                xtit = ''
                ytit = ''

                if i==0 : ytit = nofix_latex[j]
                xtit = nofix_latex[i]

                pltnum = (nnofix-1-j) * (nnofix-1) + i+1
                plt.subplot(nnofix-1, nnofix-1, pltnum)

                plt.plot(val[nofix_name[i]],val[nofix_name[j]], 'D',
                         color='black', markersize=2)
                if j==i+1:
                    plt.xlabel(xtit, fontsize=12)
                else:
                    plt.xticks([])
                if i==0:
                    plt.ylabel(ytit, fontsize=12)
                else:
                    plt.yticks([])
                for k in range(nf - 1, -1, -1):
                    if chi2[k]/chlim<=3: #only significant chi2 values

                        color = colormap(chi2[k]/chlim)
                        # * 240) #colours the significant chi2

                        markersize = 7-(chi2[k]/(3*chlim))
                        #smaller chi2 become bigger :)

                        plt.plot((val[nofix_name[i]])[k],
                                 (val[nofix_name[j]])[k], 'o',
                                 markersize=markersize, color=color)

                    if chi2[k]==0:
                        plt.plot((val[nofix_name[i]])[k],
                                 (val[nofix_name[j]])[k], 'x',
                                 markersize=10, color='k')

        plt.subplots_adjust(hspace=0)
        plt.subplots_adjust(wspace=0)
        axcb = fig.add_axes([0.75, 0.07, 0.2, 0.02])
        cb = mpl.colorbar.ColorbarBase(axcb,
                    cmap=plt.get_cmap('viridis_r'),
                    norm=mpl.colors.Normalize(vmin=0., vmax=3),
                    orientation='horizontal')
        plt.subplots_adjust(top=0.99, right=0.99, bottom=0.07, left=0.1)
        fig.savefig(figname)
        self.logger.info(f'Plot {figname} saved in {self.plotdir}')

        return fig

    def make_contour_plot(self):
        # first version written by sabine, will add in the weekend
        #
        pass

    def plot_kinematic_maps(self, model=None, kin_set=0,
                            cbar_lims='data', figtype=None):
        """
        Generates a kinematic map of a model with v, sigma, h3, h4...

        Maps of the surface brightness, mean line-of-sight velocity,
        velocity dispersion, and higher order Gauss–Hermite moments
        are shown. The first row are data, the second row the best-fit
        model, and the third row the residuals.

        Parameters
        ----------
        model : model, optional
            Determines which model is used for the plot.
            If model = None, the model corresponding to the minimum
            chisquare (so far) is used; the setting in the configuration
            file's parameter settings is used to determine which chisquare
            to consider. The default is None.
        kin_set : integer or 'all'
            Determines which kinematic set to use for the plot.
            The value of this parameter should be the index of the data
            set (e.g. kin_set=0 , kin_set=1). The default is kin_set=0.
            If kin_set='all', several kinematic maps are produced, one
            for each kinematic dataset. A list of (fig,kin_set_name) is
            returned where fig are figure objects and kin_set_name are
            the names of the kinematics sets.
        cbar_lims : STR
            Determines which set of values is used to determine the
            limiting values defining the colorbar used in the plots.
            Accepted values: 'model', 'data', 'combined'.
            The default is 'data'.
        figtype : STR, optional
            Determines the file extension to use when saving the figure.
            If None, the default setting is used ('.png').

        Raises
        ------
        ValueError
            If kin_set is not smaller than the number of kinematic sets.
        ValueError
            If cbar_lims is not one of 'model', 'data', or 'combined'.

        Returns
        -------

        list or `matplotlib.pyplot.figure` 
            if kin_set == 'all', returns `(matplotlib.pyplot.figure, string)`, i.e.
            Figure instances along with kinemtics name or figure instance
            else, returns a `matplotlib.pyplot.figure`

        """
        # Taken from schw_kin.py.

        if figtype == None:
            figtype = '.png'

        stars = \
          self.system.get_component_from_class(physys.TriaxialVisibleComponent)
        n_kin = len(stars.kinematic_data)
        #########################################
        if kin_set == 'all':
            self.logger.info(f'Plotting kinematic maps for {n_kin} kin_sets.')
            figures = []
            for i in range(n_kin):
                fig = self.plot_kinematic_maps(model=model,
                                               kin_set=i,
                                               cbar_lims=cbar_lims)
                figures.append((fig, stars.kinematic_data[i].name))
            return figures # returns a list of (fig,kin_name) tuples
        #########################################
        if kin_set >= n_kin:
            text = f'kin_set must be < {n_kin}, but it is {kin_set}'
            self.logger.error(text)
            raise ValueError(text)
        kin_name = stars.kinematic_data[kin_set].name
        self.logger.info(f'Plotting kinematic maps for kin_set no {kin_set}: '
                         f'{kin_name}')

        if model is None:
            which_chi2 = self.settings.parameter_space_settings['which_chi2']
            models_done = np.where(self.all_models.table['all_done'])
            min_chi2 = min(m[which_chi2]
                           for m in self.all_models.table[models_done])
            t = self.all_models.table.copy(copy_data=True) # deep copy!
            t.add_index(which_chi2)
            model_id = t.loc_indices[min_chi2]
            model = self.all_models.get_model_from_row(model_id)
        # kinem_fname = model.get_model_directory() + 'nn_kinem.out'
        kinem_fname = model.directory + 'nn_kinem.out'

        # currently this only works for GaussHermite's and LegacyWeightSolver
        kin_type = type(stars.kinematic_data[kin_set])
        if kin_type is not kinematics.GaussHermite:
            self.logger.info(f'kinematic maps cannot be plot for {kin_type} - '
                             'only GaussHermite')
            fig = plt.figure(figsize=(27, 12))
            return fig
        weight_solver = model.get_weights()
        ws_type = type(weight_solver)
        if ws_type is not weight_solvers.LegacyWeightSolver:
            self.logger.info('kinematic maps cannot be plot for weight solver '
                             f'{ws_type} - only LegacyWeightSolver')
            fig = plt.figure(figsize=(27, 12))
            return fig

        body_kinem = np.genfromtxt(kinem_fname, skip_header=1)

        first_bin = sum(k.n_apertures for k in stars.kinematic_data[:kin_set])
        n_bins = stars.kinematic_data[kin_set].n_apertures
        body_kinem = body_kinem[first_bin:first_bin+n_bins]
        self.logger.debug(f'kin_set={kin_set}, plotting bins '
                          f'{first_bin} through {first_bin+n_bins-1}')
        # if kin_set==0:
        #     n_bins=stars.kinematic_data[0].n_apertures
        #     body_kinem=body_kinem[0:n_bins,:]
        #     self.logger.info(f'first_bin=0, last_bin={n_bins}')
        # elif kin_set==1:
        #     n_bins1=stars.kinematic_data[0].n_apertures
        #     n_bins2=stars.kinematic_data[1].n_apertures
        #     body_kinem=body_kinem[n_bins1:n_bins1+n_bins2,:]
        #     self.logger.info(f'first_bin={n_bins1}, last_bin={n_bins1+n_bins2}')
        # else:
        #     text = f'kin_set must be 0 or 1, not {kin_set}'
        #     self.logger.error(text)
        #     raise ValueError(text)

        if self.settings.weight_solver_settings['number_GH'] == 2:
            id_num, fluxm, flux, velm, vel, dvel, sigm, sig, dsig = body_kinem.T

            #to not need to change the plotting routine below, higher moments are set to 0
            h3m, h3, dh3, h4m, h4, dh4 = vel*0, vel*0, vel*0+0.4, vel*0, vel*0, vel*0+0.4

        if self.settings.weight_solver_settings['number_GH'] == 4:
            id_num, fluxm, flux, velm, vel, dvel, sigm, sig, dsig, h3m, h3, dh3, h4m, h4, dh4 = body_kinem.T

        if self.settings.weight_solver_settings['number_GH'] == 6:
            id_num, fluxm, flux, velm, vel, dvel, sigm, sig, dsig, h3m, h3, dh3, h4m, h4, dh4, h5m, h5, dh5, h6m, h6, dh6 = body_kinem.T

            #still ToDO: Add the kinematic map plots for h5 and h6

        text = '`cbar_lims` must be one of `model`, `data` or `combined`'
        if not cbar_lims in ['model', 'data', 'combined']:
            self.logger.error(text)
            raise AssertionError(text)
        if cbar_lims=='model':
            vmax = np.max(np.abs(velm))
            smax, smin = np.max(sigm), np.min(sigm)
            h3max, h3min = np.max(h3m), np.min(h3m)
            h4max, h4min = np.max(h4m), np.min(h4m)
        elif cbar_lims=='data':
            vmax = np.max(np.abs(vel))
            smax, smin = np.max(sig), np.min(sig)
            h3max, h3min = np.max(h3), np.min(h3)
            h4max, h4min = np.max(h4), np.min(h4)
            if h4max == h4min:
                h4max, h4min = np.max(h4m), np.min(h4m)
        elif cbar_lims=='combined':
            tmp = np.hstack((velm, vel))
            vmax = np.max(np.abs(tmp))
            tmp = np.hstack((sigm, sig))
            smax, smin = np.max(tmp), np.min(tmp)
            tmp = np.hstack((h3m, h3))
            h3max, h3min = np.max(tmp), np.min(tmp)
            tmp = np.hstack((h4m, h4))
            h4max, h4min = np.max(tmp), np.min(tmp)
        else:
            self.logger.error('unknown choice of `cbar_lims`')

        # Read aperture.dat
        # The angle that is saved in this file is measured counter clock-wise
        # from the galaxy major axis to the X-axis of the input data.

        aperture_fname = stars.kinematic_data[kin_set].aperturefile
        aperture_fname = self.input_directory + aperture_fname

        lines = [line.rstrip('\n').split() for line in open(aperture_fname)]
        minx = np.float(lines[1][0])
        miny = np.float(lines[1][1])
        sx = np.float(lines[2][0])
        sy = np.float(lines[2][1])
        sy = sy + miny
        angle_deg = np.float(lines[3][0])
        nx = np.int(lines[4][0])
        ny = np.int(lines[4][1])
        dx = sx / nx

        self.logger.debug(f"Pixel grid dimension is dx={dx},nx={nx},ny={ny}")
        grid = np.zeros((nx, ny), dtype=int)

        xr = np.arange(nx, dtype=float) * dx + minx + 0.5 * dx
        yc = np.arange(ny, dtype=float) * dx + miny + 0.5 * dx

        xi = np.outer(xr, (yc * 0 + 1))
        xt = xi.T.flatten()
        yi = np.outer((xr * 0 + 1), yc)
        yt = yi.T.flatten()

        self.logger.debug(f'PA: {angle_deg}')
        xi = xt
        yi = yt

        # read bins.dat

        bin_fname = stars.kinematic_data[kin_set].binfile
        bin_fname = self.input_directory + bin_fname
        lines_bins = [line.rstrip('\n').split() for line in open(bin_fname)]
        i = 0
        str_head = []
        i_var = []
        grid = []
        while i < len(lines_bins):
            for x in lines_bins[i]:
                if i == 0:
                    str_head.append(str(x))
                if i == 1:
                    i_var.append(np.int(x))
                if i > 1:
                    grid.append(np.int(x))
            i += 1
        str_head = str(str_head[0])
        i_var = int(i_var[0])
        grid = np.ravel(np.array(grid))

        # bins start counting at 1 in fortran and at 0 in idl:
        grid = grid - 1

        # Only select the pixels that have a bin associated with them.
        s = np.ravel(np.where((grid >= 0)))
        fhist, fbinedge = np.histogram(grid[s], bins=len(flux))
        flux = flux / fhist
        fluxm = fluxm / fhist

        ### plot settings

        minf = min(np.array(list(map(np.log10, flux[grid[s]] / max(flux)))))
        maxf = max(np.array(list(map(np.log10, flux[grid[s]] / max(flux)))))
        minfm = min(np.array(list(map(np.log10, fluxm[grid[s]] / max(fluxm)))))
        maxfm = max(np.array(list(map(np.log10, fluxm[grid[s]] / max(fluxm)))))

        # The galaxy has NOT already rotated with PA to make major axis aligned with x

        figname = self.plotdir + f'kinematic_map_{kin_name}' + figtype

        fig = plt.figure(figsize=(27, 12))
        plt.subplots_adjust(hspace=0.7,
                            wspace=0.01,
                            left=0.01,
                            bottom=0.05,
                            top=0.99,
                            right=0.99)
        sauron_colormap = plt.get_cmap('sauron')
        sauron_r_colormap = plt.get_cmap('sauron_r')
        #colormapname = plt.get_cmap('cmr.ember')

        kw_display_pixels = dict(pixelsize=dx,
                                 angle=angle_deg,
                                 colorbar=True,
                                 nticks=7,
                                 cmap='sauron')
                                 #cmap='cmr.ember')
        x, y = xi[s], yi[s]

        ### PLOT THE REAL DATA
        ax1 = plt.subplot(3, 5, 1)
        c = np.array(list(map(np.log10, flux[grid[s]] / max(flux))))
        display_pixels.display_pixels(x, y, c,
                                          vmin=minf, vmax=maxf,
                                          **kw_display_pixels)
        ax1.set_title('surface brightness (log)',fontsize=20, pad=20)
        ax2 = plt.subplot(3, 5, 2)
        display_pixels.display_pixels(x, y, vel[grid[s]],
                                          vmin=-1.0 * vmax, vmax=vmax,
                                          **kw_display_pixels)
        ax2.set_title('velocity',fontsize=20, pad=20)
        ax3 = plt.subplot(3, 5, 3)
        display_pixels.display_pixels(x, y, sig[grid[s]],
                                          vmin=smin, vmax=smax,
                                          **kw_display_pixels)
        ax3.set_title('velocity dispersion',fontsize=20, pad=20)
        ax4 = plt.subplot(3, 5, 4)
        display_pixels.display_pixels(x, y, h3[grid[s]],
                                          vmin=h3min, vmax=h3max,
                                          **kw_display_pixels)
        ax4.set_title(r'$h_{3}$ moment',fontsize=20, pad=20)
        ax5 = plt.subplot(3, 5, 5)
        display_pixels.display_pixels(x, y, h4[grid[s]],
                                          vmin=h4min, vmax=h4max,
                                          **kw_display_pixels)
        ax5.set_title(r'$h_{4}$ moment',fontsize=20, pad=20)

        ### PLOT THE MODEL DATA
        plt.subplot(3, 5, 6)
        c = np.array(list(map(np.log10, fluxm[grid[s]] / max(fluxm))))
        display_pixels.display_pixels(x, y, c,
                                          vmin=minfm, vmax=maxfm,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 7)
        display_pixels.display_pixels(x, y, velm[grid[s]],
                                          vmin=-1.0 * vmax, vmax=vmax,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 8)
        display_pixels.display_pixels(x, y, sigm[grid[s]],
                                          vmin=smin, vmax=smax,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 9)
        display_pixels.display_pixels(x, y, h3m[grid[s]],
                                          vmin=h3min, vmax=h3max,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 10)
        display_pixels.display_pixels(x, y, h4m[grid[s]],
                                          vmin=h4min, vmax=h4max,
                                          **kw_display_pixels)


        kw_display_pixels = dict(pixelsize=dx,
                                 angle=angle_deg,
                                 colorbar=True,
                                 nticks=7,
                                 cmap='bwr')

        ### PLOT THE ERROR NORMALISED RESIDUALS
        plt.subplot(3, 5, 11)
        c = (fluxm[grid[s]] - flux[grid[s]]) / flux[grid[s]]
        display_pixels.display_pixels(x, y, c,
                                          vmin=-0.05, vmax=0.05,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 12)
        c = (velm[grid[s]] - vel[grid[s]]) / dvel[grid[s]]
        display_pixels.display_pixels(x, y, c,
                                          vmin=-10, vmax=10,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 13)
        c = (sigm[grid[s]] - sig[grid[s]]) / dsig[grid[s]]
        display_pixels.display_pixels(x, y, c,
                                          vmin=-10, vmax=10,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 14)
        c = (h3m[grid[s]] - h3[grid[s]]) / dh3[grid[s]]
        display_pixels.display_pixels(x, y, c,
                                          vmin=-1, vmax=1,
                                          **kw_display_pixels)
        plt.subplot(3, 5, 15)
        c = (h4m[grid[s]] - h4[grid[s]]) / dh4[grid[s]]
        display_pixels.display_pixels(x, y, c,
                                          vmin=-1, vmax=1,
                                          **kw_display_pixels)
        fig.subplots_adjust(left=0.04, wspace=0.3,
                            hspace=0.01, right=0.97)
        kwtext = dict(size=20, ha='center', va='center', rotation=90.)
        fig.text(0.015, 0.83, 'data', **kwtext)
        fig.text(0.015, 0.53, 'model', **kwtext)
        fig.text(0.015, 0.2, 'residual', **kwtext)

        fig.savefig(figname)

        return fig

#############################################################################
######## Routines from schw_mass.py, necessary for mass_plot ################
#############################################################################

    def intg2_trimge_intrmass(self, phi, theta, Fxyparm):

        rr = Fxyparm[4,0]
        den_pot_pc = Fxyparm[0,:]
        sig_pot_pc = Fxyparm[1,:]
        q_pot = Fxyparm[2,:]
        p_pot = Fxyparm[3,:]

        sth = np.sin(theta)
        cth = np.cos(theta)
        sphi = np.sin(phi)
        Qjth = (1 - sth**2) * (1 - sphi)**2 + \
               (1 - sth**2)*(sphi/p_pot)**2 + (sth/q_pot)**2
        arg = (rr/sig_pot_pc) * np.sqrt(Qjth/np.float(2.0))

        intg = np.sqrt(np.pi/np.float(2.0))*erf(arg) - \
               np.sqrt(np.float(2.0))*arg*np.exp(-1.*arg**2)
        res = (np.sum(den_pot_pc*sig_pot_pc**3*intg/Qjth**np.float(1.5),
               dtype=np.float))*cth

        return res

# --------------------------------------------

    def PQ_Limits_l(self, x):

        return np.float(0.0)

# --------------------------------------------

    def PQ_Limits_h(self, x):

        return np.float(np.pi/np.float(2.0))

#############################################################################

    def NFW_getpar(self, mstars=None, cc=None, dmfrac=None):

        #Computes density scale, radial scale and total mass in
        #the NFW profile used in the model.
        #Input parameters: NFW dark matter concentration and fraction,
        #and stellar mass

        grav_const_km = 6.67428e-11*1.98892e30/1e9
        parsec_km = 1.4959787068e8*(648.000e3/np.pi)
        rho_crit = (3.*((7.3000e-5)/parsec_km)**2)/(8.*np.pi*grav_const_km)

        rhoc = (200./3.)*rho_crit*cc**3/(np.log(1.+cc) - cc/(1.+cc))
        rc = (3./(800.*np.pi*rho_crit*cc**3)*dmfrac*mstars)**(1./3.)
        darkmass = (800./3.)*np.pi*rho_crit*(rc*cc)**3

        return rhoc, rc, darkmass

#############################################################################

    def NFW_enclosemass(self, rho=None, Rs=None, R=None):

        #Computes cumulative mass of the NWF dark matter halo
        #Input parameters: density scale  and radial scale, and
        #array of radial positions where to compute the mass.

        M = 4. * np.pi * rho * Rs**3 * (np.log((Rs + R)/Rs) - R/(Rs + R))

        return M

#############################################################################

    def trimge_intrmass(self, r_pc=None, surf_pot_pc=None,
                        sigobs_pot_pc=None, qobs_pot=None,
                        psi_off=None, incl=None):

        theta = incl[0]
        phi = incl[1]
        psi = incl[2]

        pintr, qintr = self.triax_tpp2pqu(theta=theta, phi=phi, psi=psi,
                                          qobs=qobs_pot, psi_off=psi_off,
                                          res=1)[:2]
        p_pot = np.copy(pintr)
        q_pot = np.copy(qintr)
        sig_pot_pc = np.copy(sigobs_pot_pc)
        dens_pot_pc = surf_pot_pc*qobs_pot/(np.sqrt(2.*np.pi)*
                        sig_pot_pc*q_pot*p_pot)

        nr = len(r_pc)
        res=np.zeros(nr)
        ng=len(q_pot)

        for i in range(nr):
            Ri=r_pc[i]

            Fxyparm=np.vstack((dens_pot_pc, sig_pot_pc,q_pot.T,
                               p_pot.T, np.zeros(ng) + Ri))
            mi2=scipy.integrate.dblquad(self.intg2_trimge_intrmass,
                                        0.0, np.pi/2.0,
                                        self.PQ_Limits_l ,self.PQ_Limits_h,
                                        args=[Fxyparm],epsrel=1.00)[0]
            res[i] = mi2*8

        return res

#############################################################################

    def triax_tpp2pqu(self, theta=None, phi=None, psi=None, qobs=None,
                      psi_off=None, res=None):

        res = 1
        theta_view = theta * (np.pi/180.0)
        phi_view = phi * (np.pi/180.0)
        psi_obs = (psi+psi_off) * (np.pi /180.0)

        secth = 1.0/np.cos(theta_view)
        cotph = 1.0/np.tan(  phi_view)

        if abs(np.cos(theta_view)) < 1.0e-6 : res=0
        if abs(np.tan(phi_view  )) < 1.0e-6 : res=0

        delp = 1.0 - qobs**2

        nom1minq2 = delp*(2.0*np.cos(2.0*psi_obs) + np.sin(2.0*psi_obs)*
                    (secth*cotph - np.cos(theta_view) * np.tan(phi_view)))
        nomp2minq2 = delp*(2.0*np.cos(2.0*psi_obs) + np.sin(2.0*psi_obs)*
                     (np.cos(theta_view)*cotph - secth*np.tan(phi_view)))
        denom = 2.0*np.sin(theta_view)**2*(delp*np.cos(psi_obs)*
                (np.cos(psi_obs) + secth*cotph*np.sin(psi_obs)) - 1.0)

        if np.max(np.abs(denom)) < 1.0e-6: res=0

        # These are temporary values of the squared intrinsic axial
        # ratios p^2 and q^2
        qintr = (1.0 - nom1minq2 /denom)
        pintr = (qintr + nomp2minq2/denom)

        # Quick check to see if we are not going to take the sqrt of
        # a negative number.
        if ((np.min(qintr) < 1.0e-6) | (np.min(pintr) <= 1.0e-6)): res = 0

        # intrinsic axial ratios p and q
        qintr = np.sqrt(qintr)
        pintr = np.sqrt(pintr)

        # triaxiality parameter T = (1-p^2)/(1-q^2)
        triaxpar = (1.0-pintr**2)/(1.0-qintr**2)
        if (np.max(triaxpar) > 1.0) : res=0
        if (np.min(triaxpar) < 0.0): res=0

        if (np.max(qintr - pintr) > 0): res=0
        if (np.min(qintr) <= 0.0) : res=0

        if (res == 1):
            pintr2 = pintr
            qintr2 = qintr
            uintr2 = 1./(np.sqrt(qobs/np.sqrt((pintr*np.cos(theta_view))**2 +
                     (qintr*np.sin(theta_view))**2*
                     ((pintr*np.cos(phi_view))**2 + np.sin(phi_view)**2))))

        return  pintr2, qintr2, uintr2

#############################################################################

    def mass_plot(self, which_chi2=None, Rmax_arcs=None, figtype=None):
        """
        Generates cumulative mass plot

        The enclosed mass profiles are shown for the mass-follows-light
        component (red), for the dark matter (blue), and for the sum
        of the two (black). The solid lines correspond to the best-fit
        model, the shaded areas represent 1 sigma uncertainties.
        The mass (in solar units) is plotted here as a function of
        the distancefrom the galactic centre, both in arcsec
        (bottom axis) and in pc (top axis).

        Parameters
        ----------
        which_chi2 : STR, optional
            Determines whether chi2 or kinchi2 is used. If None, the setting
            in the configuration file's parameter settings is used.
            Must be None, 'chi2', or 'kinchi2'. The default is None.
        Rmax_arcs : numerical value
            Determines the upper range of the x-axis. Default value is None.
        figtype : STR, optional
            Determines the file extension to use when saving the figure.
            If None, the default setting is used ('.png').

        Raises
        ------
        ValueError
            If which_chi2 is not one of None, 'chi2', or 'kinchi2'.
        ValueError
            If Rmax_arcs is not set to a numerical value.

        Returns
        -------
        fig : matplotlib.pyplot.figure
            Figure instance.

        """

        # schw_mass.py
        # Chi^2 < chilev =>
        #   normalized chi^2: chi^2/chi2pmin < chlim: sqrt(2*Nobs * NGH)
        # getallnfw_out copied from schw_mass.py in this function!

        if figtype == None:
            figtype = '.png'

        if which_chi2==None:
            which_chi2 = self.settings.parameter_space_settings['which_chi2']
        if which_chi2 not in ('chi2', 'kinchi2'):
            text = 'which_chi2 needs to be chi2 or kinchi2, ' \
                   f'but it is {which_chi2}'
            self.logger.error(text)
            raise ValueError(text)
        self.logger.info(f'Making chi2 plot scaled according to {which_chi2}')

        if Rmax_arcs==None:
            text = f'Rmax_arcs must be a number, but it is {Rmax_arcs}'
            self.logger.error(text)
            raise ValueError(text)

        val = deepcopy(self.all_models.table)
        val.sort(which_chi2)
        chi2pmin = val[which_chi2][0]

        nGH = self.settings.weight_solver_settings['number_GH']
        stars = \
            self.system.get_component_from_class(physys.TriaxialVisibleComponent)
        Nobs = sum([len(kin.data) for kin in stars.kinematic_data])

        chlim = np.sqrt(2 * Nobs * nGH)

        chi2 = val[which_chi2]
        chi2 -= chi2pmin
        chilev = chlim * chi2pmin

        s = np.ravel(np.argsort(chi2))
        chi2=chi2[s]

        # select the models within 1 sigma confidence level
        s=np.ravel(np.where(chi2 <=  np.min(chi2)+chilev))
        n=len(s)
        if n < 3:
            s = np.arange(3, dtype=np.int)
            n = len(s)

        chi2=chi2[s]

        print('Selecting ',n,' models')

        ## Calulate mass profiles
        nm = 200
        R = np.logspace(np.log10(0.01),np.log10(Rmax_arcs*1.2),num = nm)

        ## Setup stellar mass profile calculation
        mgepar = stars.mge_pot.data
        mgeI = mgepar['I']
        mgesigma = mgepar['sigma']
        mgeq = mgepar['q']
        mgePAtwist = mgepar['PA_twist']

        distance = self.all_models.system.distMPc
        arctpc = distance*np.pi/0.648
        sigobs_pc = mgesigma*arctpc
        r_pc = R*arctpc
        parsec_km = 1.4959787068e8*(648.e3/np.pi)
        psi_off = mgePAtwist

        mass = np.zeros((nm,n,3))
        bhm = np.zeros(n)
        mlstellar = np.zeros(n)
        incl_a = np.zeros(n)
        phi_a = np.zeros(n)
        psi_a = np.zeros(n)

        for i in range(n):
            p = val['p-stars'][i]
            q = val['q-stars'][i]
            u = val['u-stars'][i]
            th_view,psi_view,ph_view = \
                physys.TriaxialVisibleComponent.triax_pqu2tpp(stars,p,q,u)
            incl_view = [th_view, ph_view, psi_view]

            ml = val['ml'][i]
            surf_pc = mgeI * ml
            Mstarstot = 2 * np.pi * np.sum(surf_pc * mgeq * sigobs_pc ** 2)
            mstars = self.trimge_intrmass(r_pc=r_pc, surf_pot_pc=surf_pc,
                                sigobs_pot_pc=sigobs_pc, qobs_pot=mgeq,
                                psi_off=psi_off, incl=incl_view)

            dmconc = val['c-dh'][i]
            dmR = val['f-dh'][i]
            rhoc, rc = self.NFW_getpar(mstars=Mstarstot, cc=dmconc,
                                        dmfrac=dmR)[:2]
            mdm = self.NFW_enclosemass(rho=rhoc, Rs=rc, R=r_pc*parsec_km)

            mbh = val['m-bh'][i]

            mass[:,i,0] = mstars
            mass[:,i,1] = mdm
            nm_mbh = np.empty(nm); nm_mbh.fill(mbh)
            mass[:,i,2] = nm_mbh.flatten()
            bhm[i] = mbh
            mlstellar[i] = ml
            incl_a[i] = incl_view[0]
            phi_a[i] = incl_view[1]
            psi_a[i] = incl_view[2]

            np.isfinite(1)

        arctpc = distance *np.pi / 0.648
        mm = np.sum(mass, axis=2)
        maxmass = (int(np.max(mm/10**10.)) + 1.)*10**10.

        '''
        snn = np.ravel(np.where((np.isfinite(phi_a)) & (np.isfinite(psi_a))))
        mmmin = np.min(mm, axis=1)
        mmmax = np.max(mm, axis=1)
        m0min = np.min(mass[:,:,0], axis = 1)
        m0max = np.max(mass[:,:,0], axis = 1)
        m1min = np.min(mass[:,:,1], axis = 1)
        m1max = np.max(mass[:,:,1], axis = 1)

        with open(plotdir + 'cumulative_mass.dat', 'w') as outfile:
            outfile.write(str(distance) + '   # distance\n')
            outfile.write(str(np.average(mlstellar))+'  '+
                          str(np.sqrt(np.var(mlstellar, ddof=1))) +
                          '   # stellar m/l, error\n')
            outfile.write(str(np.average(incl_a[snn]))+' '+
                          str(np.average(phi_a[snn]))+'  '+
                          str(np.average(psi_a[snn]))+'  # incl\n')
            outfile.write(str(np.sqrt(np.var(incl_a[snn], ddof=1)))+'  '+
                          str(np.sqrt(np.var(phi_a[snn], ddof=1)))+'  '+
                          str(np.sqrt(np.var(psi_a[snn], ddof=1)))+
                          ' # incl error\n')
            # mtot, mstellar, mdm
            for i in range(nm):
                outfile.write(("%7.3f" % R[i])+ '  '+("%10.4e" % mm[i,0])+ '  '+
                              ("%10.4e" % mmmin[i]) + '  '+
                              ("%10.4e" % mmmax[i]) + '  '+
                              ("%10.4e" % mass[i,0,0]) + '  '+
                              ("%10.4e" % m0min[i]) + '  '+
                              ("%10.4e" % m0max[i]) + '  '+
                              ("%10.4e" % mass[i,0,1]) + '  '+
                              ("%10.4e" % m1min[i]) + '  '+
                              ("%10.4e" % m1max[i])+ '\n')
        '''

        ## plot in linear scale
        xrange = np.array([0.1, Rmax_arcs])
        yrange = np.array([1.0e6,maxmass])

        filename1 = self.plotdir + 'enclosedmassm_linear' + figtype
        fig = plt.figure(figsize=(5,5))
        #ftit = fig.suptitle(object.upper() + '_enclosedmassm_linear', fontsize=10,fontweight='bold')
        ax = fig.add_subplot(1, 1, 1)
        ax.set_xlim(xrange)
        ax.set_ylim(yrange)
        ax.set_xlabel(r'$R$ [arcsec]', fontsize=9)
        ax.set_ylabel(r'Enclosed Mass [M$_{\odot}$]', fontsize=9)
        ax.tick_params(labelsize=8)

        ax2 = ax.twiny()
        ax2.set_xlim(xrange * arctpc / 1000.0)
        ax2.set_xlabel(r'$r$ [kpc]', fontsize=9)
        ax2.tick_params(labelsize=8)

        ax.plot(R,mm[:,0], '-', color='k', linewidth=2.0,
                label='Total')
        ax.fill_between(R, np.min(mm,axis=1),
                        np.max(mm,axis=1),facecolor='k',alpha=0.1)

        ax.plot(R,mass[:,0,0], '-', color='r', linewidth=2.0,
                label='Mass-follows-Light')
        ax.fill_between(R, np.min(mass[:,:,0],axis=1),
                        np.max(mass[:,:,0],axis=1),facecolor='r',alpha=0.1)

        ax.plot(R,mass[:,0,1], '-', color='b', linewidth=2.0,
                label='Dark Matter')
        ax.fill_between(R, np.min(mass[:,:,1],axis=1),
                        np.max(mass[:,:,1],axis=1),facecolor='b',alpha=0.1)

        ax.legend(loc='upper left', fontsize=8)
        plt.tight_layout()
        plt.savefig(filename1)

        self.logger.info(f'Plot {filename1} saved in {self.plotdir}')

        return fig


#############################################################################
######## Routines from schw_orbit.py, necessary for orbit_plot ##############
#############################################################################

    def readorbclass(self, file=None, nrow=None, ncol=None):

        #read in 'datfil/orblib.dat_orbclass.out'
        #which stores the information of all the orbits stored in the orbit library

        #norb = nE * nI2 * nI3 * ndithing^3
        #for each orbit, the time averaged values are stored:

        #lx, ly ,lz, r = sum(sqrt( average(r^2) )), Vrms^2 = average(vx^2 + vy^2 + vz^2 + 2vx*vy + 2vxvz + 2vxvy)

        #The file was stored by the fortran code orblib_f.f90 integrator_find_orbtype

        data=[]
        lines = [line.rstrip('\n').split() for line in open(file)]
        i = 0
        while i < len(lines):
            for x in lines[i]:
                data.append(np.double(x))
            i += 1
        data=np.array(data)
        data=data.reshape((int(5),int(ncol),int(nrow)), order='F')
        return data

#############################################################################

    def readorbout(self, filename=None):

        #read in 'mlxxx/nn_orb.out' of one model

        nrow=data=np.genfromtxt(filename,max_rows=1)
        nrow=int(nrow)
        data=np.genfromtxt(filename, skip_header=1,max_rows=nrow)
        n=np.array(data[:,0],dtype=int)
        ener=np.array(data[:,1],dtype=int)
        i2=np.array(data[:,2],dtype=int)
        i3=np.array(data[:,3],dtype=int)
        regul=np.array(data[:,4],dtype=np.float)
        orbtype=np.array(data[:,5],dtype=np.float)
        orbw=np.array(data[:,6],dtype=np.float)
        lcut=np.array(data[:,7],dtype=np.float)
        ntot=int(nrow)
        return n, ener,i2, i3, regul, orbtype,orbw,lcut,ntot

#############################################################################

    def triaxreadparameters(self, w_dir=None):

        #read in all the parameters in parameters.in

        filename = w_dir + 'infil/parameters_pot.in'

        header = np.genfromtxt(filename, max_rows=1)
        #nmge = int(header[0])  # MGE gaussians
        nmge = int(header)  # MGE gaussians
        mgepar = np.genfromtxt(filename, max_rows=nmge, skip_header=1)
        mgepar = mgepar.T  # MGE parameters

        distance = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 1)
        distance = np.double(distance)  # distance [Mpc]

        view_ang = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 2)
        th_view = np.double(view_ang[0])
        ph_view = np.double(view_ang[1])
        psi_view = np.double(view_ang[2])

        ml = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 3)
        ml = np.double(ml)  # M/L [M_sun/L-sun]

        bhmass = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 4)
        bhmass = np.double(bhmass)  # BH mass [M_sun]

        softlen = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 5)
        softlen = np.double(softlen)  # softening length

        nrell = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 6)
        nre = np.double(nrell[0])
        lrmin = np.double(nrell[1])
        lrmax = np.double(nrell[2])  # E, minmax log(r) [arcsec]

        nrth = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 7)
        nrth = np.int(nrth)  # theta [# I2]

        nrrad = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 8)
        nrrad = np.int(nrrad)  # phi [# I3]

        ndither = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 9)
        ndither = np.int(ndither)  # dithering dimension

        vv1 = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 10)
        vv1_1 = np.int(vv1[0])
        vv1_2 = np.int(vv1[1])

        dmm = np.genfromtxt(filename, max_rows=1, skip_header=nmge + 11)
        dm1 = np.double(dmm[0])
        dm2 = np.double(dmm[1])

        conversion_factor = distance*1.0e6*1.49598e8
        grav_const_km = 6.67428e-11*1.98892e30/1e9
        parsec_km = 1.4959787068e8*(648.000e3/np.pi)
        rho_crit = (3.0*((7.3000e-5)/parsec_km)**2)/(8.0*np.pi*grav_const_km)

        return mgepar, distance, th_view, ph_view, psi_view, ml, \
            bhmass,softlen, nre, lrmin, lrmax, nrth, nrrad, \
            ndither, vv1_1, vv1_2,dm1, dm2, conversion_factor, \
            grav_const_km, parsec_km, rho_crit

#############################################################################

    def orbit_plot(self, model=None, Rmax_arcs=None, figtype =None):
        """
        Generates an orbit plot for the selected model

        This plot shows the stellar orbit distribution, described
        as probability density of orbits; circularity (lambda_z) is
        represented here as a function of the distance from the
        galactic centre r (in arcsec).

        Parameters
        ----------
        model : model, optional
            Determines which model is used for the plot.
            If model = None, the model corresponding to the minimum
            chisquare (so far) is used; the setting in the configuration
            file's parameter settings is used to determine which chisquare
            to consider. The default is None.
        Rmax_arcs : numerical value
             upper radial limit for orbit selection, in arcsec i.e only orbits
             extending up to Rmax_arcs are plotted
        figtype : STR, optional
            Determines the file extension to use when saving the figure.
            If None, the default setting is used ('.png').

        Raises
        ------
        ValueError
            If Rmax_arcs is not set to a numerical value.

        Returns
        -------
        fig : matplotlib.pyplot.figure
            Figure instance.

        """

        # schw_orbit.py

        if figtype == None:
            figtype = '.png'

        if Rmax_arcs==None:
            text = f'Rmax_arcs must be a number, but it is {Rmax_arcs}'
            self.logger.error(text)
            raise ValueError(text)

        if model is None:
            which_chi2 = \
                self.settings.parameter_space_settings['which_chi2']
            models_done = np.where(self.all_models.table['all_done'])
            min_chi2 = min(m[which_chi2]
                           for m in self.all_models.table[models_done])
            t = self.all_models.table.copy(copy_data=True) # deep copy!
            t.add_index(which_chi2)
            model_id = t.loc_indices[min_chi2]
            model = self.all_models.get_model_from_row(model_id)

        mdir = model.get_model_directory()
        mdir_noml = mdir[:mdir[:-1].rindex('/')+1]

        file4 = mdir + 'nn_orb.out'
        file2 = mdir_noml + 'datfil/orblib.dat_orbclass.out'
        file3 = mdir_noml + 'datfil/orblibbox.dat_orbclass.out'
        file3_test = os.path.isfile(file3)
        if not file3_test: file3= '%s' % file2

        xrange=[0.0,Rmax_arcs]

        triaxreadparameters = self.triaxreadparameters(w_dir=mdir_noml)
        #distance = triaxreadparameters[1]
        nre = triaxreadparameters[8]
        nrth, nrrad, ndither = triaxreadparameters[11:14]
        conversion_factor = triaxreadparameters[18]

        #mgepar, distance, th_view, ph_view, psi_view, ml, bhmass,\
        #softlen,nre, lrmin, lrmax, nrth, nrrad, ndither, vv1_1, \
        #vv1_2,dm1,dm2,conversion_factor,grav_const_km,parsec_km, \
        #rho_crit = self.triaxreadparameters(w_dir=mdir_noml)

        norb = int(nre*nrth*nrrad)
        orbclass1 = self.readorbclass(file=file2, nrow=norb, ncol=ndither**3)
        orbclass2 = self.readorbclass(file=file3, nrow=norb, ncol=ndither**3)

        # norbout, ener, i2, i3, regul, orbtype, orbw, lcut, ntot = self.readorbout(filename=file4)
        orbw = self.readorbout(filename=file4)[6]

        orbclass=np.dstack((orbclass1,orbclass1,orbclass2))
        orbclass1a=np.copy(orbclass1)
        orbclass1a[0:3,:,:] *= -1     # the reverse rotating orbits of orbclass

        for i in range(int(0), norb):
            orbclass[:,:,i*2]=orbclass1[:, :, i]
            orbclass[:,:,i*2 + 1]=orbclass1a[:, :, i]

        ## define circularity of each orbit [nditcher^3, norb]
        lz = (orbclass[2,:,:]/orbclass[3,:,:]/np.sqrt(orbclass[4,:,:]))   # lambda_z = lz/(r * Vrms)
        # lx = (orbclass[0,:,:]/orbclass[3,:,:]/np.sqrt(orbclass[4,:,:]))   # lambda_x = lx/(r * Vrms)
        # l= (np.sqrt(np.sum(orbclass[0:3,:,:]**2, axis=0))/orbclass[3,:,:]/np.sqrt(orbclass[4,:,:]))
        r = (orbclass[3,:,:]/conversion_factor)   # from km to kpc

        # average values for the orbits in the same bundle (ndither^3).
        # Only include the orbits within Rmax_arcs
        rm=np.sum(orbclass[3,:,:] / conversion_factor, axis=0)/ndither**3
        s=np.ravel(np.where((rm > xrange[0]) & (rm < xrange[1])))

        # flip the sign of lz to confirm total(lz) > 0
        t=np.ravel(np.argsort(rm))
        yy=np.max(np.ravel(np.where(np.cumsum(orbw[t]) <= 0.5)))
        k = t[0:yy]
        if np.sum(np.sum(lz[:,k], axis=0)/(ndither**3)*orbw[k]) < 0:
            lz *= -1.

        # Make the figure
        nxbin = 7
        nybin = 21

        f1=r[:,s]
        f2=lz[:,s]
        xnbin=nxbin
        ynbin=nybin
        xbinned = [np.min(f1), np.max(f1)]
        # ybinned = [np.min(f2), np.max(f2)]
        ybinned = [-1.00000, 1.0000]
        nbins = np.array([xnbin, ynbin])
        range_bin=[[np.min(f1),np.max(f1)],[np.min(f2),np.max(f2)]]
        R = np.zeros((xnbin, ynbin))

        weight=orbw[s]

        for i in range(int(0), len(f1[0, :])):
            # RIL, xedges, yedges = np.histogram2d(f1[:,i], f2[:,i], bins=nbins, range=range_bin)
            RIL = np.histogram2d(f1[:,i], f2[:,i], bins=nbins,
                                 range=range_bin)[0]
            R += weight[i]*RIL

        R = R/np.sum(R)
        minmaxdens = [np.min(R), np.max(R)]

        ### plot the orbit distribution on lambda_z vs. r ###

        filename5 = self.plotdir + 'orbit_linear_only' + figtype
        imgxrange = xbinned
        imgyrange = ybinned
        extent = [imgxrange[0], imgxrange[1], imgyrange[0], imgyrange[1]]

        fig = plt.figure(figsize=(6,5))

        ax = fig.add_subplot(1, 1, 1)
        cax = ax.imshow(R.T, cmap='binary', interpolation='spline16',
                        extent=extent, origin='lower', vmax=minmaxdens[1],
                        vmin=minmaxdens[0], aspect='auto')

        ax.set_yticks([-1,-0.5,0,0.5,1])
        ax.set_xlabel(r'$r$ [arcsec]', fontsize=9)
        ax.set_ylabel(r'Circularity $\lambda_{z}$', fontsize=9)

        fig.colorbar(cax, orientation='vertical', pad=0.1)

        ax.plot(imgxrange, np.array([1,1])*0.80, '--', color='black',
                 linewidth=1)
        ax.plot(imgxrange, np.array([1,1])*0.25, '--', color='black',
                 linewidth=1)
        ax.plot(imgxrange, np.array([1,1])*(-0.25), '--', color='black',
                 linewidth=1)
        plt.tight_layout()
        plt.savefig(filename5)

        self.logger.info(f'Plot {filename5} saved in {self.plotdir}')

        # compute total angular momentum
        #angular= np.abs(np.sum((lzm[t[0:y+1]])*orbw[t[0:y+1]])/np.sum(orbw[t[0:y+1]]))
        #lzm = np.sum((lz), axis=0)/ndither **3
        #angular2= np.abs(np.sum((lzm[t[0:y+1]])*orbw[t[0:y+1]])/np.sum(orbw[t[0:y+1]]))

        return fig

#############################################################################
######## Routines from schw_anisotropy.py, necessary for beta_plot ##########
#############################################################################

    def N_car2sph(self, x, y, z, eps=None):

        if not eps: eps=1.0e-10
        R = np.sqrt(x**2 + y**2)
        rr = np.sqrt(x**2 + y**2 + z**2)
        res = np.zeros((3,3),dtype=np.float)
        if (R > eps and rr > eps):
            res[0,0] = x/rr
            res[0,1] = (x*z)/(R*rr)
            res[0,2] = -y/R
            res[1,0] = y/rr
            res[1,1] = (y*z)/(R*rr)
            res[1,2] = x/R
            res[2,0] = z/rr
            res[2,1] = -R/rr
            res[2,2] = 0.0
        return res

#############################################################################

    def car2sph_mu12(self, x, y, z, mu1car, mu2car, eps=None):

        #Conversion from Cartesian to spherical intrinsic moments
        #of first and second order (in first octant with x>0, y>0, and z>0)

        #Conversion from Cartesian to spherical intrinsic moments
        #of first and second order (in first octant with x>0, y>0, and z>0).
        #on input ...
        #x,y,z  = vector of n (Cartesian) coordinates
        #mu1car = (n x 3)-array with first Cartesian moments
        #mu2car = (n x 3 x 3)-array with second Cartesian moments
        #on output
        #mu1sph = (n x 3)-array with first spherical moments
        #mu2sph = (n x 3 x 3)-array with second spherical moments
        #              | mu_x |                    | <mu_xx> <mu_xy> <mu_xz> |
        #mu1car[i,*] = | mu_y |,   mu2car[i,*,*] = | <mu_yx> <mu_yy> <mu_yz> |
        #              | mu_z |                    | <mu_zx> <mu_zy> <mu_zz> |
        #idem for spherical but with (x,y,z) -> (r,theta,phi)

        if not eps: eps=1.0e-10
        nn=len(x)
        # print(nn)
        mu1sph=np.zeros((nn,3), dtype=np.float)
        mu2sph=np.zeros((nn,3,3), dtype=np.float)
        for i in range(nn):
            # conversion matrix N = N[k,j], where j=row, k=column
            N = self.N_car2sph(x[i], y[i], z[i], eps=eps)
            # first moment
            mu1sph[i, :] = np.matmul(mu1car[i,:],N)
            # second moment
            for j in range(3):           # rows
                for k in range(3):        # columns
                    mu2sph[i,k,j]= np.sum(np.outer(N[:,k],N[:,j])* \
                                   np.reshape(mu2car[i,:,:],(3,3),order='F'))
        return mu1sph, mu2sph

#############################################################################

    def N_car2cyl(self, x, y, z, eps=None):

        #Orthogonal velocity conversion matrix: N=[N_ji] (i=row,j=column)
        #Orthogonal velocity conversion matrix: N=[N_ji] (i=row,j=column)
        #<v>=N<u>, with <v> spherical and <u> Cartesian
        #from http://en.wikipedia.org/wiki/List_of_canonical_coordinate_transformations

        if not eps: eps=1.0e-10
        R2 = x**2 + y**2
        R=np.sqrt(R2)
        res = np.zeros((3,3),dtype=np.float)
        if (R > eps and R2 > eps):
            res[0,0] = x/R
            res[0,1] = -y/R
            res[0,2] = 0.0
            res[1,0] = y/R
            res[1,1] = x/R
            res[1,2] = 0.0
            res[2,0] = 0.0
            res[2,1] = 0.0
            res[2,2] = 1.0
        return res

#############################################################################

    def car2cyl_mu12(self, x, y, z, mu1car, mu2car, eps=None):

        #Conversion from Cartesian to cylindrical intrinsic moments of first
        #and second order (in first octant with x>0, y>0, and z>0)

        #Conversion from Cartesian to cylindrical intrinsic moments
        #of first and second order (in first octant with x>0, y>0, and z>0)

        if not eps: eps=1.0e-10
        nn=len(x)
        # print(nn)
        mu1sph=np.zeros((nn,3), dtype=np.float)
        mu2sph=np.zeros((nn,3,3), dtype=np.float)
        for i in range(nn):
            # conversion matrix N = N[k,j], where j=row, k=column
            N = self.N_car2cyl(x[i], y[i], z[i], eps=eps)
            # first moment
            mu1sph[i,:] = np.matmul(mu1car[i,:],N)
            # second moment
            for j in range(3):           # rows
                for k in range(3):        # columns
                    mu2sph[i,k,j]= np.sum(np.outer(N[:,k],N[:,j])* \
                                   np.reshape(mu2car[i,:,:],(3,3),order='F'))
        return mu1sph, mu2sph

#############################################################################

    def anisotropy_single(self, file=None):

        # intrinsic moments
        #"iph,ith,ir,ma,mm,me,x,y,z (in arcsec),vx,vy,vz,xv2,vy2 ,vz2,vxvy,vyvz,vzvx,OL,OS,OB"
        # 0   1   2  3  4  5  6 7 8             9  10 11 12  13  14  15   16   17   18,19,20

        filename_moments = file
        mom_par1 = np.genfromtxt(filename_moments, max_rows=1, skip_header=1)
        nmom, nph, nth, nrr = mom_par1.T
        nmom = int(nmom)
        nph = int(nph)
        nth = int(nth)
        nrr = int(nrr)
        if nmom != 16: sys.exit('made for 16 moments')

        ntot = nph*nth*nrr
        phf = np.genfromtxt(filename_moments, max_rows=1, skip_header=3)
        phf = phf.T
        thf = np.genfromtxt(filename_moments, max_rows=1, skip_header=5)
        thf = thf.T
        rrf = np.genfromtxt(filename_moments, max_rows=1, skip_header=7)
        rrf = rrf.T
        data = np.genfromtxt(filename_moments, max_rows=ntot, skip_header=10)

        x = data[:,6]
        y = data[:,7]
        z = data[:,8]
        r = np.sqrt(x**2 + y**2 + z**2)
        Bigr = np.sqrt(x**2 + y**2)

        v1car = data[:,9:12]           #; <v_t> t=x,y,z [(km/s)]
        dum = data[:,[12,15,17,15,13,16,17,16,14]]
        v2car = np.reshape(dum[:,:], (ntot,3,3), order='F')  # < v_s * v_t > s, t = x, y, z[(km / s) ^ 2]
        # v1sph, v2sph = self.car2sph_mu12(x, y, z, v1car, v2car)  # (v_r, v_phi, v_theta)
        v2sph = self.car2sph_mu12(x, y, z, v1car, v2car)[1]  # (v_r, v_phi, v_theta)
        orot = 1 - (0.5*(v2sph[:,1,1] + v2sph[:,2,2]))/(v2sph[:,0,0])
        rr = np.sum(np.sum(np.reshape(r,(nrr,nth,nph),order='F'),
                    axis=2), axis=1)/(nth*nph)
        TM = np.sum(np.sum(np.reshape(data[:,4],(nrr,nth,nph),order='F'),
                    axis=2), axis=1)
        orotR = np.sum(np.sum(np.reshape(orot*data[:,4],(nrr,nth,nph),
                    order='F'), axis=2), axis=1)/TM

        v1cyl, v2cyl = self.car2cyl_mu12(x, y, z, v1car, v2car)        # (v_R, v_phi, v_z)
        vrr = v2cyl[:,0,0]
        vpp = v2cyl[:,1,1]
        vzz = v2cyl[:,2,2]
        vp = v1cyl[:,1]
        nbins = 14
        Bint = 2**(np.arange(nbins+1, dtype=np.float)/2.5) - 1.0
        Rad = np.zeros(nbins, dtype=np.float)
        vrr_r = np.zeros(nbins, dtype=np.float)
        vpp_r = np.zeros(nbins, dtype=np.float)
        vzz_r = np.zeros(nbins, dtype=np.float)
        vp_r = np.zeros(nbins, dtype=np.float)
        d = data[:,4]
        ### Bin along bigR
        for i in range(nbins):
            ss=np.ravel(np.where((Bigr > Bint[i]) & \
                        (Bigr < Bint[i+1]) & (np.abs(z) < 5.0)))
                        # restrict to the disk plane with |z| < 5 arcsec
            nss=len(ss)
            if nss > 0:
                Rad[i] = np.average(Bigr[ss])
                vrr_r[i] = np.sum(vrr[ss]*d[ss])/np.sum(d[ss])
                vpp_r[i] = np.sum(vpp[ss]*d[ss])/np.sum(d[ss])
                vzz_r[i] = np.sum(vzz[ss]*d[ss])/np.sum(d[ss])
                vp_r[i] = np.sum(vp[ss]*d[ss])/np.sum(d[ss])

        return rr, orotR, Rad, vzz_r, vrr_r, vpp_r, vp_r

#############################################################################

    def beta_plot(self, which_chi2=None, Rmax_arcs=None, figtype =None):
        """
        Generates anisotropy plots

        The two plots show the intrinsic and projected anisotropy
        (beta_r and beta_z, respectively) as a function of the
        distance from the galactic centre (in arcsec).

        - beta_r = 1 - (sigma_t/sigma_r)^2
        - beta_z = 1 - (sigma_z/sigma_R)^2

        Solid lines and shaded areas represent the mean and standard
        deviation of the anisotropy of models having parameters in a
        confidence region around the minimum chisquare.

        Parameters
        ----------
        which_chi2 : STR, optional
            Determines whether chi2 or kinchi2 is used. If None, the setting
            in the configuration file's parameter settings is used.
            Must be None, 'chi2', or 'kinchi2'. The default is None.
        Rmax_arcs : numerical value
            Determines the upper range of the x-axis.
        figtype : STR, optional
            Determines the file extension to use when saving the figure.
            If None, the default setting is used ('.png').

        Raises
        ------
        ValueError
            If which_chi2 is not one of None, 'chi2', or 'kinchi2'.
        ValueError
            If Rmax_arcs is not set to a numerical value.

        Returns
        -------
        fig1 : matplotlib.pyplot.figure
            Figure instance.
        fig2 : matplotlib.pyplot.figure
            Figure instance.

        """

        # schw_anisotropy.py

        if figtype == None:
            figtype = '.png'

        if which_chi2==None:
            which_chi2 = self.settings.parameter_space_settings['which_chi2']
        if which_chi2 not in ('chi2', 'kinchi2'):
            text = 'which_chi2 needs to be chi2 or kinchi2, ' \
                   f'but it is {which_chi2}'
            self.logger.error(text)
            raise ValueError(text)
        self.logger.info(f'Making chi2 plot scaled according to {which_chi2}')

        if Rmax_arcs==None:
            text = f'Rmax_arcs must be a number, but it is {Rmax_arcs}'
            self.logger.error(text)
            raise ValueError(text)

        val = deepcopy(self.all_models.table)
        arg = np.argsort(np.array(val[which_chi2]))
        val.sort(which_chi2)
        chi2pmin = val[which_chi2][0]

        nGH = self.settings.weight_solver_settings['number_GH']
        stars = \
            self.system.get_component_from_class(physys.TriaxialVisibleComponent)
        Nobs = sum([len(kin.data) for kin in stars.kinematic_data])

        chlim = np.sqrt(2*Nobs*nGH)

        chi2 = val[which_chi2]
        chi2 -= chi2pmin
        chilev = chlim * chi2pmin

        s = np.ravel(np.argsort(chi2))
        chi2=chi2[s]

        # select the models within 1 sigma confidence level
        s=np.ravel(np.where(chi2 <=  np.min(chi2)+chilev))
        n=len(s)
        if n < 3:
            s = np.arange(3, dtype=np.int)
            n = len(s)

        chi2=chi2[s]

        RRn = np.zeros((100,n), dtype=np.float)
        orotn = np.zeros((100,n), dtype=np.float)
        RRnz = np.zeros((100,n), dtype=np.float)
        orotnz = np.zeros((100,n), dtype=np.float)
        Vz2 = np.zeros((100,n), dtype=np.float)
        VR2 = np.zeros((100,n), dtype=np.float)
        Vp2= np.zeros((100,n), dtype=np.float)
        Vp = np.zeros((100,n), dtype=np.float)

        for i in range(n):
            model_id = arg[i]
            model = self.all_models.get_model_from_row(model_id)
            mdir = model.get_model_directory()

            filei = mdir + 'nn_intrinsic_moments.out'

            rr, orotR, Rad, vzz_r, vrr_r, vpp_r, \
                vp_r = self.anisotropy_single(file=filei)
            nrr = len(rr)
            RRn[0:nrr,i] = rr
            orotn[0:nrr,i] = orotR

            nrad = len(Rad)
            RRnz[0:nrad,i] = Rad
            ratio = np.zeros(nrad)
            ratio[np.where(Rad>0)] = \
                vzz_r[np.where(Rad>0)]/vrr_r[np.where(Rad>0)]
            orotnz[0:nrad,i] = 1. - ratio # vzz_r/vrr_r
            Vz2[0:nrad,i] = vzz_r
            VR2[0:nrad,i] = vrr_r
            Vp2[0:nrad,i] = vpp_r
            Vp[0:nrad,i] = vp_r

        filename1 = self.plotdir + 'anisotropy_var' + figtype
        filename2 = self.plotdir + 'betaz_var' + figtype

        RRn_m = np.zeros(nrr, dtype=np.float)
        RRn_e = np.zeros(nrr, dtype=np.float)
        orot_m2 = np.zeros(nrr, dtype=np.float)
        orot_e2 = np.zeros(nrr, dtype=np.float)
        for j in range(0, nrr):
            RRn_m[j] = np.average(RRn[j,:])
            RRn_e[j] = np.sqrt(np.var(RRn[j,:], ddof=1))
            orot_m2[j] = np.average(orotn[j,:])
            orot_e2[j] = np.sqrt(np.var(orotn[j,:], ddof=1))

        radialrange=np.array([np.min(rr),Rmax_arcs])
        yrange=np.array([-1,1])

        fig1 = plt.figure(figsize=(5,5))
        ax1 = fig1.add_subplot(1,1,1)
        ax1.set_xlim(radialrange)
        yrange=np.array([min(-1,min(orot_m2-orot_e2)),1])
        ax1.set_ylim(yrange)
        if yrange[1]-yrange[0]<=4:
            yticks = np.linspace(int(yrange[0])*1.,
                        int(yrange[1])*1.,int((yrange[1]-yrange[0])/0.5)+1)
        else:
            yticks = np.linspace(int(yrange[0])*1.,
                        int(yrange[1])*1.,int((yrange[1]-yrange[0]))+1)
        ax1.set_yticks(yticks)
        ax1.plot(RRn_m,orot_m2, '-', color='black', linewidth=3.0)
        ax1.fill_between(RRn_m, orot_m2-orot_e2,
                        orot_m2+orot_e2,facecolor='gray',alpha=0.3)
        ax1.set_xlabel(r'$r$ [arcsec]', fontsize=9)
        ax1.set_ylabel(r'$\beta_{\rm r} = 1 - \sigma_{\rm t}^2/\sigma_{\rm r}^2$',
                         fontsize=9)
        ax1.tick_params(labelsize=8)
        ax1.plot(radialrange, [0,0], '--', color='black', linewidth=1.0)
        plt.tight_layout()
        plt.savefig(filename1)

        self.logger.info(f'Figure {filename1} saved in {self.plotdir}')

        fig2 = plt.figure(figsize=(5,5))
        ax = fig2.add_subplot(1,1,1)
        ax.set_xlim([0,Rmax_arcs])
        ax.set_ylim([0,1])
        ax.set_xlabel(r'$R$ [arcsec]', fontsize=9)
        ax.set_ylabel(r'$\beta_{\rm z} = 1 - \sigma_{\rm z}^2/\sigma_{\rm R}^2$',
                         fontsize=9)
        ax.tick_params(labelsize=8)
        RRn_m = np.zeros(nrad, dtype=np.float)
        RRn_e = np.zeros(nrad, dtype=np.float)
        orot_m2 = np.zeros(nrad, dtype=np.float)
        orot_e2 = np.zeros(nrad, dtype=np.float)
        for j in range(0, nrad):
            kk = np.where(orotn[j,:] > 0.0)
            if len(kk[0])>0:
                RRn_m[j] = np.average(RRn[j,kk])
                RRn_e[j] = np.sqrt(np.var(RRn[j,kk], ddof=1))
                orot_m2[j] = np.average(orotn[j,kk])
                orot_e2[j] = np.sqrt(np.var(orotn[j,kk], ddof=1))
            else:
                orot_m2[j] = -1.
        cc = orot_m2 > 0
        Rmaxcc = (int(max(RRn_m[cc])/5) + 1)*5
        ax.set_xlim([0,Rmaxcc])
        ax.plot(RRn_m[cc], orot_m2[cc], '-', color='black', linewidth =3)
        ax.fill_between(RRn_m[cc], orot_m2[cc]-orot_e2[cc],
                        orot_m2[cc]+orot_e2[cc],facecolor='gray',alpha=0.3)
        plt.tight_layout()
        plt.savefig(filename2)

        self.logger.info(f'Figure {filename2} saved in {self.plotdir}')

        return fig1, fig2


#############################################################################
######## Routines from schw_qpu.py, necessary for qpu_plot ##################
#############################################################################

    def enlargeVector(self, old_vec=None, new_length=None):
        old_indices = np.arange(0, len(old_vec))
        new_indices = np.linspace(0, len(old_vec)-1, new_length)
        spl = UnivariateSpline(old_indices, old_vec, k=1, s=0)
        new_vec = spl(new_indices)
        return new_vec

#############################################################################

    def pqintr_mge_v2(self, Rpc=None, surf_pc=None, sigma_pc=None,
                        qobs=None, psi_off=None, incl=None):

        theta = incl[0]
        phi = incl[1]
        psi = incl[2]

        r = np.arange(101, dtype=np.float)/100.0*max(Rpc)*1.02
        n = len(r)

        pintr, qintr, uintr = self.triax_tpp2pqu(theta=theta, phi=phi,
                                                 psi=psi, qobs=qobs,
                                                 psi_off=psi_off, res=1)
        sigintr_pc = sigma_pc/uintr
        sb3 = surf_pc*(2*np.pi*sigma_pc**2*qobs)/ \
              ((sigintr_pc*np.sqrt(2*np.pi))**3*pintr*qintr)
        Sz = np.zeros(n, dtype=np.float)
        Sy = np.zeros(n, dtype=np.float)
        Sx = np.zeros(n, dtype=np.float)

        for i in range(n):
            Sz[i] = np.sum(sb3*np.exp(-(r[i]**2/qintr**2)/(2*sigintr_pc**2))) # SB at z direction
            Sy[i] = np.sum(sb3*np.exp(-(r[i]**2/pintr**2)/(2*sigintr_pc**2))) # SB at y direction
            Sx[i] = np.sum(sb3*np.exp(-(r[i]**2)/(2*sigintr_pc**2))) # SB at x direction

        #### check and replace the enlargeVector function in basic file
        Sya = self.enlargeVector(old_vec=Sy, new_length=n*int(100))
        Sza = self.enlargeVector(old_vec=Sz, new_length=n*int(100))
        Sxa = self.enlargeVector(old_vec=Sx, new_length=n*int(100))
        ra = self.enlargeVector(old_vec=r, new_length=n*int(100))

        pr = np.zeros_like(Rpc)
        qr = np.zeros_like(Rpc)
        for i in range(len(Rpc)):
            k1 = np.digitize(Rpc[i], ra, right=True)
            if ra[k1]>0:
                pr[i] = ra[np.digitize(Sxa[k1], Sya, right=True)]/ra[k1]
                qr[i] = ra[np.digitize(Sxa[k1], Sza, right=True)]/ra[k1]
            else:
                pr[i] = -1.
                qr[i] = -1.
        return pr, qr

#############################################################################

    def qpu_plot(self, which_chi2=None, Rmax_arcs=None,figtype =None):
        """
        Generates triaxiality plot

        The intrinsic flattenings q (C/A) and p (B/A) are shown here,
        with the blue and black lines respectively, as a function of
        the distance from the galactic centre (in arcsec).
        The value of T = (1-p^2)/(1-q^2) is also shown (red line).

        Parameters
        ----------
        which_chi2 : STR, optional
            Determines whether chi2 or kinchi2 is used. If None, the setting
            in the configuration file's parameter settings is used.
            Must be None, 'chi2', or 'kinchi2'. The default is None.
        Rmax_arcs : numerical value
            Determines the upper range of the x-axis.
        figtype : STR, optional
            Determines the file extension to use when saving the figure.
            If None, the default setting is used ('.png').

        Raises
        ------
        ValueError
            If which_chi2 is not one of None, 'chi2', or 'kinchi2'.
        ValueError
            If Rmax_arcs is not set to a numerical value.

        Returns
        -------
        fig : matplotlib.pyplot.figure
            Figure instance.

        """

        # schw_qpu.py

        if figtype == None:
            figtype = '.png'

        if which_chi2==None:
            which_chi2 = self.settings.parameter_space_settings['which_chi2']
        if which_chi2 not in ('chi2', 'kinchi2'):
            text = 'which_chi2 needs to be chi2 or kinchi2, ' \
                   f'but it is {which_chi2}'
            self.logger.error(text)
            raise ValueError(text)
        self.logger.info(f'Making chi2 plot scaled according to {which_chi2}')

        if Rmax_arcs==None:
            text = f'Rmax_arcs must be a number, but it is {Rmax_arcs}'
            self.logger.error(text)
            raise ValueError(text)

        val = deepcopy(self.all_models.table)
        arg = np.argsort(np.array(val[which_chi2]))
        val.sort(which_chi2)
        chi2pmin = val[which_chi2][0]

        nGH = self.settings.weight_solver_settings['number_GH']
        stars = \
            self.system.get_component_from_class(physys.TriaxialVisibleComponent)
        Nobs = sum([len(kin.data) for kin in stars.kinematic_data])

        chlim = np.sqrt(2*Nobs*nGH)

        chi2 = val[which_chi2]
        chi2 -= chi2pmin
        chilev = chlim * chi2pmin

        s = np.ravel(np.argsort(chi2))
        chi2=chi2[s]

        # select the models within 1 sigma confidence level
        s=np.ravel(np.where(chi2 <=  np.min(chi2)+chilev))
        n=len(s)
        if n < 3:
            s = np.arange(3, dtype=np.int)
            n = len(s)
        if n > 100:
            s = np.arange(100, dtype=np.int)
            n = len(s)

        chi2=chi2[s]

        q_all = np.zeros((101,n), dtype=np.float)
        p_all = np.zeros((101,n), dtype=np.float)
        Rarc = np.arange(101, dtype=np.float)/100.0*Rmax_arcs

        for i in range(0, n):
            model_id = arg[i]
            model = self.all_models.get_model_from_row(model_id)
            mdir = model.get_model_directory()
            mdir_noml = mdir[:mdir[:-1].rindex('/')+1]

            #mgepar, distance, th_view, ph_view, psi_view, ml, \
            #bhmass, softlen, nre, lrmin, lrmax, nrth, nrrad, ndither, \
            #vv1_1, vv1_2, dm1, dm2, conversion_factor, grav_const_km, \
            #parsec_km, rho_crit = self.triaxreadparameters(w_dir=mdir_noml)

            mgepar, distance, th_view, ph_view, \
            psi_view = self.triaxreadparameters(w_dir=mdir_noml)[:5]

            arctpc = distance*np.pi/0.648
            Rpc = Rarc*arctpc
            surf_pc = mgepar[0,:]
            sigobs_pc = mgepar[1,:]*arctpc
            qobs = mgepar[2,:]
            p_k, q_k = self.pqintr_mge_v2(Rpc=Rpc, surf_pc=surf_pc, \
                                    sigma_pc=sigobs_pc, qobs=qobs, \
                                    psi_off=mgepar[3,:], \
                                    incl=[th_view, ph_view, psi_view])
            p_all[:,i] = p_k
            q_all[:,i] = q_k

        T_all = np.zeros_like(p_all)
        cond = (p_all>=0)
        T_all[~cond] = -1.
        T_all[cond] = (1. - p_all[cond]**2.)/(1. - q_all[cond]**2.)

        T_m = np.zeros_like(Rpc)
        T_var = np.zeros_like(Rpc)
        p_m = np.zeros_like(Rpc)
        p_var = np.zeros_like(Rpc)
        q_m = np.zeros_like(Rpc)
        q_var = np.zeros_like(Rpc)

        for i in range(101):
            cc = T_all[i,:] > 0.
            if sum(cc)>0:
                p_m[i] = np.average(p_all[i,cc])
                p_var[i] = np.sqrt(np.var(p_all[i,cc],ddof=1))
                q_m[i] = np.average(q_all[i,cc])
                q_var[i] = np.sqrt(np.var(q_all[i,cc],ddof=1))
                T_m[i] = np.average(T_all[i,cc])
                T_var[i] = np.sqrt(np.var(T_all[i,cc],ddof=1))
            else:
                p_m[i] = -1.

        cc = (p_m >= 0)

        filename1 = self.plotdir + 'triaxial_qpt' + figtype
        fig = plt.figure(figsize=(5,5))
        ax = fig.add_subplot(1,1,1)
        ax.set_xlim(np.array([0,Rmax_arcs]))
        ax.set_ylim(np.array([0.0,1.1]))
        #ax.plot(Rpc[cc]/arctpc, q_m[cc], 'x', color='black', markersize=1)
        ax.set_xlabel(r'$r$ [arcsec]', fontsize=9)
        ax.set_ylabel(r'$p$ | $q$ | $T = (1-p^2)/(1-q^2)$', fontsize=9)
        ax.tick_params(labelsize=8)

        ax.plot(Rpc[cc]/arctpc, p_m[cc], '-', color='blue',
                linewidth=3.0, label=r'$p$')
        ax.plot(Rpc[cc]/arctpc, p_m[cc]-p_var[cc], '--',
                color='blue', linewidth=0.8)
        ax.plot(Rpc[cc]/arctpc, p_m[cc]+p_var[cc], '--',
                color='blue', linewidth=0.8)

        ax.plot(Rpc[cc]/arctpc, q_m[cc], '-', color='black',
                linewidth=3.0, label=r'$q$')
        ax.plot(Rpc[cc]/arctpc, q_m[cc]-q_var[cc], '--',
                color='black', linewidth=0.8)
        ax.plot(Rpc[cc]/arctpc, q_m[cc]+q_var[cc], '--',
                color='black', linewidth=0.8)

        ax.plot(Rpc[cc]/arctpc, T_m[cc], '-', color='red',
                linewidth=3.0, label=r'$T$')
        ax.plot(Rpc[cc]/arctpc, T_m[cc]-T_var[cc], '--',
                color='red', linewidth=0.8)
        ax.plot(Rpc[cc]/arctpc, T_m[cc]+T_var[cc], '--',
                color='red', linewidth=0.8)

        ax.legend(loc='upper right', fontsize=8)
        plt.tight_layout()
        plt.savefig(filename1)

        self.logger.info(f'Plot {filename1} saved in {self.plotdir}')

        return fig

    def version_p(self):
        return sys.version.split()[0]

    def version_f(self):
        v = subprocess.run("gfortran --version", capture_output=True, \
            shell=True, check=True).stdout.decode('utf-8'). \
            split(sep='\n')[0].split()[-1]
        return v
