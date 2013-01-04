"""Genetic Algorithmn Implementation """
import random, bisect

import sys, os

sys.path.append(str(os.environ['QTRADE']))
from pyTrade.utils.LogSubsystem import LogSubsystem
from pyTrade.ai.genetic import Genetic, GeneticAlgorithm


def testGenetic(genes):
    '''--------------------------------------------    Parameters    -----'''
    '''chromosome[short_window, long_window, buy_on_event, sell_on_event] '''
    #print('chromosome: {}'.format(genes))
    '''-----------------------------------------------    Running    -----'''
    score = 0
    for gene in genes.values():
        score += gene
    return score
    

class EvolveQuant(Genetic):
    def __init__(self, evaluator, logger=None, elitism_rate=25,
                 prob_crossover=0.8, prob_mutation=0.2):
        if logger == None:
            self._logger = LogSubsystem(self.__class__.__name__, 'info').getLog()
        else:
            self._logger = logger
        self._logger.info('Initiating genetic environment.')
        Genetic.__init__(self, evaluator, elitism_rate, prob_crossover, \
                prob_mutation, self._logger)

''' 
Gene code description
long_window = 73 -> 200 : 0000000 > 1111111 + 73
ma_rate = 3 -> 10 : 000 > 111 + 2
buy_n = 10 -> 300 : 11111111 + 25
buy_rate = 37 -> 100 : 111111 + 37
'''

if __name__ == "__main__":
    ''' So a new algorithm needs a gene_description and an evaluator '''
    gene_code = {'short_window': (6,73), 'ma_rate': (3,3), 'buy_n': (8,25), 'buy_rate': (6,37)}
    ga = EvolveQuant(testGenetic, elitism_rate=30, prob_mutation=0.2)
    ga.describeGenome(gene_code, popN=400)
    GeneticAlgorithm(ga, selection='roulette').run(generations=100, freq=50)
