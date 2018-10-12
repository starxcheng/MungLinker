#!/usr/bin/env python
"""This is a script that applies a trained e2e OMR model to an input image
or a directory of input images, and outputs the corresponding MIDI file(s).
"""
from __future__ import print_function, unicode_literals
import argparse
import collections
import copy
import logging
import os
import time

import numpy as np
import pickle

from muscima.graph import NotationGraph
from muscima.io import parse_cropobject_list, export_cropobject_list
from scipy.misc import imread, imsave

from muscima.inference import play_midi

import torch
from torch.autograd import Variable

from munglinker.augmentation import ImageAugmentationProcessor
# from munglinker.model import FCN
# from munglinker.model import apply_on_image, apply_on_image_window
# from munglinker.model import apply_model
# from munglinker.model import ensure_shape_divisible, set_image_as_variable
# from munglinker.image_normalization import auto_invert, stretch_intensity
# from munglinker.image_normalization import ImageNormalizer
# from munglinker.utils import lasagne_fcn_2_pytorch_fcn
from munglinker.data_pool import PairwiseMungoDataPool, load_config
from munglinker.model import PyTorchNetwork
from munglinker.utils import generate_random_mm, select_model, config2data_pool_dict
from munglinker.utils import midi_matrix_to_midi

__version__ = "0.0.1"
__author__ = "Jan Hajic jr."


##############################################################################


class MunglinkerRunner(object):
    """The MunglinkerRunner defines the Munglinker component interface. It has a run()
    method that takes a MuNG (the whole graph) and outputs a new MuNG with the same
    objects, but different edges.
    """
    def __init__(self, model, config, runtime_batch_iterator,
                 replace_all_edges=True):
        """Initialize the Munglinker runner.

        :param model: A PyTorchNetwork() object with a net. Its predict()
            method is called, with a data pool that is constructed on the
            fly from the provided images & mungs, and with the batch iterator
            provided to this  __init__() method.

        """
        self.model = model
        self.config = config
        self.runtime_batch_iterator = runtime_batch_iterator

        # We pre-build the parameters that are used to wrap the input data
        # into a data pool.
        data_pool_dict = config2data_pool_dict(self.config)
        data_pool_dict['max_negative_samples'] = -1
        if 'grammar' not in data_pool_dict:
            logging.warning('MunglinkerRunner expects a grammar to restrict'
                            ' edge candidates. Without a grammar, it will take'
                            ' a long time, since all possible object pairs'
                            ' will be tried. (This is fine if you trained without'
                            ' the grammar restriction, obviously.)')
        self.data_pool_dict = data_pool_dict

        self.replace_all_edges = replace_all_edges

    def run(self, image, mung):
        """Processes the image and outputs MIDI.

        :returns: A ``midiutil.MidiFile.MIDIFile`` object.
        """
        data_pool = self.build_data_pool(image, mung)
        mungo_pairs, output_classes = self.model.predict(data_pool,
                                                        self.runtime_batch_iterator)
        # Since the runner only takes one image & MuNG at a time,
        # we have the luxury that all the mung pairs belong to the same
        # document, and we can just re-do the edges.
        mungo_copies = [copy.deepcopy(m) for m in mung.cropobjects]
        if self.replace_all_edges:
            for m in mungo_copies:
                m.outlinks = []
                m.inlinks = []

        new_mung = NotationGraph(mungo_copies)
        for mungo_pair, has_edge in zip(mungo_pairs, output_classes):
            if has_edge:
                mungo_fr, mungo_to = mungo_pair
                new_mung.add_edge(mungo_fr.objid, mungo_to.objid)
            else:
                mungo_fr, mungo_to = mungo_pair
                if new_mung.has_edge(mungo_fr.objid, mungo_to.objid):
                    new_mung.remove_edge(mungo_fr.objid, mungo_to.objid)

        return new_mung

    def build_data_pool(self, image, mung):
        data_pool = PairwiseMungoDataPool(mungs=[mung], images=[image],
                                          **self.data_pool_dict)
        return data_pool

    def model_output_to_midi(self, output_repr):
        return midi_matrix_to_midi(output_repr)


