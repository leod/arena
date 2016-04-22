#!/usr/bin/env python
import sys; sys.path.append("..")
#import random
import copy
import datetime
import logging
import math
from random import choice

import fireplace.logging
from fireplace import cards
from fireplace.cards.heroes import *
from fireplace.exceptions import GameOver
from fireplace.entity import Entity
from fireplace.game import Game
from fireplace.player import Player
from fireplace.utils import random_draft
from hearthstone.enums import PlayState

class SearchState(object):
    def current_player(self):
        pass
    def next_state(self, play):
        pass
    def legal_plays(self):
        pass
    def copy_and_play(self, play):
        pass
    def winner(self):
        pass

class Play(object):
    def play():
        pass

class HeroPowerPlay(Play):
    def __init__(self, target_idx=None):
        self.target_idx = target_idx

    def play(self, game):
        player = game.current_player
        heropower = game.current_player.hero.power

        if self.target_idx != None:
            heropower.use(target=heropower.targets[self.target_idx])
        else:
            heropower.use()

class CardPlay(Play):
    def __init__(self, card_idx, choice_idx=None, target_idx=None):
        self.card_idx = card_idx
        self.choice_idx = choice_idx
        self.target_idx = target_idx

    def play(self, game):
        player = game.current_player
        card = player.hand[self.card_idx]

        target = None
        if card.choose_cards:
            card = card.choose_cards[self.choice_idx]
        if card.has_target():
            target = card.targets[self.target_idx]

        card.play(target=target)

class ChoicePlay(Play):
    def __init__(self, choice_idx):
        self.choice_idx = choice_idx

    def play(self, game):
        choice = game.current_player.choice
        choice.choose(choice.cards[self.choice_idx])

class AttackPlay(Play):
    def __init__(self, character_idx, target_idx):
        self.character_idx = character_idx
        self.target_idx = target_idx

    def play(self, game):
        player = game.current_player
        character = player.characters[self.character_idx]
        character.attack(character.targets[self.target_idx])

class EndTurnPlay(Play):
    def play(self, game):
        game.end_turn()
        
def entity_hash(e, from_e=None):
    hashes = ()
    for k, v in e.manager.items():
        if isinstance(v, Entity):
            if v is from_e:
                continue # Ignore, so that we don't cycle forever
            else:
                hashes += (entity_hash(v, from_e=e),)  
        else:
            hashes += (hash(k), hash(v))

    return hash(hashes) 

def entity_eq(a, b, from_a=None, from_b=None):
    if a.type != b.type:
        return False

    a_items = list(a.manager.items())
    b_items = list(b.manager.items())

    if len(a_items) != len(b_items):
        return False

    for (k1, x), (k2, y) in zip(a_items, b_items):
        if isinstance(x, Entity):
            if not isinstance(y, Entity):
                return False

            if x is from_a and y is from_b: # This detects immediate cycles
                return True

            if not entity_eq(x, y, a, b):
                return False
        elif x != y:
            return False

    return True

def hash_game(game):
    hashes = ()
    for e in game.entities:
        hashes += (entity_hash(e),)
    return hash(hashes)

class GameState(object):
    def __init__(self, game):
        self.game = game
        self.hash_value = hash_game(game)

    def __hash__(self):
        assert self.hash_value != None
        return self.hash_value

    def __eq__(self, other):
        if self.hash_value != other.hash_value:
            print("HASH")
            return False

        entities = self.game.entities
        other_entities = other.game.entities

        if len(entities) != len(other_entities):
            return False

        for a, b in zip(entities, other_entities):
            if not entity_eq(a, b):
                return False

        return True

    def current_player(self):
        return 0 if self.game.current_player is self.game.player1 else 1

    def legal_plays(self):
        plays = []

        player = self.game.current_player
        heropower = player.hero.power
        
        if not player.choice:
            if heropower.is_usable():
                if heropower.has_target():
                    for target_idx in range(len(heropower.targets)):
                        plays.append(HeroPowerPlay(target_idx))
                else:
                    plays.append(HeroPowerPlay())

            for card_idx, card in enumerate(player.hand):
                if card.is_playable():
                    if card.choose_cards and card.has_target():
                        for choice_idx, chosen_card in enumerate(card.choose_cards):
                            for target_idx in range(len(chosen_card.targets)):
                                plays.append(CardPlay(card_idx, choice_idx=choice_idx, target_idx=target_idx))
                    elif card.has_target():
                        for target_idx in range(len(card.targets)):
                            plays.append(CardPlay(card_idx, target_idx=target_idx))
                    elif card.choose_cards:
                        for choice_idx in range(len(card.choose_cards)):
                            plays.append(CardPlay(card_idx, choice_idx=choice_idx))
                    else:
                        plays.append(CardPlay(card_idx))

            for character_idx, character in enumerate(player.characters):
                if character.can_attack():
                    for target_idx in range(len(character.targets)):
                        plays.append(AttackPlay(character_idx, target_idx))

            plays.append(EndTurnPlay())
        else: 
            for choice_idx in range(len(player.choice.cards)):
                plays.append(ChoicePlay(choice_idx))

        return plays

    def copy_and_play(self, play):
        next_game = copy.deepcopy(self.game)
        #log.debug("COPY AND PLAY %r", play)

        try:
            play.play(next_game)
        except GameOver:
            pass

        return GameState(next_game)

    def winner(self):
        if self.game.player1.playstate == PlayState.WON:
            return 0
        elif self.game.player2.playstate == PlayState.WON:
            return 1
        elif self.game.player1.playstate == PlayState.TIED:
            return -1
        else:
            return None

