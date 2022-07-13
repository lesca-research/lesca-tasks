"""
Implementation of a color Stroop task. Answers can be given via keystrokes.

The participant is instructed to ignore the meaning of the printed word and
indicate the ink color of the word. 

There are 3 conditions: congruent, conflicting and naming, depending on how 
ink color matches the word meaning. 
For example, in the congruent condition the words "RED", "GREEN" and "BLUE" are
 displayed in the ink colors red, green, and blue, respectively.
For the conflicting condition the printed words are
different from the ink color in which they are printed (e.g., the word
"RED" printed in blue ink). 
The neutral condition consists of noncolor words presented in an ink color 
(e.g., the word "CHAIR" printed in red ink) and had a low level of conflict and low attentional demands.

The participant is instructed to respond to the ink color in which the
text appeared by pressing the corresponding buttons 

The paradigm offers a practice session with a short duration for familiarization and performance assessment.

A trial begins Stroop stimulus for 2000 ms, during which the participant is 
instructed to respond as quickly as possible. 
The interstimulus interval is taken so that all event onsets are random within
the duration of the session. The presentation is randomized 
A total of 120 trials are presented: 42 congruent, 42 neutral, 36 incongruent.
A lower number of incongruent trials is used in order to reduce the expectancy 
of a stimulus conflict relative to the other conditions.

A trial is composed of:
  - cue: either circle, square or cross, displayed for a given amount of time
  - stim: a word with a given color, which can be surrounded by a box and
          displayed for a given amount of time

In terms of interference between the color of the word and its meaning, 
a stimulus can be either STIM_CONGRUENT, STIM_NEUTRAL, STIM_UNCOLORED or 
STIM_INCONCRUENT

The task can be either TASK_COLOR_NAMING or TASK_WORD_READING

TODOS:
- add trigger in exported variables @XPD
- add paradigm version string @XPD (?)

Changelog:


* 2019/11/15, v0.23
- add synced dual pulse option for synchronization (to test)
- update GPIO indexes to new pulse box
- Change block order to A-B-B-A-A-B-A-B
- Add illustrations during familiarization

* 2019/11/15, v0.22 
- Simplify and improve familiarization (remove performance target, less trials)
- Add saving of stimulation snapshot (in test menu)

* 2019/10/01, v0.21 
- Add trial-specific audio recording with accurate time-stamping

* 2019/09/01, v0.20 
- Use red, blue, green, yellow with consistant luminance. As in the
  classic 4-color stroop
- Add speech input (only instructions, audio recording NO HANDLED)
- Use subject ID as prefix for output data file
- Add French translations
- Refactor definition instruction messages
- Use ACTIONcardioRisk prefix for participant ID

* 2019/08/01, v0.19
- Remove everything related to exercise 
- Cleaned comments
- fork from Stroop ACUMOB

* 2018/05/10, v0.18
- add output of stim end timestamp @XPD
- add output of performance @XPD

* 2018/05/09, v0.17
- add effort-related labels for sessions
- remove Mekari
- remove cycling between random versions of sessions
- add fixation cross during rest blocks
- add performance feedback just after block
  WARNING: this will delay all the onsets, only for testing for now in the main sessions
  TODO: take into account perf display delay if critical. But maybe this will
        only be used during familiarization where timing is not critical.
        Still, the event of performance display should be reported in the XPD file

* 2018/04/26, v0.16
- adjust colors: lighter blue and darker purple
- increase font size

* 2018/04/17, v0.15
- fix delay when displaying frame around word
- fix missing subject_id in XPD header

* 2018/04/16, v0.14
- switching blocks composed of sub-blocks of inhibition trials, 
  interleaved with single reading trials (switch trials).
- naming blocks using 4 common words
- answers using keys u,i,o,p
- 4 colors
- add 1st AccuNirs Strooper paradigm
 
* 2018/04/02, v0.13
- abort by pressing backspace key during rest periods
- abort by pressing backspace key during rest periods
- add clock syncing with lesca.ca and output of time stamps
- add answer management
- add subject PIN 
- add data saving
- add triggering
- add translation
- ensure reproducibility of main sessions (unit tested)

* 2018/04/01, v0.12
- add some tests
- improve choice function to ensure that random picking from a list 
  provides at least one realisation of each element if number of picks
  is larger than list size.
* 2018/03/31, v0.11
- improve Stim/Trial/Block/Session design to better plug expyriment API
- add menus

* 2018/03/29, v0.1
- add paradigm of Mekari 2015
- add session/block/trial definitions as namedtupled

"""
import sys
import os.path as op
import os
from collections import OrderedDict
from itertools import cycle, product, chain, zip_longest
import time
import urllib.request, urllib.parse, urllib.error
import warnings
import numpy as np
from numpy.random import shuffle, randint, dirichlet, rand
import hashlib
from collections import defaultdict, namedtuple
if sys.version_info < (3, 9):
    import importlib_resources
else:
    import importlib.resources as importlib_resources

from expyriment import design, control, stimuli, io #, design, misc
import expyriment.misc.constants as cst

from lesca_tasks import trigger, default_task_arg_parser
from lesca_tasks.trigger import NO_TRIGGER

from lesca_tasks.logging import logger

np.random.seed(4344)

VERSION = '0.23'
LANGUAGES = ['f', 'e'] # French, English


# Paradigm specification
Stim = namedtuple('Stim', 'label duration_ms char_ID ' \
                          'expected_answer responses xp_stimuli')
VOID_STIM = Stim('void', 0, NO_TRIGGER, None, None, [])
Trial = namedtuple('Trial', 'label char_ID stimuli ')

class Block:
    def __init__(self, label, char_ID, trials, show_performance=False):
        self.label = label
        self.char_ID = char_ID
        self.trials = trials
        self.show_performance = show_performance

Session = namedtuple('Session', 'label char_ID blocks')
Color = namedtuple('Color', 'name rgb')


TR_FR = {"Preparing session..." : "Preparation de la session...",
         "Press space to start session" : "Appuyez sur espace pour demarrer",
         "xxxx" : "xxxx",
         "green": "vert",
         "blue" : "bleu",
         "red" : "rouge",
         "yellow" : "jaune",
         "orange": "orange",
         "purple": "violet",
         "white": "blanc",
         "but" : "alors",
         "when" : "quand",
         "for" : "pour",
         "with" : "avec"}

def tr(word, language):
    """ Translation given english word into given language """
    if language == 'e':
        return word
    elif language == 'f':
        return TR_FR[word]
    else:
        raise Exception('Uknown language: %s' % language)

def incongruences(colors):
    incongruences = []
    for col_name, color in list(colors.items()):        
        incongruences.extend([(col_name, cn, col)
                              for cn,col in list(colors.items()) if cn != col_name])
    return incongruences


def interleave_element(l1, e):
    return list(chain(*[(e1,e) for e1 in l1])) 

def zip_join(l, intermediates):
    assert len(intermediates) == len(l)-1
    return list(chain(*zip_longest(l, intermediates)))[:-1]

class AbortBlockException(Exception):
    pass


ALL_COLORS = {"green": (25, 255, 25),
              "blue" : (0, 0, 255),
              "red" :  (255, 0, 0),
              "yellow" : (250, 255, 25),
              "orange": (255, 127, 0),
              "purple": (225, 0, 255),
              "white": (255, 255, 255)}

COLOR_NAMES = dict((col_rgb,col_name) for col_name,col_rgb in list(ALL_COLORS.items()))

def rest_stim(duration_ms, exp, symbol='+'):
    return Stim('Stim_rest', duration_ms, NO_TRIGGER, None, None,
                [stimuli.TextLine(symbol, text_size=exp['CROSS_SIZE'],
                                  text_colour=ALL_COLORS['white'])])


NEUTRAL_WORDS = [] #"CHAIR", "BOAT", "BOTTLE", "SCREEN", "CABLE", "SUGAR", "HOUSE", "PLANE", "WHEEL", "JACKET", "GLOVES"]

