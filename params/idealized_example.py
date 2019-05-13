"""Parameter file for lensing reconstruction on a idealized, full-sky simulation library.

    The CMB simulations are the FFP10 lensed CMB simulations, together with homogeneous, Gaussian noise maps.

    The CMB simulations are located on NERSC systems project directory, hence this may only be used there.

    The parameter files should instantiate
        * the simulation library 'sims'
        * the inverse-variance filtered simulation library 'ivfs'
        * the 3 quadratic estimator libraries, 'qlms_dd', 'qlms_ds', 'qlms_ss'.
        * the 3 quadratic estimator power spectra libraries 'qcls_dd, 'qcls_ds', 'qcls_ss'.
          (qcls_ss is required for the MCN0 calculation, qcls_ds and qcls_ss for the RDN0 calculation.)
        * the quadratic estimator response library 'qresp_dd'
        * the semi-analytical Gaussian lensing bias library 'nhl_dd'
        * the N1 lensing bias library 'n1_dd'.

    On the first call the this module a couple of things will be cached in the directories defined below.

"""

import os
import healpy as hp
import numpy as np

from plancklens2018.filt import filt_simple, filt_util
from plancklens2018 import utils
from plancklens2018 import qest, qecl, qresp
from plancklens2018 import nhl
from plancklens2018.n1 import n1
from plancklens2018.sims import planck2018_sims, phas, maps, utils as maps_utils

assert 'PL2018' in os.environ.keys(), 'Set env. variable PL2018 to the planck 2018 lensing directory'
PL2018 = os.environ['PL2018']

#--- definition of simulation and inverse-variance filtered simulation libraries:
lmax_ivf = 2048
lmin_ivf = 100  # We will use in the QE only CMB modes between lmin_ivf and lmax_ivf
lmax_qlm = 4096 # We will calculate lensing estimates until multipole lmax_qlm.
nside = 2048 # Healpix resolution of the data and sims.
nlev_t = 35. # Filtering noise level in temperature (here also used for the noise simulations generation).
nlev_p = 55. # Filtering noise level in polarization (here also used for the noise simulations generation).
nsims = 300  # Total number of simulations to consider.

transf = hp.gauss_beam(5. / 60. / 180. * np.pi, lmax=lmax_ivf) * hp.pixwin(nside)[:lmax_ivf + 1]
#: CMB transfer function. Here a 5' Gaussian beam and healpix pixel window function.

cl_unl = utils.camb_clfile(os.path.join(PL2018, 'inputs','cls','FFP10_wdipole_lenspotentialCls.dat'))
cl_len = utils.camb_clfile(os.path.join(PL2018, 'inputs','cls','FFP10_wdipole_lensedCls.dat'))
#: Fiducial unlensed and lensed power spectra used for the analysis.

cl_weight = utils.camb_clfile(os.path.join(PL2018, 'inputs','cls','FFP10_wdipole_lensedCls.dat'))
cl_weight['bb'] *= 0.
#: CMB spectra entering the QE weights (the spectra multplying the inverse-variance filtered maps in the QE legs)

libdir_pixphas = os.path.join(PL2018, 'temp', 'pix_phas_nside%s'%nside)
pix_phas = phas.pix_lib_phas(libdir_pixphas, 3, (hp.nside2npix(nside),))
#: Noise simulation T, Q, U random phases instance.

sims = maps_utils.sim_lib_shuffle(maps.cmb_maps_nlev(planck2018_sims.cmb_len_ffp10(), transf, nlev_t, nlev_p, nside,
                            pix_lib_phas=pix_phas), {idx: nsims if idx == -1 else idx for idx in range(-1, nsims)})
#: Simulation library. Here this combines the ffp10 lensed CMBs together with the transfer function
#  and homogeneous noise as defined by the phase library.
#  The funny dictionary in the last argument is just a way.


# --- We turn to the inverse-variance filtering library. In this file we use trivial isotropic filtering,
#     (independent T and Pol. filtering)
ftl = utils.cli(cl_len['tt'][:lmax_ivf+ 1] + (nlev_t / 60. / 180. *np.pi  / transf) ** 2)
fel = utils.cli(cl_len['ee'][:lmax_ivf+ 1] + (nlev_p / 60. / 180. *np.pi  / transf) ** 2)
fbl = utils.cli(cl_len['bb'][:lmax_ivf+ 1] + (nlev_p / 60. / 180. *np.pi  / transf) ** 2)
ftl[:lmin_ivf] *= 0.
fel[:lmin_ivf] *= 0.
fbl[:lmin_ivf] *= 0.
#: Inverse CMB co-variance in T, E and B (neglecting TE coupling).

