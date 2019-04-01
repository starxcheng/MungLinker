#!/usr/bin/env python
"""
This is a script that receives two MuNG files. The first
is supposed to be the output of an OMR file, while the
second represents the expected MuNG (ground-truth.)
The script then computes evaluation metrics as regards
the notation assembly stage of the OMR pipeline.
"""
from __future__ import print_function, unicode_literals, division

__version__ = "0.0.1"
__author__ = "Jorge Calvo-Zaragoza"

import argparse
import logging
import os
import numpy as np

from muscima.io import parse_cropobject_list


##############################################################################

def build_argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, add_help=True,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-r', '--reference', action='store', required=True,
                        help='The reference MuNG (ground-truth annotation).')
    parser.add_argument('-p', '--predicted', action='store',
                        help='The predicted MuNG (output of OMR).')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Turn on INFO messages.')
    parser.add_argument('--debug', action='store_true',
                        help='Turn on DEBUG messages.')
    return parser


"""
    Check whether two objects (predicted and reference ones)
    should be considered to match. They do iif:
        - The class name is equal
        - Their IoU exceeds a threshold
"""


def match(p_obj, r_obj, threshold=0.7):
    if p_obj.clsname == r_obj.clsname:
        p_box = [p_obj.left, p_obj.top, p_obj.right, p_obj.bottom]
        r_box = [r_obj.left, r_obj.top, r_obj.right, r_obj.bottom]

        box_area = ((r_box[2] - r_box[0] + 1) * (r_box[3] - r_box[1] + 1))
        iw = (min(p_box[2], r_box[2]) - max(p_box[0], r_box[0]) + 1)

        if iw > 0:
            ih = (min(p_box[3], r_box[3]) - max(p_box[1], r_box[1]) + 1)

            if ih > 0:
                ua = np.float64((p_box[2] - p_box[0] + 1) *
                                (p_box[3] - p_box[1] + 1) +
                                box_area - (iw * ih)
                                )

                IoU = iw * ih / ua

                if IoU > threshold:
                    return True

    return False


def get_object_matching_pairs(predicted_objects, reference_objects):
    pairs = []

    for p_obj in predicted_objects:
        for r_obj in reference_objects:
            if match(p_obj, r_obj):
                logging.debug('Match', p_obj.objid, r_obj.objid)
                pairs.append((p_obj.objid, r_obj.objid))

    return pairs


def cropobject_dict_from_list(cropobject_list):
    return {cropobject.objid: cropobject for cropobject in cropobject_list}


def main(args):
    print('Starting evaluation...')

    # Read crop objects list
    reference_objects = parse_cropobject_list(args.reference)
    predicted_objects = parse_cropobject_list(args.predicted)

    # Build pairs between predicted and reference
    object_matching_pair = get_object_matching_pairs(predicted_objects, reference_objects)

    # Relative ids
    reference_to_prediction_mapping = {r: p for p, r in object_matching_pair}
    prediction_to_reference_mapping = {p: r for p, r in object_matching_pair}

    # Build dict's from crop object lists that are accessed by id
    predicted_objects = cropobject_dict_from_list(predicted_objects)
    reference_objects = cropobject_dict_from_list(reference_objects)

    # Basic evaluation metrics
    true_positives, false_positives, false_negatives = [0, 0, 0]

    for p_obj_id, r_obj_id in object_matching_pair:
        predicted_object = predicted_objects[p_obj_id]
        reference_object = reference_objects[r_obj_id]

        # Check TP and FP (from predicted to reference)
        for out_p_edge in predicted_object.outlinks:
            if prediction_to_reference_mapping[out_p_edge] in reference_object.outlinks:
                true_positives += 1
                logging.debug(" ".join(map(str, [p_obj_id, r_obj_id, out_p_edge])))
            else:
                false_positives += 1

        # Check FN (from reference to predicted)
        for out_r_edge in reference_object.outlinks:
            if reference_to_prediction_mapping[out_r_edge] not in predicted_object.outlinks:
                false_negatives += 1

    print('F1-Score: {0:.3f}'.format((2. * true_positives) / (2. * true_positives + false_positives + false_negatives)))
    print("True positives: {0}, False positives: {1}, False Negatives: {2}".format(true_positives, false_positives, false_negatives))


if __name__ == '__main__':
    parser = build_argument_parser()
    args = parser.parse_args()
    main(args)