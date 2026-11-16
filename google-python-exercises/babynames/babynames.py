import re
import sys


def extract_names(filename):
    with open(filename, encoding='utf-8') as f:
        text = f.read()

    names = []
    m = re.search(r'Popularity in (\d{4})', text)
    if m:
        names.append(m.group(1))

    name_rank = {}
    for rank, boy, girl in re.findall(r'<td>(\d+)</td><td>(\w+)</td><td>(\w+)</td>', text):
        name_rank.setdefault(boy, rank)
        name_rank.setdefault(girl, rank)

    for name in sorted(name_rank):
        names.append(name + ' ' + name_rank[name])

    return names


def main():
    args = sys.argv[1:]
    if not args:
        print('usage: [--summaryfile] file [file ...]')
        sys.exit(1)

    summary = False
    if args[0] == '--summaryfile':
        summary = True
        del args[0]

    for filename in args:
        text = '\n'.join(extract_names(filename))
        if summary:
            with open(filename + '.summary', 'w', encoding='utf-8') as f:
                f.write(text + '\n')
        else:
            print(text)


if __name__ == '__main__':
    main()
