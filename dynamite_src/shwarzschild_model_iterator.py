import schwarzschild
import parameter_space
import numpy as np

class SchwarzschildModelIterator(object):

    def __init__(self,
                 system=None,
                 all_models=None,
                 settings=None):
        stopping_crit = settings.parameter_space_settings['stopping_criteria']
        n_max_iter = stopping_crit['n_max_iter']
        model_inner_iterator = SchwarzschildModelInnerIterator(
            system=system,
            all_models=all_models,
            settings=settings)
        for iter in range(n_max_iter):
            status = model_inner_iterator.run_iteration(iter)
            if status['stop'] is True:
                print(f'Stopping after iteration {iter}')
                print(status)
                break


class SchwarzschildModelInnerIterator(object):

    def __init__(self,
                 iter=0,
                 system=None,
                 all_models=None,
                 settings=None):
        self.system = system
        self.all_models = all_models
        self.settings = settings
        self.parspace = parameter_space.ParameterSpace(system)
        # get specified parameter generator object
        par_generator_type = settings.parameter_space_settings['generator_type']
        self.par_generator_type = par_generator_type
        self.par_generator = getattr(parameter_space,
                                     par_generator_type)(self.parspace)

    def run_iteration(self, iter):
        # generate parameter sets for this iteration
        print(f'{self.par_generator_type}: "iteration {iter}"')
        self.par_generator.generate(current_models=self.all_models)
        # generate parameter sets for this iteration
        if self.par_generator.status['stop'] is False:
            print('... running here!')
            # find models not yet done
            idx_todo = np.where(self.all_models.table['all_done'] == False)
            idx_todo = idx_todo[0]
            for idx in idx_todo:
                # extract the parameter values
                parset0 = self.all_models.table[idx]
                parset0 = parset0[self.parspace.par_names]
                # create and run the model
                mod0 = self.create_model(parset0)
                self.all_models.table['chi2'][idx] = mod0.chi2
                self.all_models.table['kinchi2'][idx] = mod0.kinchi2
                self.all_models.table['which_iter'][idx] = iter
        return self.par_generator.status

    def create_model(self, parset):
        kwargs = {'system':self.system,
                  'settings':self.settings,
                  'parspace':self.parspace,
                  'parset':parset}
        # create a model object based on choices in settings
        if self.settings.legacy_settings['use_legacy_mode']:
            mod = getattr(schwarzschild, 'LegacySchwarzschildModel')(**kwargs)
        else:
            # TODO: create other model classes based on a choice of:
            # (i) orbit library generator
            # (i) weight solver
            # (iii) colour solver
            # mod = getattr(schwarzschild, '...')(**kwargs)
            raise ValueError("""
                             Only Legacy Mode currently implemented. Set
                                 legacy_settings:
                                     use_legacy_mode: True
                             in the config file
                             """)
        return mod







# end
