# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM Corp. 2017 and later.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


class VarFormBased:
    """An initial state derived from a variational form.
       Intended to be used programmatically only.
    """

    def __init__(self, var_form, params):
        """Constructor.

        Args:
            var_form (VariationalForm): the variational form.
            params (list or numpy.ndarray): parameter for the variational form.
        """
        super().__init__()
        if not var_form.num_parameters == len(params):
            raise RuntimeError('Incompatible parameters provided.')
        self._var_form = var_form
        self._var_form_params = params

    def construct_circuit(self, mode, register=None):
        """
        Construct the statevector of desired initial state.

        Args:
            mode (string): `vector` or `circuit`. The `vector` mode produces the vector.
                            While the `circuit` constructs the quantum circuit corresponding that
                            vector.
            register (QuantumRegister): register for circuit construction.

        Returns:
            QuantumCircuit or numpy.ndarray: statevector.

        Raises:
            ValueError: when mode is not 'vector' or 'circuit'.
        """
        if mode == 'vector':
            raise RuntimeError('Initial state based on variational form does not support vector mode.')
        elif mode == 'circuit':
            return self._var_form.construct_circuit(self._var_form_params, q=register)
        else:
            raise ValueError('Mode should be either "vector" or "circuit"')
