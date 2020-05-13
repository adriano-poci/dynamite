import numpy as np
from . data import Integrated, Kinematic
from scipy import special, stats


class Histogram(object):
    def __init__(self, xedg, y, normalise=True):
        self.xedg = xedg
        self.x = (xedg[:-1] + xedg[1:])/2.
        self.dx = xedg[1:] - xedg[:-1]
        self.y = y
        if normalise:
            self.normalise()
        else:
            self.normalised = False

    def normalise(self):
        norm = np.sum(self.y*self.dx, axis=-1)
        self.y /= norm
        self.normalised = True


class GauusianMixture1D(object):
    def __init__(self,
                 weights=None,
                 means=None,
                 sigmas=None):
        assert (len(weights)==len(means)) & (len(means)==len(sigmas))
        self.nrm = stats.norm(means, sigmas)
        self.weights = weights

    def evaluate(self, x):
        y = self.weights * self.nrm.pdf(x[:,np.newaxis])
        y = np.sum(y, 1)
        return y


class GaussHermite(Integrated, Kinematic):
    def __init__(self,
                 filename=None):
        self.filename = filename
        if filename is not None:
            self.read_file()

    def read_file(self):
        f = open(self.filename)
        header = f.readline()
        f.close()
        header = header.split()
        n_vbins, n_gh = header
        n_vbins, n_gh = int(n_vbins), int(n_gh)
        self.n_vbins = n_vbins
        self.n_gh = n_gh
        # n_gh read from the file header is currently unused and incorrect
        # TODO: fix/remove it... for now hardcode n_gh = 4
        self.n_gh = 4
        # TODO: move names/dtypes to the file header
        names = ['vbin_id', 'v', 'dv', 'sigma', 'dsigma', 'n_gh']
        for i_gh in range(3, self.n_gh):
            names += ['h{i_gh}', 'dh{i_gh}']
        ncols = len(names)
        dtype = [float for i in range(ncols)]
        dtype[0] = int
        dtype[5] = int
        data = np.genfromtxt(self.filename,
                             skip_header=1,
                             names=names,
                             dtype=dtype)
        # 6th column of kin_data.dat is == (unused and incorrect?) n_gh
        # TODO: remove it
        self.data = data

    def getgauher(self,
                  vm, sg,
                  veltemp, Nvhist, Nvmax, dvhist,
                  hh, Nhermmax, gam, ingam):
        # wrapper to the fortran routine here
        pass

    def get_hermite_polynomial_coeffients(self, max_order=None):
        """Get coeffients for hermite polynomials normalised as in eqn 14 of
        Capellari 2016

        Parameters
        ----------
        max_order : int
            The maximum order hermite polynomial desired

        Returns
        -------
        array (max_order+1, max_order+1)
            coeffients[i,j] = coef of x^j in polynomial of order i

        """
        if max_order is None:
            max_order = self.n_gh
        coeffients = []
        for i in range(0, max_order+1):
            # physicists hermite polynomials
            coef_i = special.hermite(i)
            coef_i = coef_i.coefficients
            # reverse poly1d array so that j'th entry is coeefficient of x^j
            coef_i = coef_i[::-1]
            # scale according to eqn 14 of Capellari 16
            coef_i *= (special.factorial(i) * 2**i)**-0.5
            # fill poly(i) with zeros for 0*x^j for j>i
            coef_i = np.concatenate((coef_i, np.zeros(max_order-i)))
            coeffients += [coef_i]
        coeffients = np.vstack(coeffients)
        return coeffients

    def standardise_velocities(self, v, v_mu, v_sig):
        w = (v - v_mu)/v_sig
        return w

    def evaluate_hermite_polynomials(self, coeffients, w,
                                     standardised=True,
                                     v_mu=None,
                                     v_sig=None):
        """
        Parameters
        ----------
        coeffients : array
            coeffients of hermite polynomials as given by method
            get_hermite_polynomial_coeffients
        w : array
            if standardised==True, standardised velocities,
            else physical velocities and v_mu and v_sig must also be set

        Returns
        -------
        polynomials evaluated at w in array of shape (n_herm_max,) + w.shape

        """
        if not standardised:
            w = self.standardise_velocities(w, v_mu, v_sig)
        n_herm = coeffients.shape[0]
        w_pow_i = np.vstack([w**i for i in range(n_herm)])
        result = np.dot(coeffients, w_pow_i)
        return result

    def evaluate_losvd(self, v, v_mu, v_sig, h):
        w = self.standardise_velocities(v, v_mu, v_sig)
        n_herm = h.shape[0]
        coef = self.get_hermite_polynomial_coeffients(max_order=n_herm-1)
        nrm = stats.norm()
        hpolys = self.evaluate_hermite_polynomials(coef, w)
        losvd = nrm.pdf(w) * np.dot(h, hpolys)
        return losvd

    def get_gh_expansion_coefficients(self,
                                      v_mu=0,
                                      v_sig=1,
                                      vel_hist=None,
                                      max_order=4):
        """Calcuate coeffients of gauss hermite expansion of histogrammed LOSVD
        around a given v_mu and v_sig

        Parameters
        ----------
        v_mu : float/array
            observed mean velocity
        v_sig : float/array
            observed velocity dispersion
        vel_hist : Histogram
            velocity histogram
        max_order : int
            The maximum order hermite polynomial desired in the expansion

        Returns
        -------
        array shape v_mu.shape + (n_herm_max,)
            expansion coeffients

        """
        w = self.standardise_velocities(vel_hist.x, v_mu, v_sig)
        coef = self.get_hermite_polynomial_coeffients(max_order=max_order)
        nrm = stats.norm()
        hpolys = self.evaluate_hermite_polynomials(coef, w)
        h = vel_hist.y * nrm.pdf(w) * hpolys        # integrand
        h = np.sum(h * vel_hist.dx, 1)              # integral
        h *= 2 * np.pi**0.5                         # pre-factor
        losvd_unnorm = self.evaluate_losvd(vel_hist.x, v_mu, v_sig, h)
        gamma = np.sum(losvd_unnorm * vel_hist.dx)
        h /= gamma
        return h

    def transform_orbits_to_observables(self, orb_lib):
        # actual code to transform orbits to GH coefficients
        return gauss_hermite_coefficients









# end