assert(set(NEUTRAL_WORDS + list(ALL_COLORS.keys())).issubset(list(TR_FR.keys())))

def is_android_running():
    """ Return True if the current OS is android """
    try:
        import android
    except ImportError:
        return False
    return True

from numpy.random import default_rng

def choice(l, nb_repetitions=1, balanced=False, rng=None):
    x = np.empty(len(l), dtype=object)
    x[:] = l

    if rng is None:
        rng = default_rng()
    if nb_repetitions < len(l):
        if not balanced:
            return rng.choice(x, nb_repetitions, replace=True)
        else:
            return rng.choice(x, nb_repetitions, replace=False)
    else:
        if not balanced:
            return np.concatenate((rng.choice(x, len(x), replace=False),
                                   rng.choice(x, nb_repetitions-len(x),
                                              replace=True)))
        else:
            return np.random.choice(np.concatenate((rng.choice(x, len(x), replace=False),
                                                    choice(x, nb_repetitions-len(x), True, rng=rng))),
                                    nb_repetitions, replace=False)

BLOCK_CHAR_ID = {
    'naming' : {
        'control' : 'L',
        'congruent' : 'E',
        'incongruent' : 'G'
    },
    'reading' : {
        'control' : 'M',
        'congruent' : 'F',
        'incongruent' : 'H'
    },
    'switching' : 'W'
}

STIM_CHAR_ID = {
    'naming' : {
        'control' : 'X',
        'congruent' : 'C',
        'incongruent' : 'I'
    },
    'reading' : {
        'control' : 'Y',
        'congruent' : 'T',
        'incongruent' : 'R'
    }
}

TRIAL_NX = 0 # Naming control
TRIAL_NI = 1 # Naming incongruent
TRIAL_RI = 2 # Reading incongruent

TRIALS_SPEC = [('naming', 'control'),
               ('naming', 'inhibition'),
               ('reading', 'inhibition')]

