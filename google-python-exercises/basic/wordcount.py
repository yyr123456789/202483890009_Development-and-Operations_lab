import sys


def _word_counts(filename):
    counts = {}
    with open(filename, encoding='utf-8') as f:
        for word in f.read().split():
            w = word.lower()
            counts[w] = counts.get(w, 0) + 1
    return counts


def print_words(filename):
    counts = _word_counts(filename)
    for w in sorted(counts):
        print(w, counts[w])


def print_top(filename):
    counts = _word_counts(filename)
    for w, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
        print(w, c)


def main():
    if len(sys.argv) != 3:
        print('usage: ./wordcount.py {--count | --topcount} file')
        sys.exit(1)
    option, filename = sys.argv[1], sys.argv[2]
    if option == '--count':
        print_words(filename)
    elif option == '--topcount':
        print_top(filename)
    else:
        print('unknown option: ' + option)
        sys.exit(1)


if __name__ == '__main__':
    main()