class StateStats(object):
    wins = 0
    plays = 0

class MonteCarlo(object):
    def __init__(self, state, seconds, max_moves=100):
        self.state_stats = {}
        self.state = state
        self.calculation_time = datetime.timedelta(seconds=seconds)
        self.max_moves = max_moves

    def run_simulation(self):
        visited_states = set()
        state = self.state
        player = state.current_player()

        expand = True
        for t in range(self.max_moves):
            legal_plays = state.legal_plays()
            plays_states = [(p, state.copy_and_play(p)) for p in legal_plays]

            if all(self.state_stats.get((player, s)) for p, s in plays_states):
                log.debug("COOL NODE")
                log_total = math.log(sum(self.state_stats[(player, s)].plays for p, s in plays_states))

                play_values = []
                for p, s in plays_states:
                    stats = self.state_stats[(p, s)]
                    win_prob = stats.wins / float(stats.plays)
                    bound = self.C * math.sqrt(log_total / float(stats.plays))

                    play_values.append((win_prob + bound, p, s))

                value, play, state = max(play_values)
            else:
                play = choice(legal_plays)
                state = state.copy_and_play(play)
                log.debug("MCTS RANDOM PLAY %r", play)

            if expand and (player, state) not in self.state_stats:
                expand = False
                self.state_stats[(player, state)] = StateStats()

            visited_states.add((player, state))

            player = state.current_player()
            winner = state.winner()

            if winner != None:
                break

        for player, state in visited_states:
            if (player, state) not in self.state_stats:
                continue
            stats = self.state_stats[(player, state)] 
            stats.plays += 1
            if player == winner:
                stats.wins += 1
            if t > self.max_depth:
                self.max_depth = t

    def get_play(self):
        self.max_depth = 0
        state = self.state
        player = state.current_player()
        legal_plays = state.legal_plays()

        #if len(legal_plays) == 1:
            #return legal_plays[0]

        games = 0
        begin_time = datetime.datetime.utcnow()
        while datetime.datetime.utcnow() - begin_time < self.calculation_time:
            log.info("SIMULATION %d", games)
            self.run_simulation()
            games += 1

        print((games, datetime.datetime.utcnow() - begin_time))

        plays_states = [(p, self.state.copy_and_play(p)) for p in legal_moves]

        play_win_probs = []
        for play, next_state in plays_states:
            stats = self.state_stats.get((player, next_state), None)
            if stats:
                win_prob = stats.wins / float(stats.plays)
            else:
                win_prob = 0.0
            play_win_probs.append((play, win_prob, stats))

        percent_wins, move, _ = max(play_win_probs)

        for percent_wins, move, stats in sorted(play_win_probs):
            print("{}: {0:.2f}% ({} / {}".format(move, percent_wins, stats.wins, stats.plays))

        print("Maximum depth searched: " + str(self.max_depth))

        return play


def play_full_game(hero1, deck1, hero2, deck2):
    log.info('{} vs {}'.format(hero1, hero2))
    player1 = Player("Player1", deck1, hero1)
    player2 = Player("Player2", deck2, hero2)

    game = Game(players=(player1, player2))
    game.start()

    # Random mulligan for now
    for player in game.players:
        if player.choice:
            player.choice.choose()

    print(repr(game))
    return

    begin_time = datetime.datetime.utcnow()
    N = 1000
    for i in range(N):
        game2 = copy.deepcopy(game)
    end_time = datetime.datetime.utcnow()
    print((end_time - begin_time))
    return

    try:
        while True:
            state = GameState(game)

            #if state.winner() != None:
                #print("Winner: " + str(state.winner()))
                #break

            mcts = MonteCarlo(state, 1)
            play = mcts.get_play()

            log.info("GOT A MOVE!!!! %r", play)
            break

            fireplace.logging.log.setLevel(logging.DEBUG)
            play.play(game)
            fireplace.logging.log.setLevel(logging.WARN)
    except GameOver:
        state = GameState(game)
        if state.winner() != None:
            log.info("Winner: " + str(state.winner()))

def load_deck(filename):
    hero = None
    deck = []

    with open(filename) as f:
        for line in f.readlines():
            card_name = line[0:-1]

            if not hero:
                hero = card_name
                continue

            if card_name not in cards.db:
                sys.stderr.write('Card not found: ' + card_name)
                return None

            #print(cards.db[card_name])
            #print(type(cards.db[card_name]))

            deck.append(cards.db[card_name].id)

    return (hero, deck)

log = fireplace.logging.get_logger('mcts')

def main():
    cards.db.initialize()
    fireplace.logging.log.setLevel(logging.WARN)

    (hero1, deck1) = load_deck(sys.argv[1])
    (hero2, deck2) = load_deck(sys.argv[2])
    #return

    play_full_game(hero1, deck1, hero2, deck2)

if __name__ == "__main__":
    main()