class Strooper:

    # Block design
    NB_BLOCKS_NAMING = 4
    NB_BLOCKS_SWITCHING = 4
    NB_BLOCKS = NB_BLOCKS_NAMING + NB_BLOCKS_SWITCHING

    REST_DURATION = 35000 #ms
    REST_DURATION_JITTER = 15000 #ms
    NB_TRIALS_PER_BLOCK = 15
    NB_TRIALS_SWITCH_PER_BLOCK = 4

    BLOCK_CUE_DURATION = 1000 #ms
    # Event-related design
    ER_NB_SWITCHING = 25
    ER_NB_INHIB = ER_NB_SWITCHING * 3
    ER_NB_CONTROL = ER_NB_SWITCHING
    ER_ISI_MIN_MS = 400
    ER_ISI_MEAN_MS = 4000


    BASELINE_PRE_DURATION = 30000 #ms
    BASELINE_POST_DURATION = 30000 #ms

    CUE_DURATION = 400 #ms
    STIM_DURATION = 1800 #ms
    COLORS = dict((c,ALL_COLORS[c]) for c in ['blue', 'red', 'green', 'yellow'])

    # WORDS = ['but','when', 'for', 'with']
    WORDS = ['xxxx']

    KEYS = OrderedDict( [(cst.K_w, 'red'),
                         (cst.K_q, 'green'),
                         (cst.K_e, 'blue'),
                         (cst.K_r, 'yellow')])

    INPUT_KBD = 1
    INPUT_SPEECH = 0

    # task / input type / language
    INSTRUCTIONS = {
    'fam_input' : {
        INPUT_KBD : {
            'f' : "Une série de mots colorés vont être présentés en séquence. " \
                  "A chaque apparition d'un mot, identifiez la couleur de "\
                  "l'encre en utilisant le clavier.\n\n" \
                  "Dans ce qui suit, identifiez la couleur de l'encre d'un "\
                  " mot en appuyant sur la touche associée." ,
            'e' : 'A series of colored words will be presented in sequence, '\
                  'one at a time. You are asked to identify colors by pressing keys '\
                  'on the keyboard.\n\n'\
                  'In the following test, identify the color of the ink by pressing '\
                  'the associated key.' ,
            },
        INPUT_SPEECH : {
            'f' : "Une série de mots colorés vont être présentés.\n" \
                  "A chaque mot, prononcez la couleur de l'encre.\n\n" \
                  "Le symbole '#' indique le début de la série.\n\n\n"
                  "Appuyez sur espace pour commencer" ,
            'e' : 'A series of colored words will be presented in sequence, '\
                  'one at a time. You are asked to identify the colors of the ink '\
                  'and pronounce it.\n\n' \
                  'Press space to launch the test.' \
            }
        },
     'fam_naming' : {
        INPUT_KBD : {
            'f': "Une série de mots colorés SANS RECTANGLE vont être " \
                 "présentés.\nIdentifiez la COULEUR DE L'ENCRE en " \
                 "appuyant sur la touche correspondante.\n\n" \
                 "Appuyez sur espace pour lancer le test",
            'e': 'A series of colored words WITH NO FRAME will be presented in sequence, '\
                 'one at a time.\nIdentify the INK COLOR '\
                 'by pressing the associated key.\n\n'\
                 'Press space to launch the test.'
            },
        INPUT_SPEECH : {
            'f': "Une série de mots colorés SANS RECTANGLE vont être " \
                 "présentés.\nIdentifiez la COULEUR DE L'ENCRE et " \
                 "prononcez la.\n\n" \
                 "Appuyez sur espace pour lancer le test",
            'e': 'A series of colored words WITH NO FRAME will be presented in sequence, '\
                 'one at a time.\nIdentify the INK COLOR '\
                 'and pronounce it.\n\n'\
                 'Press space to launch the test.'
            }
        },
      'fam_switching' : {
          INPUT_KBD : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés.\n\n" \
                    "Lorsque le mot est SANS RECTANGLE, identifiez la "\
                    "COULEUR DE L'ENCRE en appuyant sur la touche correspondante.\n\n"\
                    "Lorsqu'un RECTANGLE ENTOURE le mot, LISEZ le mot dans votre tête " \
                    "et appuyez sur la touche correspondante à la couleur.",
              'e' : 'A series of colored words will be presented in sequence, '\
                    'one at a time.\n\nWhen the word has NO FRAME, identify ' \
                    'the INK COLOR by pressing the associated key.\n\n'\
                    'When the word HAS A FRAME: READ THE WORD in your head' \
                    'and press the associated color key.'
              },
          INPUT_SPEECH : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés.\n\n" \
                    "Lorsque le mot est SANS rectangle, prononcez la "\
                    "COULEUR DE L'ENCRE.\n\n"\
                    "Lorsque le mot est AVEC rectangle, LISEZ le mot.\n\n\n"\
                     "Appuyez sur espace pour lancer le test",
              'e' : 'A series of colored words will be presented in sequence, '\
                    'one at a time.\n\nWhen the word has NO FRAME, identify ' \
                    'the INK COLOR and pronounce it.\n\n'\
                    'When the word HAS A FRAME: READ THE WORD.\n\n\n'\
                    'Press space to launch the test.'
              }      
        },
      'fam_full_XXXX' : {
          INPUT_KBD : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés. Parfois certains mots "\
                    "seront entourés d'un rectangle et parfois non.\n\n" \
                    "Lorsque le mot est SANS rectangle,\nindiquez la "\
                    "COULEUR DE L'ENCRE.\n\n"\
                    "Lorsque le mot est AVEC un rectangle,\n indiquez la couleur en LISANT le mot.",
              'e' : 'A series of colored words will be presented in sequence, '\
                    'one at a time.\n\nWhen the word has NO FRAME, identify ' \
                    'the INK COLOR by pressing the associated key.\n\n'\
                    'When the word HAS A FRAME: READ THE WORD in your head' \
                    'and press the associated color key.'
              },
          INPUT_SPEECH : {
              'f' : "Une série de mots 'XXXX' colorés vont être " \
                    "présentés.\n\n" \
                    "Pressez la touche correspondant à la couleur de l'encre.\n\n" \
                    "Le symbole '#' indique le début de la série.\n\n",
              'e' : "A sequence of XXXX colored words will follow. "
				    "Press the key matching the ink color.n\n" \
				    "The symbol # indicates the start of the sequence."
              }      
        }, # 10 trials, expected accuracy of 90%. If not redo
        'fam_full_inhib_reading' : {
          INPUT_KBD : {
              'f' : "TODO \n appuyez sur la touche correspondante à la couleur.\n\n\n"\
                     "Appuyez sur espace pour lancer le test",
              'e' : 'TODO \n press the associated color key.\n\n\n'\
                    'Press space to launch the test.'
              },
          INPUT_SPEECH : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés.\n\n" \
                    "Prononcez la couleur de l'encre.\n\n\n"\
                     "Appuyez sur espace pour lancer le test",
              'e' : 'TODO \n\n\n'\
                    'Press space to launch the test.'
              }
        }, # 10 trials, expected accuracy of 80%. If not redo
        'fam_full_inhib_color' : {
          INPUT_KBD : {
              'f' : "TODO \n appuyez sur la touche correspondante à la couleur.\n\n\n"\
                     "Appuyez sur espace pour lancer le test",
              'e' : 'TODO \n press the associated color key.\n\n\n'\
                    'Press space to launch the test.'
              },
          INPUT_SPEECH : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés.\n\n" \
                    "Lorsque le mot est SANS RECTANGLE, identifiez la "\
                    "COULEUR DE L'ENCRE en appuyant sur la touche correspondante.\n\n"\
                    "Lorsqu'un RECTANGLE ENTOURE le mot, LISEZ le mot dans votre tête " \
                    "et appuyez sur la touche correspondante à la couleur.",
              'e' : 'A series of colored words will be presented in sequence, '\
                    'one at a time.\n\nWhen the word has NO FRAME, identify ' \
                    'the INK COLOR by pressing the associated key.\n\n'\
                    'When the word HAS A FRAME: READ THE WORD in your head' \
                    'and press the associated color key.'
              }
        }, # 10 trials, expected accuracy of 80%. If not redo
        'fam_full_switching' : {
          INPUT_KBD : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés. Parfois certains mots "\
                    "seront entourés d'un rectangle et parfois non.\n\n" \
                    "Lorsque le mot est SANS rectangle,\nindiquez la "\
                    "COULEUR DE L'ENCRE.\n\n"\
                    "Lorsque le mot est AVEC un rectangle,\n indiquez la couleur en LISANT le mot.",
              'e' : "A sequence of colored words will be shown. Some words will be " \
                    "surrounded by a rectangle and others not.\n\n"\
                    "When the word has NO rectangle, identify the INK COLOR and press the matching key.\n\n" \
                    "When the word HAS A RECTANGLE, READ the word in your head and press the matching key.\n\n"
                    'Press space to launch the test.'
              },
          INPUT_SPEECH : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés. Parfois certains mots "\
                    "seront entourés d'un rectangle et parfois non.\n\n" \
                    "Lorsque le mot est SANS rectangle,\nprononcez la "\
                    "COULEUR DE L'ENCRE.\n\n"\
                    "Lorsque le mot est AVEC un rectangle,\nLISEZ le mot.\n\n\n"\
                     "Appuyez sur espace pour lancer le test",
              'e' : 'TODO \n\n\n'\
                    'Press space to launch the test.'
              }
        }, 
        'fam_full_blocs' : {
          INPUT_KBD : {
              'f' : "Une pratique va suivre.\n\n"\
                    "Rappel des instructions:\n" \
                    "- mot SANS rectangle: identifiez la COULEUR DE L'ENCRE et pressez le bouton correspondant\n"\
                    "- mot AVEC rectangle: LISEZ le mot dans votre tête et pressez le bouton correspondant\n"\
                    "- croix blanche: regardez simplement la croix.\n\n"\
                    "Le symbole '#' indiquera le début de chaque série.",
              'e' : 'A series of colored words will be presented in sequence, '\
                    'one at a time.\n\nWhen the word has NO FRAME, identify ' \
                    'the INK COLOR by pressing the associated key.\n\n'\
                    'When the word HAS A FRAME: READ THE WORD in your head' \
                    'and press the associated color key.\n\n' \
                    'The symbole # indicates the start of sequence.'
              },
          INPUT_SPEECH : {
              'f' : "Une pratique va suivre.\n\n"\
                    "Rappel des instructions:\n" \
                    "- mot SANS rectangle: prononcez la COULEUR DE L'ENCRE\n"\
                    "- mot AVEC rectangle: LISEZ le mot\n"\
                    "- croix blanche: regardez simplement la croix.\n\n"\
                    "Le symbole '#' indiquera le début de chaque série.\n\n" \
                    "Appuyez sur espace pour lancer le test",
              'e' : 'TODO \n\n\n'\
                    'Press space to launch the test.'
              }
        },
        'fam_full_intro' : {
          INPUT_KBD : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés. Parfois certains mots "\
                    "seront entourés d'un rectangle et parfois non.\n\n" \
                    "Lorsque le mot est SANS rectangle,\nindiquez la "\
                    "COULEUR DE L'ENCRE.\n\n"\
                    "Lorsque le mot est AVEC un rectangle,\nLISEZ le mot.\n\n\n"\
                     "Appuyez sur espace pour lancer le test",
              'e' : "A sequence of colored words will be shown. Some words will be " \
                    "surrounded by a rectangle and others not.\n\n"\
                    "When the word has NO rectangle, identify the INK COLOR and press the matching key.\n\n" \
                    "When the word HAS A RECTANGLE, READ the word in your head and press the matching key.\n\n"
                    'Press space to launch the test.'
              },
          INPUT_SPEECH : {
              'f' : "Une série de mots colorés vont être " \
                    "présentés.\n\n"\
                    "Lorsque le mot est SANS rectangle,\nprononcez la "\
                    "COULEUR DE L'ENCRE.\n\n"\
                    "Lorsque le mot est AVEC rectangle,\nLISEZ le mot.\n\n"\
                    "Les écrans suivants vont présenter des exemples.",
              'e' : 'TODO \n\n\n'\
                    'Press space to launch the test.'
              }
        },
        'fam_full_rest' : {
          INPUT_KBD : {
              'f' : "TODO \n appuyez sur la touche correspondante à la couleur.\n\n\n"\
                     "Appuyez sur espace pour lancer le test",
              'e' : 'TODO \n press the associated color key.\n\n\n'\
                    'Press space to launch the test.'
              },
          INPUT_SPEECH : {
              'f' :  "Lorsqu'une une croix blanche est affichée, "\
                     "regardez simplement la croix et ne pensez à rien de particulier.\n\n"\
                     "L'écran suivant montre un exemple.",
              'e' : 'TODO \n\n\n'\
                    'Press space to launch the test.'
              }
        },
    }

    def __init__(self, input_type=INPUT_KBD):
        self.input_type = input_type

    def data_fn(self, rfn):
        return (importlib_resources.files('porch.data.stroop_color')
                .joinpath('rfn'))

    def gen_cue_stim(self, exp):
        xp_stims = [stimuli.TextLine("")]
        return Stim('Stim_cue', Strooper.CUE_DURATION, NO_TRIGGER,
                    None, None, xp_stims)

    def gen_word_stim(self, exp, word, color, stim_type, framed=False):
        xp_stims = [stimuli.TextLine(tr(word, exp['language']).upper(),
                                     text_size=exp['TEXT_SIZE'],
                                     text_colour=color)]
        if framed:
            txt_size = xp_stims[0].surface_size
            xp_stims.append(stimuli.Rectangle((txt_size[0]+exp['TXT_FRAME_PAD'],
                                               txt_size[1]+exp['TXT_FRAME_PAD']),
                                              line_width=exp['TXT_FRAME_LW'],
                                              colour=exp['TXT_FRAME_COLOR']))

        if not framed: # color naming
            expected_answer = COLOR_NAMES[color]
            task = 'naming'
        else: # word reading
            expected_answer = word
            task = 'reading'
        stim_label = 'Stim_%s_%s' % (task, stim_type)
        return Stim(stim_label, Strooper.STIM_DURATION,
                    STIM_CHAR_ID[task][stim_type], expected_answer,
                    Strooper.KEYS, xp_stims)

    def gen_naming_trials(self, exp, words=None, colors=None,
                          prepend_cue=True):
        if colors is None:
            colors = list(Strooper.COLORS.items())
        if words is None:
            words = Strooper.WORDS
        trials = []
        for word, (col_name, col) in product(words, colors):
            stims = [self.gen_word_stim(exp, word, col, 'control')]
            if prepend_cue:
                stims.insert(0, self.gen_cue_stim(exp))
            trials.append(Trial('Trial_%s_C%s' % (word, col_name), NO_TRIGGER,
                                stims))
        return trials

    def gen_congruent_naming_trials(self, exp):
        return [Trial('Trial_%s_%s' % (col_name, col_name), NO_TRIGGER,
                      [self.gen_cue_stim(exp),
                       self.gen_word_stim(exp, col_name, col, 'congruent')])
                for col_name, col in list(Strooper.COLORS.items())]

    def prepend_block_cue(self, exp, block_trials):
        return [Trial('Trial_block_cue', NO_TRIGGER,
                      [rest_stim(Strooper.BLOCK_CUE_DURATION, exp, '#')])] + \
               block_trials

    def gen_naming_block(self, exp, show_performance=False, rng=None):
        char_id = BLOCK_CHAR_ID['naming']['control']
        return Block('Block_Naming', char_id,
                     self.prepend_block_cue(exp,
                        list(choice(self.gen_naming_trials(exp),
                                    Strooper.NB_TRIALS_PER_BLOCK, rng=rng))
                     ),
                     show_performance=show_performance)

    def gen_congruent_naming_block(self, exp, show_performance=False, rng=None):
        char_id = BLOCK_CHAR_ID['naming']['congruent']
        return Block('Block_Naming_Congruent', char_id,
                     self.prepend_block_cue(exp,
                         list(choice(self.gen_congruent_naming_trials(exp),
                                     Strooper.NB_TRIALS_PER_BLOCK,
                                     balanced=True, rng=rng))
                     ),
                     show_performance=show_performance)

    def gen_inhib_trials(self, exp, colors=None, framed=False, prepend_cue=True):
        if colors is None:
            colors = Strooper.COLORS
        trials = []
        for word, col_name, col in incongruences(colors):
            stims = [self.gen_word_stim(exp, word, col, 'incongruent',
                                        framed=framed)]
            if prepend_cue:
                stims.insert(0, self.gen_cue_stim(exp))
            trials.append(Trial('Trial_' + word.upper() + '_' + col_name,
                                NO_TRIGGER, stims))
        return trials

    def gen_inhibit_color_block(self, exp, show_performance=False, rng=None):
        char_id = BLOCK_CHAR_ID['naming']['incongruent']
        return Block('Block_Naming_Incongruent', char_id,
                     self.prepend_block_cue(exp,
                        list(choice(self.gen_inhib_trials(exp, framed=True),
                                    Strooper.NB_TRIALS_PER_BLOCK, rng=rng))
                     ),
                     show_performance=show_performance)

    def gen_inhibit_reading_block(self, exp, show_performance=False, rng=None):
        char_id = BLOCK_CHAR_ID['reading']['incongruent']
        return Block('Block_Reading_Incongruent', char_id,
                     self.prepend_block_cue(exp,
                         list(choice(self.gen_inhib_trials(exp),
                                     Strooper.NB_TRIALS_PER_BLOCK, rng=rng))
                     ),
                     show_performance=show_performance)

    def get_all_possible_trials(self, exp):
        return [Trial('Trial_rest', NO_TRIGGER, [rest_stim(0, exp)])] + \
               self.gen_naming_trials(exp) + \
               self.gen_inhib_trials(exp) + \
               self.gen_switch_trials(exp)

    def gen_switch_trials(self, exp, prepend_cue=True):
        trials = []
        for word, col_name, col in incongruences(Strooper.COLORS):
            stims = [self.gen_word_stim(exp, word, col, 'incongruent',
                                        framed=True)]
            if prepend_cue:
                stims.insert(0, self.gen_cue_stim(exp))
            trials.append(Trial('Trial_' + word.upper() + '_' + col_name + '_sw',
                                NO_TRIGGER, stims))
        return trials

    def gen_inhib_sub_block_sizes(self, exp, rng):
        min_trials = 1
        max_trials = 4
        total_trials = Strooper.NB_TRIALS_PER_BLOCK - \
                       Strooper.NB_TRIALS_SWITCH_PER_BLOCK
        nb_sub_blocks = Strooper.NB_TRIALS_SWITCH_PER_BLOCK + 1
        sub_block_sizes = []
        for i in range(nb_sub_blocks-1):
            adjusted_max = total_trials - (nb_sub_blocks-i) * min_trials - \
                           sum(sub_block_sizes)
            sub_block_sizes.append(rng.integers(min_trials,
                                                min(max_trials, adjusted_max)+1))
        sub_block_sizes.append(total_trials - sum(sub_block_sizes))
        sub_block_sizes = np.array(sub_block_sizes)
        rng.shuffle(sub_block_sizes) #TODO: use numpy here
        assert(sum(sub_block_sizes) == total_trials)
        print('sub_block_sizes:', sub_block_sizes)
        return sub_block_sizes
    def gen_switching_block(self, exp, show_performance=False, rng=None):
        nb_switches = Strooper.NB_TRIALS_SWITCH_PER_BLOCK
        switch_trials = choice(self.gen_switch_trials(exp), nb_switches, rng=rng)
        inhib_trials_ref = self.gen_inhib_trials(exp)
        trials = [Trial('Trial_block_cue', NO_TRIGGER,
                        [rest_stim(Strooper.BLOCK_CUE_DURATION, exp, '#')])]
        inhib_sub_block_sizes = self.gen_inhib_sub_block_sizes(exp, rng)
        for nb_inhib_sub_block, switch_trial in zip(inhib_sub_block_sizes,
                                                    switch_trials):
            trials.extend(choice(inhib_trials_ref, nb_inhib_sub_block, rng=rng))
            trials.append(switch_trial)
        trials.extend(choice(inhib_trials_ref, inhib_sub_block_sizes[-1], rng=rng))

        return Block('Block_Switching_Incongruent', BLOCK_CHAR_ID['switching'],
                     trials, show_performance)

    def gen_familiarization_input_session(self, exp, session_type, session_label, rng):

        msg = Strooper.INSTRUCTIONS['fam_input'][self.input_type][exp['language']]

        if exp['TEST']:
            fam_text_size = 12
        else:
            fam_text_size = 50

        stim_instr = stimuli.TextBox(msg, size=(exp['scr_w']*.6,
                                                exp['scr_h']*.7),
                                     text_size=fam_text_size,
                                     text_justification=0)
        return Session(session_label, NO_TRIGGER,
                       [Block('Block_input_intro', NO_TRIGGER,
                              [Trial('Trial_input_intro', NO_TRIGGER,
                                    [Stim('Stim_input_intro', None, NO_TRIGGER,
                                          'DUMMY', {cst.K_SPACE:'DUMMY'},
                                          [stim_instr])])],
                              show_performance=False),
                        self.gen_congruent_naming_block(exp, show_performance=False, rng=rng)])

    def gen_familiarization_naming_session(self, exp, session_type, session_label, rng):

        msg = Strooper.INSTRUCTIONS['fam_naming'][self.input_type][exp['language']]       
        if exp['TEST']:
            fam_text_size = 12
        else:
            fam_text_size = 50

        stim_instr = stimuli.TextBox(msg, size=(exp['scr_w']*.6,
                                                exp['scr_h']*.7),
                                     text_size=fam_text_size,
                                     text_justification=0)
        return Session(session_label, NO_TRIGGER,
                       [Block('Block_fam_naming_intro', NO_TRIGGER,
                              [Trial('Trial_fam_naming_intro', NO_TRIGGER,
                                    [Stim('Stim_fam_naming_intro', None, NO_TRIGGER,
                                          'DUMMY', {cst.K_SPACE:'DUMMY'},
                                          [stim_instr])])]),
                        self.gen_naming_block(exp, show_performance=False, rng=rng)])


    def gen_familiarization_switching_session(self, exp, session_type, session_label, rng):

        msg = Strooper.INSTRUCTIONS['fam_switching'][self.input_type][exp['language']]       

        if exp['TEST']:
            fam_text_size = 12
        else:
            fam_text_size = 50
            
        stim_instr = stimuli.TextBox(msg, size=(exp['scr_w']*.6,
                                                exp['scr_h']*.7),
                                     text_size=fam_text_size,
                                     text_justification=0)
        return Session(session_label, NO_TRIGGER,
                       [Block('Block_fam_switching_intro', NO_TRIGGER,
                              [Trial('Trial_fam_switching_intro', NO_TRIGGER,
                                    [Stim('Stim_fam_switching_intro', None, NO_TRIGGER,
                                          'DUMMY', {cst.K_SPACE:'DUMMY'},
                                          [stim_instr])])],
                              show_performance=False),
                        self.gen_switching_block(exp, True, rng=rng)])

    def gen_familiarization_full_sessions(self, exp, session_type, session_label, rng):
        
        msg_fam_intro = Strooper.INSTRUCTIONS['fam_full_intro'][self.input_type][exp['language']]
        
        if exp['TEST']:
            fam_text_size = 12
        else:
            fam_text_size = 50
        
        sessions = []
        
        stim_instr = stimuli.TextBox(msg_fam_intro, 
                                     size=(exp['scr_w']*.6, exp['scr_h']*.7),
                                     text_size=fam_text_size,
                                     text_justification=0)
        sessions.append((Session('Session_fam_intro', NO_TRIGGER,
                         [Block('Block_fam_intro', NO_TRIGGER,
                                [Trial('Trial_fam_intro', NO_TRIGGER,
                                     [Stim('Stim_fam_intro', None, NO_TRIGGER,
                                           'DUMMY', {cst.K_SPACE:'DUMMY'},
                                           [stim_instr])])],
                                show_performance=False)]), 0, 1))

        from IPython import embed; embed()
        fam_example_pic_fn = \
            self.data_fn('instruction_stim_illustration_XXXX_%s.png' % \
                         exp['language'])
        pic_stim = stimuli.Picture(fam_example_pic_fn)
        pic_stim.scale_to_fullscreen()
        sessions.append((pic_stim, 0, 1))
        
        fam_example_pic_fn = op.join(exp['stim_data_dir'], 
                                     'instruction_stim_illustration_color_%s.png' % \
                                     exp['language'])
        pic_stim = stimuli.Picture(fam_example_pic_fn)
        pic_stim.scale_to_fullscreen()
        sessions.append((pic_stim, 0, 1))
        
        fam_example_pic_fn = op.join(exp['stim_data_dir'], 
                                     'instruction_stim_illustration_reading_%s.png' % \
                                     exp['language'])
        pic_stim = stimuli.Picture(fam_example_pic_fn)
        pic_stim.scale_to_fullscreen()
        sessions.append((pic_stim, 0, 1))
        
        msg_fam_test = Strooper.INSTRUCTIONS['fam_full_blocs'][self.input_type][exp['language']]
        stim_instr = stimuli.TextBox(msg_fam_test, 
                                     size=(exp['scr_w']*.6, exp['scr_h']*.7),
                                     text_size=fam_text_size,
                                     text_justification=0)
        rest_duration = 5000 # millisecond
        sessions.append((Session('Session_fam_test', NO_TRIGGER,
                         [Block('Block_fam_test_intro', NO_TRIGGER,
                                [Trial('Trial_fam_test_intro', NO_TRIGGER,
                                     [Stim('Stim_fam_test_intro', None, NO_TRIGGER,
                                           'DUMMY', {cst.K_SPACE:'DUMMY'},
                                           [stim_instr])])]),
                          Block('rest', NO_TRIGGER,
                                [Trial('rest', NO_TRIGGER,
                                       [rest_stim(rest_duration, exp)])]),
                          self.gen_naming_block(exp, show_performance=False, rng=rng),
                          Block('rest', NO_TRIGGER,
                                [Trial('rest', NO_TRIGGER,
                                       [rest_stim(rest_duration, exp)])]),
                          self.gen_switching_block(exp, show_performance=True, rng=rng),
                          Block('rest', NO_TRIGGER,
                                [Trial('rest', NO_TRIGGER,
                                       [rest_stim(rest_duration, exp)])])
                          ]), 0, 1))
        return sessions


    def gen_main_session(self, exp, session_type, session_label, rng=None):

        seed = int(hashlib.sha256(session_label.encode('utf-8')).hexdigest(),
                   16) % 10**8
        print('Random seed digested from %s: %d' % (session_label, seed))
        rng = default_rng(seed) # np.random.seed(seed)
        if session_type == 'block':
            return self.gen_main_session_block(exp, session_label, rng)
        else:
            return self.gen_main_session_event_related(exp, session_label, rng)


    def gen_main_session_event_related(self, exp, session_label, rng):
        # Trials: NX, NI, RI
        nb_switching = Strooper.ER_NB_SWITCHING
        nb_naming_inhib = Strooper.ER_NB_INHIB
        nb_naming_control = Strooper.ER_NB_CONTROL
        nb_trials = nb_switching + nb_naming_inhib + nb_naming_control

        stim_seq = gen_random_stroop_seq(nb_naming_control=nb_naming_control,
                                         nb_naming_inhib=nb_naming_inhib,
                                         nb_switching=nb_switching,
                                         rng=rng)

        isis_ms = rng.exponential(scale=Strooper.ER_ISI_MEAN_MS - Strooper.ER_ISI_MIN_MS,
                                  size=nb_trials) + Strooper.ER_ISI_MIN_MS
        print('Params for ISIs: min=%d, mean=%d' %(Strooper.ER_ISI_MIN_MS,
                                                   Strooper.ER_ISI_MEAN_MS))
        print('Generated ISIs: min=%d, max=%d, mean=%d' %(isis_ms.min(), isis_ms.max(),
                                                          isis_ms.mean()))
        # TODO: total session length
        return self.generate_stroop_session(exp, stim_seq, isis_ms, rng=rng)



    def generate_stroop_session(self, exp, stim_seq, isis_ms, rng=None):

        next_trials = {'naming' : {'control': {}, 'inhibition' : {}},
                       'reading' : {'inhibition' : {}}}
        all_sw_trials = self.gen_switch_trials(exp, prepend_cue=False)
        next_trials['reading']['inhibition'][None] = all_sw_trials
        all_ctrl_trials = self.gen_naming_trials(exp, prepend_cue=False)
        next_trials['naming']['control'][None] = all_ctrl_trials
        all_inhib_trials = self.gen_inhib_trials(exp, prepend_cue=False)
        next_trials['naming']['inhibition'][None] = all_inhib_trials
        for prev_c_name, prev_c in Strooper.COLORS.items():
            ctrl_trials = [t for t in all_ctrl_trials
                           if t.stimuli[0].expected_answer != prev_c_name]
            next_trials['naming']['control'][prev_c_name] = ctrl_trials

            inhib_trials = [t for t in all_inhib_trials
                            if t.stimuli[0].expected_answer != prev_c_name]
            next_trials['naming']['inhibition'][prev_c_name] = inhib_trials

            sw_trials = [t for t in all_sw_trials
                         if t.stimuli[0].expected_answer != prev_c_name]
            next_trials['reading']['inhibition'][prev_c_name] = sw_trials

        trials = []
        session_length_ms = Strooper.BASELINE_PRE_DURATION + \
            Strooper.BASELINE_POST_DURATION
        prev_answer = None
        for itrial, (stim_symbol, isi_ms) in enumerate(zip(stim_seq, isis_ms)):
            task, stim_type = TRIALS_SPEC[stim_symbol]
            print('prev_answer:', prev_answer)
            chosen_trial = choice(next_trials[task][stim_type][prev_answer],
                                  rng=rng)[0]
            trials.append(chosen_trial)
            session_length_ms += chosen_trial.stimuli[0].duration_ms
            prev_answer = chosen_trial.stimuli[0].expected_answer
            trials.append(Trial('rest', NO_TRIGGER, [rest_stim(isi_ms, exp)]))
            session_length_ms += isi_ms
        session_length_sec = round(session_length_ms / 1000)
        print('Total session duration = %dmin%02dsec' % (session_length_sec//60,
                                                         session_length_sec%60))
        return Session('Session_Stroop_ER', 'S',
                       [Block('rest', NO_TRIGGER,
                              [Trial('rest', NO_TRIGGER,
                                     [rest_stim(Strooper.BASELINE_PRE_DURATION,
                                                exp)])]),
                        Block('Block_Stroop_ER', None, trials,
                              show_performance=False),
                        Block('rest', NO_TRIGGER,
                              [Trial('rest', NO_TRIGGER,
                                     [rest_stim(Strooper.BASELINE_POST_DURATION,
                                                exp)])])])

    def gen_main_session_block(self, exp, session_label, rng):
        def rd_gen():
            # Variability not homogeneous and quite low with Dirichlet
            # jitters = Strooper.REST_DURATION_JITTER * \
            #           (dirichlet(np.zeros(Strooper.NB_BLOCKS)+0.01, 1) - \
            #            1./Strooper.NB_BLOCKS)[0]
            #
            # More deterministic but way more variability:
            jitters = (rng.random(Strooper.NB_BLOCKS//2) * \
                       Strooper.REST_DURATION_JITTER)
            jitters = np.concatenate((jitters.copy(), -jitters.copy()))
            if Strooper.NB_BLOCKS % 2:
                jitters = np.concatenate((jitters, [0]))
            rng.shuffle(jitters)

            all_rests = [Strooper.REST_DURATION + jitter for jitter in jitters]

            #HACK
            assert(all([rt<=(Strooper.REST_DURATION+Strooper.REST_DURATION_JITTER) \
                        for rt in all_rests]))
            assert(all([rt>=(Strooper.REST_DURATION-Strooper.REST_DURATION_JITTER) \
                        for rt in all_rests]))
            print('all_rests:', all_rests)

            while len(all_rests) > 0:
                yield all_rests.pop()

        rd = rd_gen()
        rest_blocks = [Block('rest', NO_TRIGGER,
                             [Trial('rest', NO_TRIGGER,
                                    [rest_stim(next(rd), exp)])])
                       for ir in range(Strooper.NB_BLOCKS)]

        naming_blocks = (self.gen_naming_block(exp, rng=rng)
                         for i in range(Strooper.NB_BLOCKS_NAMING))

        switching_blocks = (self.gen_switching_block(exp, rng=rng)
                             for i in range(Strooper.NB_BLOCKS_SWITCHING))

        # A-B-B-A-A-B-A-B:
        assert(Strooper.NB_BLOCKS == 8)
        stim_blocks = [naming_blocks.send(None), switching_blocks.send(None),
                       switching_blocks.send(None), naming_blocks.send(None),
                       naming_blocks.send(None), switching_blocks.send(None),
                       naming_blocks.send(None), switching_blocks.send(None)]

        all_blocks = stim_blocks + rest_blocks
        all_blocks[::2] = stim_blocks
        all_blocks[1::2] = rest_blocks

        all_blocks = [Block('baseline_pre', NO_TRIGGER,
                             [Trial('rest', NO_TRIGGER,
                                    [rest_stim(Strooper.BASELINE_PRE_DURATION, exp)])])] + \
                      all_blocks
        return Session('Strooper_main', NO_TRIGGER, all_blocks)


def run_sessions(exp_data, sessions, block_type, session_prefix, rng):
    """ 
    Run several sessions. Go to the next session only if performance
    is enough, up to a maximum number of repetitions.

    Return a dict mapping the session label to an array of performances.
    One for each session repetition.
    """
    performances = defaultdict(list)

    if callable(sessions):
        sessions = sessions(exp_data, block_type, session_prefix, rng)

    if isinstance(sessions, Session): # single session, no perf or repetition criteria
        sessions = [(sessions, 0, 1)]
    
    def randomize_session(s):
        return s

    for isession, (session, perf_min, repeat_max) in enumerate(sessions):
        i_repetition = 0
        perf = None       
        while (perf is None or perf < perf_min) and i_repetition < repeat_max:
            try:
                if i_repetition > 0:
                    session = randomize_session(session)
                perf = run_session(exp_data, session, 
                                   start_with_key=(isession==0 and i_repetition==0),
                                   show_prep_text=False)
                if isinstance(session, Session):
                    print('session ', session.label, 'perf:', perf, 'i_rep:', i_repetition,
                          'rep_max:', repeat_max)
                    performances[session_prefix + session.label].append(perf)
                i_repetition += 1 # if session aborted, will not count as repetition
            except AbortBlockException: 
                pass
            exp_data['SESSION_IDX'] += 1 # increased even if session aborted
            
    return performances
    
def run_session(exp_data, session, session_label='', start_with_key=True,
                show_prep_text=True, dual_trigger_at_start=False):
    """ Run a single session and return the average performance """

    if show_prep_text:
        stimuli.TextLine(tr("Preparing session...", exp_data['language']),
                        text_size=exp_data['TEXT_SIZE']).present()

    exp = exp_data['exp']
    subject_pin = exp_data['subject_pin']
    session_idx = exp_data['SESSION_IDX']
    test_flag = exp_data['TEST']

    if callable(session):
        session = session(exp_data, session_label)
    elif isinstance(session, stimuli.Picture):
        session.present()
        exp.keyboard.wait(keys=cst.K_SPACE)
        return None # No performance

    # Preload session stimuli:
    for b in session.blocks:
        for t in b.trials:
            for stim in t.stimuli:
                for xp_stim in stim.xp_stimuli:
                    xp_stim.preload()

    session_performance = None

    if start_with_key:
        stimuli.TextLine(tr("Press space to start session",
                            exp_data['language']) + ' ' + session_label,
                         text_size=exp_data['TEXT_SIZE']).present()
        exp.keyboard.wait(keys=cst.K_SPACE)

    reinit_triggers()

    trial_idx = 0 # session-wise trial index

    # Run session:
    trigger_on(session.char_ID, session.label)

    for block_idx, block in enumerate(session.blocks):
        trigger_on(block.char_ID, block.label)
        performance = None
        nb_expected_answers = 0
        for trial in block.trials:
            trigger_on(trial.char_ID, trial.label)
            for stim in trial.stimuli:
                ptime = 0

                nb_stims = len(stim.xp_stimuli)

                start_ts = time.time() * 1000
                for istim, xp_stim in enumerate(stim.xp_stimuli):
                    ptime += xp_stim.present(clear=istim==0,
                                             update=istim==nb_stims-1)
                trigger_on(stim.char_ID, stim.label)

                if stim.duration_ms is not None:
                    wait_duration = stim.duration_ms - ptime
                    #TODO: remove this when testing is done
                    # print('stim:', stim.label)
                    # print('ptime:', ptime)
                    # print('wait duration:', wait_duration)

                    #TODO: comment this when tests are good
                    assert(wait_duration >=0)
                else:
                    wait_duration = None

                answer = 'NA'
                if stim.responses is None:
                    # passive stimulation
                    btn,_ = exp.keyboard.wait(keys=cst.K_BACKSPACE,
                                              duration=wait_duration)
                    rt = None
                    if btn == cst.K_BACKSPACE:
                        trigger_off(stim.char_ID, stim.label)
                        trigger_off(trial.char_ID, trial.label)
                        trigger_off(block.char_ID, block.label)
                        trigger_off(session.char_ID, session.label)
                        exp.data.save()
                        return
                else:
                        # keyboard response expected
                    btn, rt = exp.keyboard.wait(keys=list(stim.responses.keys()),
                                                duration=wait_duration)
                    if wait_duration is not None and rt is not None:
                        exp.clock.wait(wait_duration-rt)
                    if btn is not None:
                        answer = stim.responses[btn]

                    # print('answer:', answer)
                    # print('stim.expected_answer:', stim.expected_answer)
                    if stim.expected_answer is not None and stim.expected_answer != 'DUMMY':
                        if performance is None:
                            performance = 1. * (answer == stim.expected_answer)
                        else:
                            performance += 1. * (answer == stim.expected_answer)
                        nb_expected_answers += 1

                trigger_off(stim.char_ID, stim.label)

                # print 'Stim', stim.label, 'duration=', stim.duration_ms, \
                #     'ptime=', ptime

                # Save data
                end_ts = time.time() * 1000
                exp.data.add([subject_pin, session_idx, test_flag,
                              session.label, block.label, block_idx, trial.label,
                              trial_idx, stim.label, "%f" % start_ts,
                              "%f" % end_ts, stim.expected_answer,
                              answer, rt]) # takes max 0.15 ms on rpi4

            trigger_off(trial.char_ID, trial.label)
            trial_idx += 1
        trigger_off(block.char_ID, block.label)
        if block.show_performance and performance is not None:
            start_ts = time.time() * 1000
            perf_perc = performance * 100. / nb_expected_answers
            stimuli.TextLine('performance = %1.2f%%' % perf_perc,
                             text_size=exp_data['TEXT_SIZE']).present()
            exp.clock.wait(2000)
            end_ts = time.time() * 1000
            exp.data.add([subject_pin, session_idx, test_flag,
                          session.label, block.label, block_idx, 'perf_feedback',
                          'NA', -1, "%f" % start_ts, "%f" % end_ts,
                          'NA', '%1.2f' % perf_perc, 'NA'])

        if performance is not None:
            if session_performance is None:
                session_performance = 0.0
            session_performance += performance / len(session.blocks)

    trigger_off(session.char_ID, session.label)
    exp.events.save() #debug
    exp.data.save()
    reset_triggers()

    # Unload stimuli:
    for b in session.blocks:
        for t in b.trials:
            for stim in t.stimuli:
                for xp_stim in stim.xp_stimuli:
                    xp_stim.unload()

    return session_performance


def main():
    """
    Usage:
    """
    min_args = 2
    max_args = 2

    usage = 'usage: %prog [options] ACQUISITION_TAG SESSION_TYPE'
    description = 'Run the color stroop task'
    parser = default_task_arg_parser(usage, description)
    
    (options, args) = parser.parse_args()
    logger.setLevel(options.verbose)

    nba = len(args)
    if (not options.unit_tests and
        (nba < min_args or (max_args >= 0 and nba > max_args))):
        parser.print_help()
        sys.exit(1)

    if options.test or options.unit_tests:
        control.set_develop_mode(True)

    if not options.unit_tests:
        subject_pin, session_type = args

    ### init ###
    exp = design.Experiment("stroop_color_%s" % session_type)
    exp.data_variable_names = ["subject_id", "session_idx", "test_flag",
                               "session_label",  "block_label", "block_idx",
                               "trial_label", "trial_idx", "stim_label",
                               "stim_start_timestamp",
                               "stim_end_timestamp", "expected_answer",
                               "answer", "reaction_time"]

    exp = control.initialize(exp)

    ### Start expyriment ###
    control.start(auto_create_subject_id=True, skip_ready_screen=True)
    # exp.set_log_level(2) #debug
    # exp.keyboard.set_logging(True) #debug 
    # exp.mouse.show_cursor()

    exp_data = {}

    exp_data['language'] = options.language
    exp_data['subject_pin'] = subject_pin if not options.unit_tests else 'test'
    exp_data['SESSION_IDX'] = 1 # TODO: when main session needs to be redone...

    exp_data['scr_w'] = exp.screen.size[0]
    exp_data['scr_h'] = exp.screen.size[1]
    exp_data['exp'] = exp

    exp_data['TEST'] = options.test

    exp_data['CROSS_SIZE'] = 80
    exp_data['TEXT_SIZE'] = 80

    exp_data['TXT_FRAME_PAD'] = exp.screen.size[1] * 0.025
    exp_data['TXT_FRAME_LW'] = 2
    exp_data['TXT_FRAME_COLOR'] = cst.C_WHITE
    exp_data['OS'] = ['desktop','android'][is_android_running()]

    exp_data['DUAL_TRIGGER_DURATION_MS'] = 100
    exp_data['DUAL_TRIGGER_POST_DURATION_MS'] = 1000

    if options.unit_tests:
        exp_data['TEST'] = False
        utests(exp_data)
        sys.exit(0)

    strooper = Strooper(input_type=Strooper.INPUT_KBD)

    rng = default_rng(56341)

    session_actions = OrderedDict()

    session_actions['test_input'] = \
                    (strooper.gen_familiarization_input_session,
                     'block', 'fam_input', rng)

    session_actions['instructions'] = \
                    (strooper.gen_familiarization_full_sessions,
                     'block', 'fam_full', rng)

    session_actions['practice'] = \
                    (strooper.gen_familiarization_switching_session,
                     'block', 'fam_switch', rng)

    session_actions['main_block'] = (strooper.gen_main_session, 'block',
                                     'main_block', None)
    session_actions['main_ER'] = (strooper.gen_main_session, 'ER',
                                  'main_ER', None)
    try:
        selection = session_type
        run_sessions(exp_data, session_actions[selection][0],
                     session_actions[selection][1], session_actions[selection][2],
                     session_actions[selection][3])
    except AbortBlockException: #TODO: put in run_sessions
        pass
    exp_data['SESSION_IDX'] += 1 #TODO: put in run_sessions
        
    ## End expyriment ##
    control.end()

#### Tests ####

def save_stim_snapshots(exp_data):
    strooper = Strooper(input_type=Strooper.INPUT_SPEECH)
    fig_dir = 'snapshots'
    if not op.exists(fig_dir):
        os.makedirs(fig_dir)

    for t in strooper.get_all_possible_trials(exp_data):
        for stim in t.stimuli:
            nb_stims = len(stim.xp_stimuli)
            for istim, xp_stim in enumerate(stim.xp_stimuli):
                xp_stim.present(clear=istim==0,
                                update=istim==nb_stims-1)
                snapshot_fn = op.join(fig_dir, '_'.join([t.label,
                                                         stim.label, 
                                                         str(stim.expected_answer)])) + \
                                                         '.png'
                exp_data['exp'].screen.save(snapshot_fn)

def test_main_menu(exp_data):
    show_main_menu(exp_data)


def test_rest_block(exp_data):
    strooper = Strooper()
    main_session = strooper.gen_main_session(exp_data)
    perfs = run_sessions(exp_data, Session('Strooper_REST', NO_TRIGGER,
                                           [main_session.blocks[1]]),
                         'test_')
    assert(perfs['test_Strooper_REST'] == [None])

def test_exe_block(exp_data):
    strooper = Strooper()
    main_session = strooper.gen_main_session(exp_data)
    perfs = run_sessions(exp_data, [(Session('Strooper_SWITCH', NO_TRIGGER,
                                            [main_session.blocks[2]]), 0, 3)],
                        'test_')
    assert(perfs['test_Strooper_SWITCH']==[0])

def test_exe_block_repeat(exp_data):
    strooper = Strooper()
    main_session = strooper.gen_main_session(exp_data)
    perfs = run_sessions(exp_data, [(Session('Strooper_SWITCH', NO_TRIGGER,
                                            [main_session.blocks[2]]), 1, 2)],
                         'test_rep_')
    assert(perfs['test_rep_Strooper_SWITCH']==[0, 0])


def test_fam_full_intro(exp):
    msg_fam_test = Strooper.INSTRUCTIONS['fam_full_blocs'][Strooper.INPUT_SPEECH][exp['language']]

    stim_instr = stimuli.TextBox(msg_fam_test, 
                             size=(exp['scr_w']*.6, exp['scr_h']*.7),
                             text_size=50,
                             text_justification=0)
    session = Session('Session_fam_test', NO_TRIGGER,
                      [Block('Block_fam_test_intro', NO_TRIGGER,
                                [Trial('Trial_fam_test_intro', NO_TRIGGER,
                                     [Stim('Stim_fam_test_intro', None, NO_TRIGGER,
                                           'DUMMY', {cst.K_SPACE:'DUMMY'},
                                           [stim_instr])])])])
    perfs = run_sessions(exp, session, 'test_')
    assert(perfs['test_fam_test']==[None])

def test_chained_sessions(exp_data):
    strooper = Strooper()
    main_session = strooper.gen_main_session(exp_data)
    perfs = run_sessions(exp_data, [(Session('Strooper_REST', NO_TRIGGER,
                                            [main_session.blocks[1]]), 1, 1),
                                    (Session('Strooper_SWITCH', NO_TRIGGER,
                                            [main_session.blocks[2]]), 1, 2)],
                         'test_chain_')
    assert(perfs['test_chain_Strooper_SWITCH']==[0, 0])
    assert(perfs['test_chain_Strooper_REST']==[None])

def test_blank(exp_data):
    stimuli.BlankScreen().present()
    exp_data['exp'].clock.wait(200)


def utests(exp_data):
    utest_gen_event_related(exp_data)
    utest_zip_join()
    utest_main_session_seed(exp_data)
    utest_choice(exp_data)

def utest_zip_join():
    l = [1, 2, 3, 4, 5]
    i = ['a', 'b', 'c', 'd']
    assert zip_join(l,i)==[1, 'a', 2, 'b', 3, 'c', 4, 'd', 5]

from numpy.random import default_rng

def gen_random_stroop_seq(nb_naming_control, nb_naming_inhib, nb_switching,
                          rng=None):
    """
    Generate a random sequence of Stroop stimuli where switching trials
    are always after a naming_inhib trial.
    """
    assert(nb_switching < nb_naming_inhib)
    stim_seq = np.concatenate((np.zeros(nb_naming_control, dtype=int) + TRIAL_NX,
                               np.zeros(nb_naming_inhib, dtype=int) + TRIAL_NI))
    rng.shuffle(stim_seq)

    itrial_ni_for_sw = rng.choice(nb_naming_inhib, size=nb_switching,
                                  replace=False)

    itrial_switching = set(np.where(stim_seq==TRIAL_NI)[0][itrial_ni_for_sw])
    trial_seq = []
    for itrial, trial in enumerate(stim_seq):
        trial_seq.append(trial)
        if itrial in itrial_switching:
            trial_seq.append(TRIAL_RI)
    return trial_seq

def generate_stroop_session(trial_sequence, isis):
    for itrial, trial_symbol, isi in enumerate(trial_sequence):
        pass

def utest_gen_event_related(exp_data):
    rng = default_rng()

    # Trials: NX, NI, RI
    nb_switching = 25
    nb_naming_inhib = nb_switching * 3
    nb_naming_control = nb_switching
    nb_trials = nb_switching + nb_naming_inhib + nb_naming_control

    stim_seq = gen_random_stroop_seq(nb_naming_control=nb_naming_control,
                                     nb_naming_inhib=nb_naming_inhib,
                                     nb_switching=nb_switching,
                                     rng=rng)

    mean_isi_ms = 4000
    isis_ms = rng.exponential(scale=mean_isi_ms, size=nb_trials)
    strooper = Strooper()
    session = strooper.generate_stroop_session(exp_data, stim_seq, isis_ms, rng=rng)



    if len(session.blocks) != 3:
        raise Exception('len(blocks)=%d != 3' % len(session.blocks))
    all_isis = np.zeros(nb_trials)

    istim = 0
    for itrial, trial in enumerate(session.blocks[1].trials):
        if itrial%2 != 0:
            if trial.stimuli[0].label != 'Stim_rest':
                raise Exception('trial.stimuli[0].label=%s != Stim_rest' % \
                                trial.stimuli[0].label)
            try:
                all_isis[istim] = trial.stimuli[0].duration_ms
            except IndexError:
                from IPython import embed; embed()
            istim += 1
        else:
            pass
    if not np.allclose(all_isis.mean(), mean_isi_ms, atol=350):
        raise Exception('actual mean ISI %d ms != expected ISI of %d ms' % \
                        (all_isis.mean(), mean_isi_ms))

def utest_main_session_seed(exp_data):

    strooper = Strooper()

    # Check that main session generation gives constant result
    # even if random generator is used in between calls
    main_session1 = strooper.gen_main_session(exp_data, 'ER', 'test')
    randint(0,10000,100)
    main_session1_regen = strooper.gen_main_session(exp_data, 'ER', 'test')
    assert_sessions_equal(main_session1, main_session1_regen)

    main_session1_again = strooper.gen_main_session(exp_data, 'ER', 'test')
    randint(0,10000,100)
    main_session1_again_regen = strooper.gen_main_session(exp_data, 'ER', 'test')
    assert_sessions_equal(main_session1_again, main_session1_again_regen)
    assert_sessions_equal(main_session1_again, main_session1)


def assert_sessions_equal(s1, s2):
    assert(len(s1.blocks) == len(s2.blocks))
    for b1,b2 in zip(s1.blocks, s2.blocks):
        assert(b1.label == b2.label)
        assert(b1.char_ID == b2.char_ID)
        assert(len(b1.trials) == len(b2.trials))
        for t1,t2 in zip(b1.trials, b2.trials):
            assert(t1.label == t2.label)
            assert(t1.char_ID == t2.char_ID)
            assert(len(t1.stimuli) == len(t2.stimuli))
            for stim1,stim2 in zip(t1.stimuli, t2.stimuli):
                assert(stim1.label == stim2.label)
                assert(stim1.expected_answer == stim2.expected_answer)
                assert(stim1.char_ID == stim2.char_ID)
                assert(stim1.duration_ms == stim2.duration_ms)
                assert(len(stim1.xp_stimuli) == len(stim2.xp_stimuli))

def utest_choice(exp_data):
    seq = list(range(10))
    set_seq = set(seq)
    nb_samples = 5000

    def check_freqs(nb_picks):
        counts = np.zeros((nb_picks, len(seq)))
        for i in range(nb_samples):
            rnd = choice(seq, nb_picks).astype(np.int)
            for j,n in enumerate(rnd):
                counts[j,n] += 1.0
            if nb_picks >= len(seq):
                # Check that there is always one representation of each
                # element when nb of picks is larger than nb of elements:
                assert(set(rnd) ==  set_seq)
        np.testing.assert_allclose(counts / nb_samples,
                                   np.zeros((nb_picks, len(seq))) + 1./len(seq),
                                   atol=0.015)
    check_freqs(5)
    check_freqs(len(seq))
    check_freqs(15)

test_suite = [save_stim_snapshots, test_main_menu,
              test_blank,
              test_fam_full_intro,
              test_exe_block, test_rest_block,
              test_exe_block_repeat, test_chained_sessions,
              utests]