##############################################################################


def show_result(*args, **kwargs):
    raise NotImplementedError()

##############################################################################


def build_argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, add_help=True,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-m', '--model', required=True,
                        help='The name of the model that you wish to use.')
    parser.add_argument('-p', '--params', required=True,
                        help='The state dict that should be loaded for this model.'
                             ' Note that you have to make sure you are loading'
                             ' a state dict for the right model architecture.')
    parser.add_argument('-c', '--config_file', required=True,
                        help='The config file that controls how inputs'
                             ' to the network will be extracted from MuNGOs.')

    parser.add_argument('-i', '--input_image', required=True,
                        help='A single-system input image for which MIDI should'
                             ' be output. This is the simplest input mode.')
    parser.add_argument('-g', '--input_mung', required=True,
                        help='A MuNG XML file. The edges inoinks/outlinks in'
                             ' the file are ignored, unless the --retain_edges'
                             ' flag is set [NOT IMPLEMENTED].')

    parser.add_argument('-o', '--output_mung', required=True,
                        help='The MuNG with inferred edges should be exported'
                             ' to this file.')

    parser.add_argument('--visualize', action='store_true',
                        help='If set, will plot the image and output MIDI'
                             '[NOT IMPLEMENTED].')
    parser.add_argument('--batch_size', type=int, action='store', default=10,
                        help='The runtime iterator batch size.')

    parser.add_argument('--input_dir',
                        help='A directory with single-system input images. For'
                             ' each of these, a MIDI will be produced. Use'
                             ' instead of --input_image for batch processing.'
                             ' [NOT IMPLEMENTED]')
    parser.add_argument('--output_dir',
                        help='A directory where the output MIDI files will be'
                             ' stored. Use together with --input_dir.'
                             ' [NOT IMPLEMENTED]')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Turn on INFO messages.')
    parser.add_argument('--debug', action='store_true',
                        help='Turn on DEBUG messages.')

    return parser


def main(args):
    logging.info('Starting main...')
    _start_time = time.clock()

    ##########################################################################
    # First we prepare the model

    logging.info('Loading config: {}'.format(args.config))
    config = load_config(args.config)

    logging.info('Loading model: {}'.format(args.model))
    model_mod = select_model(args.model)
    build_model_fn = model_mod.get_build_model()
    net = build_model_fn()

    logging.info('Loading model params from state dict: {0}'.format(args.params))
    params = torch.load(args.params)
    net.load_state_dict(params)

    use_cuda = torch.cuda.is_available()
    if use_cuda:
        logging.info('\tModel: CUDA available, moving to GPU')
        net.cuda()

    runtime_batch_iterator = model_mod.runtime_batch_iterator(batch_size=args.batch_size)

    model = PyTorchNetwork(net=net, print_architecture=False)

    ########################################################
    # Now we run it

    logging.info('Initializing runner...')
    runner = MunglinkerRunner(model=model,
                              config=config,
                              runtime_batch_iterator=runtime_batch_iterator,
                              replace_all_edges=True)

    logging.info('Loading image: {}'.format(args.input_image))
    img = imread(args.input_image, mode='L')

    logging.info('Loading MuNG: {}'.format(args.input_mung))
    input_mungos = parse_cropobject_list(args.input_mung)
    input_mung = NotationGraph(input_mungos)

    logging.info('Running OMR')
    output_mung = runner.run(img, input_mung)

    ##########################################################################
    # And deal with the output:

    if args.visualize:
        logging.info('Visualization not implemented!!!')
        pass

    if args.play:
        logging.info('Playback not implemented!!!')
        pass

    logging.info('Saving output MuNG to: {}'.format(args.output_mung))
    with open(args.output_mung, 'w') as hdl:
        hdl.write(export_cropobject_list(output_mung.cropobjects))

    # No evaluation here.

    _end_time = time.clock()
    logging.info('run.py done in {0:.3f} s'.format(_end_time - _start_time))


if __name__ == '__main__':
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    if args.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    main(args)