libdir_ivfs  = os.path.join(PL2018, 'temp', 'idealized_example', 'ivfs')
ivfs    = filt_simple.library_fullsky_sepTP(libdir_ivfs, sims, nside, transf, cl_len, ftl, fel, fbl, cache=True)
#: Inverse-variance filtering instance.

#---- QE libraries instances. For the MCN0 and RDN0 calculation, we need in general three of them,
# which we called qlms_dd, qlms_ds, qlms_ss.
# qlms_dd is the QE library which builds a lensing estimate with the same simulation on both legs
# qlms_ds is the QE library which builds a lensing estimate with a simulation on one leg and the data on the second.
# qlms_ss is the QE library which builds a lensing estimate with a simulation on one leg and another on the second.

# Shuffling dictionary used for qlms_ss. This remaps idx -> idx + 1 by blocks of 60 up to 300:
ss_dict = { k : v for k, v in zip( np.concatenate( [ range(i*60, (i+1)*60) for i in range(0,5) ] ),
                    np.concatenate( [ np.roll( range(i*60, (i+1)*60), -1 ) for i in range(0,5) ] ) ) }
# Shuffling dictionary used for qlms_ds. This remap all sim. indices to the data maps:
ds_dict = { k : -1 for k in range(300)}

ivfs_d = filt_util.library_shuffle(ivfs, ds_dict)
#: This is a filtering instance always returning the data map.
ivfs_s = filt_util.library_shuffle(ivfs, ss_dict)
#: This is a filtering instance shuffling simulation indices according to 'ss_dict'.

libdir_qlmsdd = os.path.join(PL2018, 'temp', 'idealized_example', 'qlms_dd')
libdir_qlmsds = os.path.join(PL2018, 'temp', 'idealized_example', 'qlms_ds')
libdir_qlmsss = os.path.join(PL2018, 'temp', 'idealized_example', 'qlms_ss')
qlms_dd = qest.library_sepTP(libdir_qlmsdd, ivfs, ivfs,   cl_len['te'], nside, lmax_qlm={'P': lmax_qlm, 'T':lmax_qlm})
qlms_ds = qest.library_sepTP(libdir_qlmsds, ivfs, ivfs_d, cl_len['te'], nside, lmax_qlm={'P': lmax_qlm, 'T':lmax_qlm})
qlms_ss = qest.library_sepTP(libdir_qlmsss, ivfs, ivfs_s, cl_len['te'], nside, lmax_qlm={'P': lmax_qlm, 'T':lmax_qlm})

#---- QE spectra libraries instances:
# This takes power spectra of the QE maps from the QE libraries, after subtracting a mean-field.
# Only qlms_dd needs a mean-field subtraction.
libdir_qcls_dd = os.path.join(PL2018, 'temp', 'idealized_example', 'qcls_dd')
libdir_qcls_ds = os.path.join(PL2018, 'temp', 'idealized_example', 'qcls_ds')
libdir_qcls_ss = os.path.join(PL2018, 'temp', 'idealized_example', 'qcls_ss')

mc_sims_bias = np.arange(60) #: The mean-field will be calculated from these simulations.
mc_sims_var  = np.arange(60, 300) #: The covariance matrix will be calculated from these simulations

mc_sims_mf_dd = mc_sims_bias
mc_sims_mf_ds = np.array([])
mc_sims_mf_ss = np.array([]) #:By construction, only qcls_dd needs a mean-field subtraction.

qcls_dd = qecl.library(libdir_qcls_dd, qlms_dd, qlms_dd, mc_sims_mf_dd)
qcls_ds = qecl.library(libdir_qcls_ds, qlms_ds, qlms_ds, mc_sims_mf_ds)
qcls_ss = qecl.library(libdir_qcls_ss, qlms_ss, qlms_ss, mc_sims_mf_ss)

#---- semi-analytical Gaussian lensing bias library
libdir_nhl_dd = os.path.join(PL2018, 'temp', 'idealized_example', 'nhl_dd')
nhl_dd = nhl.nhl_lib_simple(libdir_nhl_dd, ivfs, cl_weight, lmax_qlm)

#---- N1 lensing bias library
libdir_n1_dd = os.path.join(PL2018, 'temp', 'n1_ffp10')
n1_dd = n1.library_n1(libdir_n1_dd,cl_len['tt'],cl_len['te'],cl_len['ee'])

#---- QE response calculation library.
libdir_resp_dd = os.path.join(PL2018, 'temp', 'idealized_example', 'qresp')
qresp_dd = qresp.resp_lib_simple(libdir_resp_dd, lmax_ivf, cl_weight, cl_len,{'t': ivfs.get_ftl(), 'e':ivfs.get_fel(), 'b':ivfs.get_fbl()}, lmax_qlm)
