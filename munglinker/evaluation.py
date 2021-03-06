#!/usr/bin/env python
"""This is a file that implements various evaluation functionality
for the MungLinker experiments."""
from __future__ import print_function, unicode_literals
import argparse
import logging
import time

import numpy as np

from munglinker.utils import dice

__version__ = "0.0.1"
__author__ = "Jan Hajic jr."


def evaluate_clf(pred_classes, true_classes):
    """Returns binary classification metrics: accuracy overall,
    and precisions, recalls and f-scores as pairs of scores for the 0 and 1
    classes. Typically, the f-score for the positive class is what MuNGLinker
    is most interested in."""
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    accuracy = accuracy_score(true_classes, pred_classes)
    precision, recall, f_score, true_sum = precision_recall_fscore_support(true_classes,
                                                                           pred_classes,
                                                                           average='binary')
    return {'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f-score': f_score,
            'support': true_sum}


def evaluate_classification_by_class_pairs(mungos_from, mungos_to, true_classes, pred_classes,
                                           flatten_results=False, retain_negative=False,
                                           min_support=10):
    """Produce a dict of evaluation results for individual class pairs
    in the data. (Note that grammar restrictions are already built into
    that, if a grammar is used.) By default, retains only the recall, precision,
    f-score for the positive class, and support for both.

    Expects true_classes and pred_classes to be 1-D numpy arrays.

    :param flatten_results: If set, will flatten the results, so that
        the output is a single-level dict with keys like ``notehead-full__stem__fsc``,
        ``key_signature__sharp__fsc``, etc.

    :param retain_negative: If set, will not discard the negative class result
        in per-class data. [NOT IMPLEMENTED]

    :param min_support: In order to be included in the output, a class pair
        has to have a support of at least this many examples.
    """
    class_pair_index = {}
    for i, (m_fr, m_to, tc, pc) in enumerate(zip(mungos_from, mungos_to,
                                                 true_classes, pred_classes)):
        cpair = m_fr.clsname, m_to.clsname
        if cpair not in class_pair_index:
            class_pair_index[cpair] = []
        class_pair_index[cpair].append(i)

    class_pair_results = dict()
    for cpair in class_pair_index:
        cpi = np.array(class_pair_index[cpair]).astype('int64')
        cp_true = np.array([true_classes[i] for i in cpi])
        cp_pred = np.array([pred_classes[i] for i in cpi])
        cp_results_all = evaluate_clf(cp_pred, cp_true)
        # print('cpair {}: support {}'.format(cpair, cp_results_all['support']))
        if cp_results_all['support'] is None:
            cp_results_all['support'] = len(cpi)
        elif isinstance(cp_results_all['support'], list):
            cp_results_all['support'] = cp_results_all['support'].sum()
        if cp_results_all['support'] < min_support:
            continue
        # print('Cpair {}: results\n{}'.format(cpair, cp_results_all))
        cp_results = {
            'recall': cp_results_all['recall'],
            'precision': cp_results_all['precision'],
            'f-score': cp_results_all['f-score'],
            'support': cp_results_all['support']}
        if flatten_results:
            cpair_name = '__'.join(cpair)
            for k, v in cp_results.items():
                class_pair_results[cpair_name + '__' + k] = v
        else:
            class_pair_results[cpair] = cp_results

    return class_pair_results


def print_class_pair_results(class_pair_results, min_support=20):
    """Prints the class pair results ordered by support, from more to less.
    Prints only class pairs that have at least ``min_support`` positive
    plus negative examples."""
    import pprint
    cpair_ordered = sorted([k for k in class_pair_results.keys() if k != 'all'],
                           key=lambda cp: class_pair_results[cp]['support'],
                           reverse=True)
    for cpair in cpair_ordered:
        values = class_pair_results[cpair]
        if values['support'] < min_support:
            continue
        if cpair == 'all':
            cpair_name = cpair
        else:
            cpair_name = '__'.join(cpair)
        for k in ['f-score', 'recall', 'precision', 'support', 'loss']:
            if k in values:
                print('{}__{}'.format(cpair_name, k), values[k])
        print('---------')




##############################################################################


def build_argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, add_help=True,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Turn on INFO messages.')
    parser.add_argument('--debug', action='store_true',
                        help='Turn on DEBUG messages.')

    return parser


def main(args):
    logging.info('Starting main...')
    _start_time = time.time()

    # Your code goes here
    raise NotImplementedError()

    _end_time = time.time()
    logging.info('[XXXX] done in {0:.3f} s'.format(_end_time - _start_time))


if __name__ == '__main__':
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    if args.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    main(args)
