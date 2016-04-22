#!/usr/bin/env python
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

cards.db.initialize()
fireplace.logging.log.setLevel(logging.WARN)

deck1 = random_draft(SHAMAN)
deck2 = random_draft(PALADIN)

player1 = Player("Player1", deck1, SHAMAN)
player2 = Player("Player2", deck2, PALADIN)

game = Game(players=(player1, player2))
game.start()

for player in game.players:
    if player.choice:
        player.choice.choose()

begin_time = datetime.datetime.utcnow()
N = 100
for i in range(N):
    game2 = copy.deepcopy(game)
end_time = datetime.datetime.utcnow()

print((end_time - begin_time) / N)
