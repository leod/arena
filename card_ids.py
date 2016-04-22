import json
import sys

with open(sys.argv[1]) as f:
    cards = json.loads(f.read())

while True:
    try:
        line = input()
    except EOFError:
        break
    found = False
    for card in cards:
        if card['name'] == line and (card['type'] == 'MINION' or card['type'] == 'SPELL' or card['type'] == 'WEAPON'):
            print(card['id'])
            found = True
            break
    if not found:
        sys.stderr.write('Card not found ' + str(line) + '\n')

