# Kulkarn group @ UC Davis
"""Definition of the Zeotype class.

This module defines the central object in analyzing Zeotypes
"""
import shutil
import sys, os
from ase import Atoms

try:
    from ase.neighborlist import natural_cutoffs
except:
    from ase.utils import natural_cutoffs
from ase.calculators.vasp import Vasp
from copy import deepcopy
import json


class KulTools:
    """KulTools class that provides all the necessary tools for running simulations. Currently targetted towards using vasp. """

    def __init__(self, structure: Atoms, calculation_type, structure_type, calc_spec=None, gamma_only=None):
        assert isinstance(structure, Atoms), 'structure must be an Atoms object'
        self.structure = structure
        self.structure_after = None
        assert calculation_type in ['spe', 'opt', 'opt_fine',
                                    'dry_run', 'alchemy'], "Unknown calculation_type = %s" % calculation_type

        self.calculation_type = calculation_type
        self.structure_type = structure_type

        self.gamma_only = gamma_only
        print('KT: VASP_GAMMA= %s' % self.gamma_only)
        self.hpc = self.identify_hpc_cluster()
        print('KT: HPC= %s' % self.hpc)
        self.set_vasp_eviron_vars()

        self.calc = self.get_default_calc(**calc_spec)
        self.modify_calc_according_to_structure_type()

    def get_input_params(self):
        return deepcopy(self.calc.input_params)

    def identify_hpc_cluster(self) -> str:
        """
        Identify the hpc cluster, and return value
        """
        path_home = os.environ['HOME']
        if path_home.startswith('/global/homes'):
            host_name = 'cori'
        elif path_home.startswith('/home/'):
            if os.environ['SLURM_SUBMIT_HOST'] == 'hpc1':
                host_name = 'hpc1'
            elif os.environ['SLURM_SUBMIT_HOST'] == 'hpc2':
                host_name = 'hpc2'
        elif path_home.startswith('/Users/'):
            host_name = 'local'
        elif path_home.startswith('/home1/'):
            host_name = 'stampede'
        else:
            RuntimeWarning('Check cluster settings, cluster type not detected')
        return host_name

    def set_vasp_eviron_vars(self):
        """
        Identify and set vasp environmental variables
        """
        if self.hpc == 'hpc1':
            os.environ['VASP_PP_PATH'] = '/home/ark245/programs/vasp5.4.4/pseudopotentials/pseudo54'
            if self.gamma_only:
                vasp_exe = 'vasp_gam'
            else:
                vasp_exe = 'vasp_std'
            os.environ[
                'VASP_COMMAND'] = 'module load vasp/5.4.4pl2-vtst; NTASKS=`echo $SLURM_TASKS_PER_NODE|tr \'(\' \' \'|awk \'{print $1}\'`; NNODES=`scontrol show hostnames $SLURM_JOB_NODELIST|wc -l`; NCPU=`echo " $NTASKS * $NNODES " | bc`; echo "num_cpu=" $NCPU; srun -n $NCPU %s | tee -a op.vasp' % vasp_exe

        elif self.hpc == 'hpc2':
            os.environ['VASP_PP_PATH'] = '/home/ark245/programs/pseudopotentials/pseudo54'
            if self.gamma_only:
                vasp_exe = 'vasp_gam'
            else:
                vasp_exe = 'vasp_std'
            os.environ[
                'VASP_COMMAND'] = 'NTASKS=`echo $SLURM_TASKS_PER_NODE|tr \'(\' \' \'|awk \'{print $1}\'`; NNODES=`scontrol show hostnames $SLURM_JOB_NODELIST|wc -l`; NCPU=`echo " $NTASKS * $NNODES " | bc`; echo "num_cpu=" $NCPU; $(which mpirun) --map-by core --display-map --report-bindings --mca btl_openib_allow_ib true --mca btl_openib_if_include mlx5_0:1 --mca btl_openib_warn_nonexistent_if 0 --mca btl_openib_warn_no_device_params_found 0 --mca pml ob1 --mca btl openib,self,vader --mca mpi_cuda_support 0 -np $NCPU %s | tee -a op.vasp' % vasp_exe
            print(os.environ['VASP_COMMAND'])

        elif self.hpc == 'cori':
            os.environ['VASP_PP_PATH'] = '/global/homes/a/ark245/pseudopotentials/PBE54'
            if self.gamma_only:
                vasp_exe = 'vasp_gam'
            else:
                vasp_exe = 'vasp_std'
            os.environ[
                'VASP_COMMAND'] = 'NTASKS=`echo $SLURM_TASKS_PER_NODE|tr \'(\' \' \'|awk \'{print $1}\'`; NNODES=`scontrol show hostnames $SLURM_JOB_NODELIST|wc -l`; NCPU=`echo " $NTASKS * $NNODES " | bc`; echo "num_cpu=" $NCPU; srun -n $NCPU %s | tee -a op.vasp' % vasp_exe
        elif self.hpc == 'stampede':
            os.environ['VASP_PP_PATH'] = '/home1/05364/ark245/pseudopotentials/PBE54'
            if self.gamma_only:
                vasp_exe = 'vasp_gam_vtst'
            else:
                vasp_exe = 'vasp_std_vtst'
            os.environ[
                'VASP_COMMAND'] = 'module load vasp/5.4.4; export OMP_NUM_THREADS=1;rm op.vasp; mpirun -np $SLURM_NTASKS %s | tee op.vasp' % vasp_exe
        elif self.hpc == 'local':
            os.environ['VASP_PP_PATH'] = 'local_vasp_pp'
            if self.gamma_only:
                vasp_exe = 'vasp_gam'
            else:
                vasp_exe = 'vasp_std'
            os.environ['VASP_COMMAND'] = 'local_%s' % vasp_exe
        else:
            RuntimeWarning('Check cluster settings, cluster type not detected')

        try:
            vasp_pp_path = os.environ['VASP_PP_PATH']
            vasp_command = os.environ['VASP_COMMAND']
            print('KT: VASP_PP_PATH= %s' % vasp_pp_path)
            print('KT: VASP_COMMAND= %s' % vasp_command)
        except KeyError:
            pass

    def get_default_calc(self, kpts=(1, 1, 1), potim=0.5, encut=500, ispin=2, nsw=50, prec='Normal', istart=1,
                         isif=2, ismear=0, sigma=0.05, nelmin=4, nelmdl=-4, nwrite=1, icharg=2, lasph=True,
                         ediff=1E-6, ediffg=-0.05, ibrion=2, lcharg=False, lwave=False, laechg=False,
                         voskown=1, algo='Fast', lplane='True', lread='Auto', isym=0, xc='PBE', lorbit=11,
                         nupdown=-1, npar=4, nsim=4, ivdw=12, **kwargs):
        """Sets a default calculator regadless of the structure type"""

        return Vasp(kpts=kpts,
                    potim=potim,
                    encut=encut,
                    ispin=ispin,
                    nsw=nsw,
                    prec=prec,
                    istart=istart,
                    isif=isif,
                    ismear=ismear,
                    sigma=sigma,
                    nelmin=nelmin,
                    nelmdl=nelmdl,
                    nwrite=nwrite,
                    icharg=icharg,
                    lasph=lasph,
                    ediff=ediff,
                    ediffg=ediffg,
                    ibrion=ibrion,
                    lcharg=lcharg,
                    lwave=lwave,
                    laechg=laechg,
                    voskown=voskown,
                    algo=algo,
                    lplane=lplane,
                    lreal=lread,
                    isym=isym,
                    xc=xc,
                    lorbit=lorbit,
                    nupdown=nupdown,
                    npar=npar,
                    nsim=nsim,
                    ivdw=ivdw)

    def modify_calc_according_to_structure_type(self):
        assert self.structure_type in ['zeo', 'mof', 'metal',
                                       'gas-phase'], "Unknown structure_type = %s" % self.structure_type
        if self.structure_type == 'zeo' or self.structure_type == 'mof':
            pass
        elif self.structure_type == 'metal':
            self.calc.set(sigma=0.2, ismear=1)
        elif self.structure_type == 'gas-phase':
            self.calc.set(kpts=(1, 1, 1), lreal=False)

    def run_dry_run(self) -> Atoms:
        return deepcopy(self.structure)

    def run_alchemy(self) -> Atoms:
        with open('input_params.txt', 'w') as f:
            json.dump(self.get_input_params(), f, indent=4, sort_keys=True)

        atoms = deepcopy(self.structure)
        for a in atoms:
            a.symbol = 'Au'
        return atoms

    def run_dft(self, atoms) -> Atoms:
        atoms = deepcopy(atoms)  # prevent side effects
        atoms.set_calculator(self.calc)
        atoms.get_potential_energy()  # Run vasp here
        return atoms

    def run_spe(self) -> Atoms:
        """Runs a simple single point energy"""
        self.calc.set(nsw=0)
        return self.run_dft(self.structure)

    def run_opt(self):
        """Runs a simple optimization"""
        return self.run_dft(self.structure)

    def run_opt_fine(self):
        """Runs a finer optimization"""
        self.calc.set(ibrion=1, potim=0.05, nsw=50, ediffg=-0.03)
        return self.run_dft(self.structure)

    def run_vib(self):
        """Runs a simple vib calculation"""
        self.calc.set(ibrion=5, potim=0.02, nsw=1)
        return self.run_dft(self.structure)

    def run_solv(self, lrho=False):
        """Runs a simple solvation calculation"""
        self.calc.set(potim=0.0, nsw=5, lwave=True, lsol=False, prec='Accurate')
        atoms = self.run_dft(self.structure)
        shutil.copyfile('WAVECAR', 'solv-spe-WAVECAR')
        self.calc.set(potim=0.0, nsw=3, lwave=True, lsol=True, prec='Accurate')
        atoms = self.run_dft(atoms)

        if lrho:
            shutil.copyfile('WAVECAR', 'solv-spe-rho-WAVECAR')
            self.calc.set(potim=0.0, nsw=0, lwave=True, lsol=True, prec='Accurate', lrhob=True, lrhoion=True)
            atoms = self.run_dft(atoms)

        return atoms

    def run(self):
        if self.calculation_type == 'dry_run':
            self.structure_after = self.run_dry_run()
        elif self.calculation_type == 'opt':
            self.structure_after = self.run_opt()  # atoms,dir_name)
        elif self.calculation_type == 'opt_fine':
            self.structure_after = self.run_opt_fine()
        elif self.calculation_type == 'vib':
            self.structure_after = self.run_vib()
        elif self.calculation_type == 'solv':
            self.structure_after = self.run_solv()
        elif self.calculation_type == 'alchemy':
            self.structure_after = self.run_alchemy()
        else:
            raise RuntimeError('calculation type does not match allowed calc types')

        return self.structure_after
