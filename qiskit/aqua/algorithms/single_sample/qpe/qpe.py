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
"""
The Quantum Phase Estimation Algorithm.
"""

import logging
import numpy as np

from qiskit.quantum_info import Pauli

from qiskit.aqua import Operator, AquaError
from qiskit.aqua import Pluggable, PluggableType, get_pluggable_class
from qiskit.aqua.utils import get_subsystem_density_matrix
from qiskit.aqua.algorithms import QuantumAlgorithm
from qiskit.aqua.circuits import PhaseEstimationCircuit


logger = logging.getLogger(__name__)


class QPE(QuantumAlgorithm):
    """The Quantum Phase Estimation algorithm."""

    PROP_NUM_TIME_SLICES = 'num_time_slices'
    PROP_EXPANSION_MODE = 'expansion_mode'
    PROP_EXPANSION_ORDER = 'expansion_order'
    PROP_NUM_ANCILLAE = 'num_ancillae'

    CONFIGURATION = {
        'name': 'QPE',
        'description': 'Quantum Phase Estimation for Quantum Systems',
        'input_schema': {
            '$schema': 'http://json-schema.org/schema#',
            'id': 'qpe_schema',
            'type': 'object',
            'properties': {
                PROP_NUM_TIME_SLICES: {
                    'type': 'integer',
                    'default': 1,
                    'minimum': 1
                },
                PROP_EXPANSION_MODE: {
                    'type': 'string',
                    'default': 'trotter',
                    'oneOf': [
                        {'enum': [
                            'suzuki',
                            'trotter'
                        ]}
                    ]
                },
                PROP_EXPANSION_ORDER: {
                    'type': 'integer',
                    'default': 1,
                    'minimum': 1
                },
                PROP_NUM_ANCILLAE: {
                    'type': 'integer',
                    'default': 1,
                    'minimum': 1
                }
            },
            'additionalProperties': False
        },
        'problems': ['energy'],
        'depends': [
            {'pluggable_type': 'initial_state',
             'default': {
                     'name': 'ZERO'
                }
             },
            {'pluggable_type': 'iqft',
             'default': {
                     'name': 'STANDARD',
                }
             },
        ],
    }

    def __init__(
            self, operator, state_in, iqft, num_time_slices=1, num_ancillae=1,
            expansion_mode='trotter', expansion_order=1,
            shallow_circuit_concat=False
    ):
        """
        Constructor.

        Args:
            operator (Operator): the hamiltonian Operator object
            state_in (InitialState): the InitialState pluggable component representing the initial quantum state
            iqft (IQFT): the Inverse Quantum Fourier Transform pluggable component
            num_time_slices (int): the number of time slices
            num_ancillae (int): the number of ancillary qubits to use for the measurement
            expansion_mode (str): the expansion mode (trotter|suzuki)
            expansion_order (int): the suzuki expansion order
            shallow_circuit_concat (bool): indicate whether to use shallow (cheap) mode for circuit concatenation
        """
        self.validate(locals())
        super().__init__()

        self._num_ancillae = num_ancillae
        self._ret = {}
        self._operator = operator
        self._pauli_list = self._operator.get_flat_pauli_list()
        self._ret['translation'] = sum([abs(p[0]) for p in self._pauli_list])
        self._ret['stretch'] = 0.5 / self._ret['translation']

        # translate the operator
        self._operator._simplify_paulis()
        translation_op = Operator([
            [
                self._ret['translation'],
                Pauli(
                    np.zeros(self._operator.num_qubits),
                    np.zeros(self._operator.num_qubits)
                )
            ]
        ])
        translation_op._simplify_paulis()
        self._operator += translation_op

        # stretch the operator
        for p in self._pauli_list:
            p[0] = p[0] * self._ret['stretch']

        self._phase_estimation_circuit = PhaseEstimationCircuit(
            operator=self._operator, state_in=state_in, iqft=iqft,
            num_time_slices=num_time_slices, num_ancillae=num_ancillae,
            expansion_mode=expansion_mode, expansion_order=expansion_order,
            shallow_circuit_concat=shallow_circuit_concat, pauli_list=self._pauli_list
        )
        self._binary_fractions = [1 / 2 ** p for p in range(1, num_ancillae + 1)]

    @classmethod
    def init_params(cls, params, algo_input):
        """
        Initialize via parameters dictionary and algorithm input instance.

        Args:
            params: parameters dictionary
            algo_input: EnergyInput instance
        """
        if algo_input is None:
            raise AquaError("EnergyInput instance is required.")

        operator = algo_input.qubit_op

        qpe_params = params.get(Pluggable.SECTION_KEY_ALGORITHM)
        num_time_slices = qpe_params.get(QPE.PROP_NUM_TIME_SLICES)
        expansion_mode = qpe_params.get(QPE.PROP_EXPANSION_MODE)
        expansion_order = qpe_params.get(QPE.PROP_EXPANSION_ORDER)
        num_ancillae = qpe_params.get(QPE.PROP_NUM_ANCILLAE)

        # Set up initial state, we need to add computed num qubits to params
        init_state_params = params.get(Pluggable.SECTION_KEY_INITIAL_STATE)
        init_state_params['num_qubits'] = operator.num_qubits
        init_state = get_pluggable_class(PluggableType.INITIAL_STATE,
                                         init_state_params['name']).init_params(params)

        # Set up iqft, we need to add num qubits to params which is our num_ancillae bits here
        iqft_params = params.get(Pluggable.SECTION_KEY_IQFT)
        iqft_params['num_qubits'] = num_ancillae
        iqft = get_pluggable_class(PluggableType.IQFT, iqft_params['name']).init_params(params)

        return cls(operator, init_state, iqft, num_time_slices, num_ancillae,
                   expansion_mode=expansion_mode,
                   expansion_order=expansion_order)

    def construct_circuit(self):
        """Construct circuit.

        Returns:
            QuantumCircuit: quantum circuit.
        """
        qc = self._phase_estimation_circuit.construct_circuit()
        return qc

    def _compute_energy(self):
        qc = self.construct_circuit()
        if self._quantum_instance.is_statevector:
            result = self._quantum_instance.execute(qc)
            complete_state_vec = result.get_statevector(qc)
            ancilla_density_mat = get_subsystem_density_matrix(
                complete_state_vec,
                range(self._num_ancillae, self._num_ancillae + self._operator.num_qubits)
            )
            ancilla_density_mat_diag = np.diag(ancilla_density_mat)
            max_amplitude = max(ancilla_density_mat_diag.min(), ancilla_density_mat_diag.max(), key=abs)
            max_amplitude_idx = np.where(ancilla_density_mat_diag == max_amplitude)[0][0]
            top_measurement_label = np.binary_repr(max_amplitude_idx, self._num_ancillae)[::-1]
        else:
            from qiskit import ClassicalRegister
            c_ancilla = ClassicalRegister(self._num_ancillae, name='ca')
            qc.add_register(c_ancilla)
            qc.barrier(self._phase_estimation_circuit.ancillary_register)
            qc.measure(self._phase_estimation_circuit.ancillary_register, c_ancilla)
            result = self._quantum_instance.execute(qc)
            ancilla_counts = result.get_counts(qc)
            top_measurement_label = sorted([(ancilla_counts[k], k) for k in ancilla_counts])[::-1][0][-1][::-1]

        top_measurement_decimal = sum(
            [t[0] * t[1] for t in zip(self._binary_fractions, [int(n) for n in top_measurement_label])]
        )

        self._ret['top_measurement_label'] = top_measurement_label
        self._ret['top_measurement_decimal'] = top_measurement_decimal
        self._ret['eigvals'] = [top_measurement_decimal / self._ret['stretch'] - self._ret['translation']]
        self._ret['energy'] = self._ret['eigvals'][0]

    def _run(self):
        self._compute_energy()
        return self._ret
