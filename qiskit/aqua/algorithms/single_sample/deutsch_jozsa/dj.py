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
The Deutsch-Jozsa algorithm.
"""

import logging
import operator

from qiskit import ClassicalRegister, QuantumCircuit

from qiskit.aqua.algorithms import QuantumAlgorithm
from qiskit.aqua import AquaError, Pluggable, PluggableType, get_pluggable_class

logger = logging.getLogger(__name__)


class DeutschJozsa(QuantumAlgorithm):
    """The Deutsch-Jozsa algorithm."""

    CONFIGURATION = {
        'name': 'DeutschJozsa',
        'description': 'Deutsch Jozsa',
        'input_schema': {
            '$schema': 'http://json-schema.org/schema#',
            'id': 'dj_schema',
            'type': 'object',
            'properties': {
            },
            'additionalProperties': False
        },
        'problems': ['functionevaluation'],
        'depends': [
            {
                'pluggable_type': 'oracle',
                'default': {
                     'name': 'TruthTableOracle',
                },
            },
        ],
    }

    def __init__(self, oracle):
        self.validate(locals())
        super().__init__()

        self._oracle = oracle
        self._circuit = None
        self._ret = {}

    @classmethod
    def init_params(cls, params, algo_input):
        if algo_input is not None:
            raise AquaError("Input instance not supported.")

        oracle_params = params.get(Pluggable.SECTION_KEY_ORACLE)
        oracle = get_pluggable_class(
            PluggableType.ORACLE,
            oracle_params['name']).init_params(params)
        return cls(oracle)

    def construct_circuit(self):
        if self._circuit is not None:
            return self._circuit

        # preoracle circuit
        qc_preoracle = QuantumCircuit(
            self._oracle.variable_register,
            self._oracle.output_register,
        )
        qc_preoracle.h(self._oracle.variable_register)
        qc_preoracle.x(self._oracle.output_register)
        qc_preoracle.h(self._oracle.output_register)
        qc_preoracle.barrier()

        # oracle circuit
        qc_oracle = self._oracle.circuit

        # postoracle circuit
        qc_postoracle = QuantumCircuit(
            self._oracle.variable_register,
            self._oracle.output_register,
        )
        qc_postoracle.h(self._oracle.variable_register)
        qc_postoracle.barrier()

        # measurement circuit
        measurement_cr = ClassicalRegister(len(
            self._oracle.variable_register), name='m')

        qc_measurement = QuantumCircuit(
            self._oracle.variable_register,
            measurement_cr
        )
        qc_measurement.measure(
            self._oracle.variable_register, measurement_cr)

        self._circuit = qc_preoracle+qc_oracle+qc_postoracle+qc_measurement
        return self._circuit

    @staticmethod
    def interpret_measurement(measurements):
        top_measurement = max(
            measurements.items(), key=operator.itemgetter(1))[0]
        top_measurement = int(top_measurement)
        if top_measurement == 0:
            return "constant"
        else:
            return "balanced"

    def _run(self):
        qc = self.construct_circuit()

        self._ret['circuit'] = qc
        self._ret['measurements'] = self._quantum_instance.execute(
            qc).get_counts(qc)
        self._ret['result'] = DeutschJozsa.interpret_measurement(
            self._ret['measurements'])

        return self._ret
