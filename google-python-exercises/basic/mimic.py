import random
import sys


def mimic_dict(filename):
    with open(filename, encoding='utf-8') as f:
        words = f.read().split()
    d = {}
    prev = ''
    for w in words:
        d.setdefault(prev, []).append(w)
        prev = w
    d.setdefault(prev, [])
    return d


def print_mimic(mimic_dict, word):
    out = []
    for _ in range(200):
        out.append(word)
        choices = mimic_dict.get(word)
        word = random.choice(choices) if choices else ''
    line = ''
    for w in out:
        if len(line) + len(w) + 1 > 70:
            print(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    if line:
        print(line)


def main():
    if len(sys.argv) != 2:
        print('usage: ./mimic.py file-to-read')
        sys.exit(1)
    print_mimic(mimic_dict(sys.argv[1]), '')


if __name__ == '__main__':
    main()
